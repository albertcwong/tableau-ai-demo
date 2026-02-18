'use client';

import { useEffect, useRef, useState } from 'react';
import { getViewEmbedUrl, sanitizeViewId } from '@/lib/tableau';
import { extractErrorMessage } from '@/lib/utils';
import type { TableauEmbedUrl } from '@/types';

// Declare tableau-viz web component type
declare global {
  namespace JSX {
    interface IntrinsicElements {
      'tableau-viz': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string;
        token?: string;
        'hide-tabs'?: string;
        toolbar?: string;
        device?: string;
        width?: string;
        height?: string;
      };
    }
  }
}

interface ViewEmbedderProps {
  viewId: string;
  viewName?: string;
  filters?: Record<string, string>;
  hideTabs?: boolean;
  hideToolbar?: boolean;
  device?: 'desktop' | 'phone' | 'tablet';
  onError?: (error: Error) => void;
  onUserAction?: (type: string, description: string, durationMs: number) => void;
  lastEventTsRef?: React.MutableRefObject<number>;
  className?: string;
}

/**
 * ViewEmbedder component for embedding Tableau views using Embedding API v3
 * Uses the tableau-viz web component for embedding
 */
function extractEventDescriptionSync(event: Event, eventType: string): string {
  const d = (event as CustomEvent).detail;
  if (!d || typeof d !== 'object') return eventType;
  const field = d.fieldName ?? d.field_name ?? d.field ?? d.filterField;
  const vals = d.appliedValues ?? d.applied_values ?? d.values ?? d.selectedValues;
  const sheet = d.sheetName ?? d.sheet_name ?? d.name;
  const param = d.parameterName ?? d.parameter_name ?? d.parameter;
  const val = d.value ?? d.formattedValue ?? d.formatted_value;
  if (eventType === 'filterchanged' && field) {
    const v = Array.isArray(vals) ? vals.map((x: { value?: string } | string) => (typeof x === 'object' && x && 'value' in x ? (x as { value?: string }).value : x)).filter(Boolean).join(', ') : vals;
    return v ? `filter ${field} = ${v}` : `filter ${field} (changed)`;
  }
  if (eventType === 'tabswitched' && sheet) return `tab → ${sheet}`;
  if (eventType === 'parameterchanged' && param) return `parameter ${param} = ${val ?? '(changed)'}`;
  return eventType;
}

function serializeFilter(f: { fieldName?: string; appliedValues?: unknown }): [string, string] | null {
  const field = (f as { fieldName?: string }).fieldName ?? (f as { field_name?: string }).field_name;
  const vals = (f as { appliedValues?: unknown }).appliedValues ?? (f as { applied_values?: unknown }).applied_values;
  if (!field) return null;
  const v = Array.isArray(vals)
    ? vals.map((x: { value?: string } | string) => (typeof x === 'object' && x && 'value' in x ? (x as { value?: string }).value : x)).filter(Boolean).join(', ')
    : String(vals ?? '');
  return [field, v ? `${field}=${v}` : `${field}=(changed)`];
}

async function extractEventDescriptionAsync(
  event: Event,
  eventType: string,
  lastFilterStateRef?: { current: Record<string, string> | null }
): Promise<string> {
  const viz = (event.target as HTMLElement) as unknown as {
    workbook?: { activeSheet?: { getFiltersAsync?: () => Promise<unknown[]>; name?: string } };
  };
  const d = (event as CustomEvent).detail;

  // Prefer event detail for filterchanged - it contains only the changed filter
  if (eventType === 'filterchanged') {
    const syncDesc = extractEventDescriptionSync(event, eventType);
    if (syncDesc !== 'filterchanged') return syncDesc;
    // Fallback: diff current vs previous to record only what changed
    if (viz?.workbook?.activeSheet?.getFiltersAsync) {
      try {
        const filters = await viz.workbook.activeSheet.getFiltersAsync();
        if (Array.isArray(filters) && filters.length > 0) {
          const current: Record<string, string> = {};
          const parts: string[] = [];
          for (const f of filters as { fieldName?: string; appliedValues?: unknown }[]) {
            const pair = serializeFilter(f);
            if (!pair) continue;
            const [field, serialized] = pair;
            current[field] = serialized;
            const prev = lastFilterStateRef?.current ?? {};
            if (prev[field] !== serialized) {
              const val = serialized.split('=').slice(1).join('=');
              parts.push(val === '(changed)' ? `${field} (changed)` : `${field} = ${val}`);
            }
          }
          if (lastFilterStateRef) lastFilterStateRef.current = current;
          return parts.length > 0 ? `filter ${parts.join('; ')}` : 'filter (changed)';
        }
      } catch (e) {
        console.warn('[ViewEmbedder] getFiltersAsync failed:', e);
      }
    }
  }

  if (eventType === 'markselectionchanged') {
    const getMarks = d?.getMarksAsync ?? (typeof d === 'object' && d && 'getMarksAsync' in d ? (d as { getMarksAsync?: () => Promise<unknown> }).getMarksAsync : null);
    if (typeof getMarks === 'function') {
      try {
        const marks = await getMarks.call(d);
        const data = (marks as { data?: unknown[] })?.data;
        const first = Array.isArray(data) ? data[0] : undefined;
        const count = (first as { data?: unknown[] } | undefined)?.data?.length ?? (marks as { totalRowCount?: number })?.totalRowCount;
        return count != null ? `mark selection (${count} marks)` : 'mark selection';
      } catch (e) {
        console.warn('[ViewEmbedder] getMarksAsync failed:', e);
      }
    }
  }

  return extractEventDescriptionSync(event, eventType);
}

export function ViewEmbedder({
  viewId,
  viewName,
  filters,
  hideTabs = false,
  hideToolbar = false,
  device = 'desktop',
  onError,
  onUserAction,
  lastEventTsRef,
  className = '',
}: ViewEmbedderProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [embedInfo, setEmbedInfo] = useState<TableauEmbedUrl | null>(null);
  const [iframeAuthRetry, setIframeAuthRetry] = useState(false);
  const vizRef = useRef<HTMLElement | null>(null);
  const [containerHeight, setContainerHeight] = useState<number | null>(null);
  const onUserActionRef = useRef(onUserAction);
  const onErrorRef = useRef(onError);
  const lastFilterStateRef = useRef<Record<string, string> | null>(null);
  onUserActionRef.current = onUserAction;
  onErrorRef.current = onError;

  useEffect(() => {
    let mounted = true;

    async function loadEmbedUrl() {
      try {
        setLoading(true);
        setError(null);
        setIframeAuthRetry(false);

        const embedData = await getViewEmbedUrl(viewId, filters);
        if (!mounted) return;

        // Check for mixed content issue: HTTPS page trying to load HTTP resource
        if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
          const embedUrl = new URL(embedData.url);
          if (embedUrl.protocol === 'http:') {
            const errorMsg = 'Mixed Content Error: This page is served over HTTPS, but the Tableau server is configured with HTTP. Please configure your Tableau server to use HTTPS, or update the server URL in the Tableau Connected App configuration to use HTTPS.';
            setError(errorMsg);
            setLoading(false);
            onErrorRef.current?.(new Error(errorMsg));
            return;
          }
        }

        // Check for potential SSL certificate issues with EC2 hostnames
        const embedUrl = new URL(embedData.url);
        if (embedUrl.hostname.includes('ec2-') && embedUrl.hostname.includes('.compute.amazonaws.com')) {
          console.warn('Warning: Tableau server is using an EC2 hostname which may have SSL certificate issues. ' +
            'If you encounter ERR_CERT_COMMON_NAME_INVALID errors, configure a valid SSL certificate or use a reverse proxy.');
        }

        setEmbedInfo(embedData);
      } catch (err: any) {
        if (!mounted) return;
        const errorMessage = extractErrorMessage(err, 'Failed to load embed URL');
        const isPATError = errorMessage.includes('Personal Access Token') || 
                          errorMessage.includes('PAT') ||
                          (err?.response?.status === 400 && errorMessage.includes('embedding'));
        if (isPATError) {
          const patErrorMsg = 'View embedding is not supported with PAT. Connect with Connected App to embed views.';
          setError(patErrorMsg);
          setLoading(false);
          onErrorRef.current?.(new Error(patErrorMsg));
          return;
        }
        setError(errorMessage);
        setLoading(false);
        onErrorRef.current?.(err instanceof Error ? err : new Error(errorMessage));
      }
    }

    loadEmbedUrl();

    return () => {
      mounted = false;
    };
  }, [viewId, filters, onError]);

  // ResizeObserver to track container height
  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = entry.contentRect.height;
        setContainerHeight(height);
        // Update viz height if it exists
        if (vizRef.current && height > 0) {
          vizRef.current.setAttribute('height', `${height}px`);
        }
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!embedInfo || !containerRef.current) return;

    let mounted = true;

    function embedView() {
      if (!embedInfo) return;
      
      try {
        setLoading(true);
        setError(null);

        // Clear container and reset filter state for new viz
        if (containerRef.current) {
          containerRef.current.innerHTML = '';
        }
        lastFilterStateRef.current = null;

        // Get container height for initial sizing
        if (!containerRef.current) return;
        const height = containerRef.current.clientHeight || containerHeight || 600;

        // Create new tableau-viz web component using Tableau Embedding API v3
        // Use sanitized viewId - suffixes like ,1:1 cause "Error parsing command parameter value string"
        if (!containerRef.current) return;
        const cleanViewId = sanitizeViewId(viewId);
        const viz = document.createElement('tableau-viz') as HTMLElement;
        viz.id = `tableau-viz-${cleanViewId}`;
        viz.setAttribute('data-view-id', cleanViewId);

        // Set required attributes per Tableau Embedding API v3 documentation
        viz.setAttribute('src', embedInfo.url);
        if (embedInfo.token) {
          viz.setAttribute('token', embedInfo.token);
        }
        if (iframeAuthRetry) {
          viz.setAttribute('iframe-auth', '');
        }

        // Optional attributes
        if (hideTabs) {
          viz.setAttribute('hide-tabs', 'true');
        }
        viz.setAttribute('toolbar', hideToolbar ? 'hidden' : 'top');
        viz.setAttribute('device', device);
        viz.setAttribute('width', '100%');
        viz.setAttribute('height', `${height}px`);

        // Append to container
        containerRef.current!.appendChild(viz);
        vizRef.current = viz;

        let viewLoaded = false;
        const markLoaded = () => {
          if (!viewLoaded && mounted) {
            viewLoaded = true;
            setLoading(false);
          }
        };

        const initFilterState = async () => {
          const wb = (viz as unknown as { workbook?: { activeSheet?: { getFiltersAsync?: () => Promise<unknown[]> } } }).workbook;
          if (wb?.activeSheet?.getFiltersAsync) {
            try {
              const filters = await wb.activeSheet.getFiltersAsync();
              if (Array.isArray(filters) && filters.length > 0) {
                const state: Record<string, string> = {};
                for (const f of filters as { fieldName?: string; appliedValues?: unknown }[]) {
                  const pair = serializeFilter(f);
                  if (pair) state[pair[0]] = pair[1];
                }
                lastFilterStateRef.current = state;
              }
            } catch {
              /* ignore */
            }
          }
        };

        const onFirstInteractive = () => {
          markLoaded();
          initFilterState();
        };
        const onTabSwitched = () => {
          markLoaded();
          initFilterState();
        };
        viz.addEventListener('firstinteractive', onFirstInteractive);
        viz.addEventListener('tabswitched', onTabSwitched);

        const eventTypes = ['firstinteractive', 'filterchanged', 'markselectionchanged', 'tabswitched', 'parameterchanged'];
        const tsRef = lastEventTsRef ?? { current: Date.now() };
        const handleUserAction = async (e: Event) => {
          const now = Date.now();
          const durationMs = now - tsRef.current;
          tsRef.current = now;
          const desc = await extractEventDescriptionAsync(e, e.type, lastFilterStateRef);
          onUserActionRef.current?.(e.type, desc, durationMs);
        };
        if (onUserActionRef.current) {
          eventTypes.forEach((t) => viz.addEventListener(t, handleUserAction));
        }

        // Listen for errors from the tableau-viz component
        const handleVizError = (event: any) => {
          if (!mounted || viewLoaded) return;
          const errorDetail = event.detail || {};
          const errorMessage = (typeof errorDetail.message === 'string' ? errorDetail.message : errorDetail.error) || 'Unknown error';
          const errorCode = errorDetail.errorCode;
          let parsed: { message?: string; errorCode?: string } = {};
          try {
            parsed = typeof errorDetail.message === 'string' ? JSON.parse(errorDetail.message) : {};
          } catch {
            parsed = {};
          }
          const code = errorCode ?? parsed.errorCode;
          const msg = parsed.message || errorMessage;

          if (msg.includes('ERR_CERT') || msg.includes('certificate') || msg.includes('SSL') || msg.includes('TLS') || msg.includes('Common Name')) {
            const certErrorMsg = 'SSL Certificate Error: The Tableau server\'s SSL certificate is invalid or doesn\'t match the hostname. ' +
              'Solutions: 1) Configure your Tableau server with a valid SSL certificate, ' +
              '2) Use a reverse proxy (nginx/Apache) with a valid certificate, or 3) Access over HTTP if security allows.';
            setError(certErrorMsg);
            setLoading(false);
            onErrorRef.current?.(new Error(certErrorMsg));
            return;
          }

          // 401 / auth errors - try iframe-auth fallback once, then show actual error
          if (code === 'unknown-auth-error' || code === 'auth-failed' || msg.includes('401') || msg.includes('unauthorized') || msg.toLowerCase().includes('auth')) {
            if (!iframeAuthRetry) {
              setIframeAuthRetry(true);
              return;
            }
            setError(msg);
            setLoading(false);
            onErrorRef.current?.(new Error(msg));
            return;
          }

          setError(msg);
          setLoading(false);
          onErrorRef.current?.(new Error(msg));
        };

        viz.addEventListener('error', handleVizError);
        viz.addEventListener('vizloaderror', handleVizError);

        // Extended timeout - only show error if view never loaded
        const extendedTimeout = setTimeout(() => {
          if (mounted && !viewLoaded) {
            const certErrorMsg = 'View failed to load after extended timeout. ' +
              'If you see "ERR_CERT_COMMON_NAME_INVALID" in the browser console, this indicates an SSL certificate issue. ' +
              'Solutions: 1) Configure your Tableau server with a valid SSL certificate matching the hostname, ' +
              '2) Use a reverse proxy (nginx/Apache) with a valid certificate, or ' +
              '3) Access the application over HTTP if security allows.';
            setError(certErrorMsg);
            setLoading(false);
            onErrorRef.current?.(new Error(certErrorMsg));
          }
        }, 15000);

        // Normal timeout - just hide loading spinner (view may still be loading)
        const normalTimeout = setTimeout(() => {
          if (mounted && !viewLoaded) {
            setLoading(false);
          }
        }, 5000);

        return () => {
          viz.removeEventListener('firstinteractive', onFirstInteractive);
          viz.removeEventListener('tabswitched', onTabSwitched);
          if (onUserActionRef.current) {
            eventTypes.forEach((t) => viz.removeEventListener(t, handleUserAction));
          }
          viz.removeEventListener('error', handleVizError);
          viz.removeEventListener('vizloaderror', handleVizError);
          clearTimeout(extendedTimeout);
          clearTimeout(normalTimeout);
        };

      } catch (err) {
        if (!mounted) return;
        const errorMessage = err instanceof Error ? err.message : 'Failed to embed view';
        setError(errorMessage);
        setLoading(false);
        onErrorRef.current?.(err instanceof Error ? err : new Error(errorMessage));
      }
    }

    const cleanup = embedView();

    return () => {
      if (typeof cleanup === 'function') cleanup();
      mounted = false;
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
      vizRef.current = null;
    };
  }, [embedInfo, hideTabs, hideToolbar, device, iframeAuthRetry]);

  return (
    <div className={`relative w-full h-full ${className}`}>
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50 dark:bg-gray-900 z-10">
          <div className="text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">Loading view...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-4 z-10 bg-gray-50 dark:bg-gray-900">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-900/20 max-w-md text-center">
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {viewName || viewId}
            </p>
            <p className="mt-1 text-xs font-medium text-amber-800 dark:text-amber-200">
              Unable to load — still in context
            </p>
            <p className="mt-2 text-xs text-gray-600 dark:text-gray-400">{error}</p>
          </div>
        </div>
      )}

      <div
        ref={containerRef}
        className={`w-full h-full ${loading || error ? 'hidden' : ''}`}
        style={{ height: '100%', minHeight: 0 }}
      />
    </div>
  );
}
