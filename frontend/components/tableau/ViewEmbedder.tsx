'use client';

import { useEffect, useRef, useState } from 'react';
import { getViewEmbedUrl, sanitizeViewId } from '@/lib/tableau';
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
  filters?: Record<string, string>;
  hideTabs?: boolean;
  hideToolbar?: boolean;
  device?: 'desktop' | 'phone' | 'tablet';
  onError?: (error: Error) => void;
  className?: string;
}

/**
 * ViewEmbedder component for embedding Tableau views using Embedding API v3
 * Uses the tableau-viz web component for embedding
 */
export function ViewEmbedder({
  viewId,
  filters,
  hideTabs = false,
  hideToolbar = false,
  device = 'desktop',
  onError,
  className = '',
}: ViewEmbedderProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [embedInfo, setEmbedInfo] = useState<TableauEmbedUrl | null>(null);
  const vizRef = useRef<HTMLElement | null>(null);
  const [containerHeight, setContainerHeight] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadEmbedUrl() {
      try {
        setLoading(true);
        setError(null);

        const embedData = await getViewEmbedUrl(viewId, filters);
        if (!mounted) return;

        // Check for mixed content issue: HTTPS page trying to load HTTP resource
        if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
          const embedUrl = new URL(embedData.url);
          if (embedUrl.protocol === 'http:') {
            const errorMsg = 'Mixed Content Error: This page is served over HTTPS, but the Tableau server is configured with HTTP. Please configure your Tableau server to use HTTPS, or update the server URL in the Tableau Connected App configuration to use HTTPS.';
            setError(errorMsg);
            setLoading(false);
            onError?.(new Error(errorMsg));
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
        
        // Check if this is a PAT authentication error
        const errorMessage = err instanceof Error ? err.message : 'Failed to load embed URL';
        const isPATError = errorMessage.includes('Personal Access Token') || 
                          errorMessage.includes('PAT') ||
                          (err?.response?.status === 400 && errorMessage.includes('embedding'));
        
        if (isPATError) {
          const patErrorMsg = 'View embedding is not supported with PAT. Connect with Connected App to embed views.';
          const fallbackMsg = 'View is in context. Data will be fetched via server when using Summary.';
          setError(`${patErrorMsg} ${fallbackMsg}`);
          setLoading(false);
          onError?.(new Error(patErrorMsg));
          return;
        }
        
        setError(errorMessage);
        setLoading(false);
        onError?.(err instanceof Error ? err : new Error(errorMessage));
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

        // Clear container
        if (containerRef.current) {
          containerRef.current.innerHTML = '';
        }

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

        viz.addEventListener('firstinteractive', markLoaded);
        viz.addEventListener('tabswitched', markLoaded);

        // Listen for errors from the tableau-viz component
        const handleVizError = (event: any) => {
          if (!mounted || viewLoaded) return;
          const errorDetail = event.detail || {};
          const errorMessage = errorDetail.message || errorDetail.error || 'Unknown error';
          
          if (errorMessage.includes('ERR_CERT') || 
              errorMessage.includes('certificate') || 
              errorMessage.includes('SSL') ||
              errorMessage.includes('TLS') ||
              errorMessage.includes('Common Name')) {
            const certErrorMsg = 'SSL Certificate Error: The Tableau server\'s SSL certificate is invalid or doesn\'t match the hostname. ' +
              'This is a browser security restriction. Solutions: ' +
              '1) Configure your Tableau server with a valid SSL certificate, ' +
              '2) Use a reverse proxy (nginx/Apache) with a valid certificate, or ' +
              '3) Access the application over HTTP if security allows.';
            setError(certErrorMsg);
            setLoading(false);
            onError?.(new Error(certErrorMsg));
            return;
          }
          
          setError(errorMessage);
          setLoading(false);
          onError?.(new Error(errorMessage));
        };

        viz.addEventListener('error', handleVizError);

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
            onError?.(new Error(certErrorMsg));
          }
        }, 15000);

        // Normal timeout - just hide loading spinner (view may still be loading)
        const normalTimeout = setTimeout(() => {
          if (mounted && !viewLoaded) {
            setLoading(false);
          }
        }, 5000);

        return () => {
          viz.removeEventListener('firstinteractive', markLoaded);
          viz.removeEventListener('tabswitched', markLoaded);
          viz.removeEventListener('error', handleVizError);
          clearTimeout(extendedTimeout);
          clearTimeout(normalTimeout);
        };

      } catch (err) {
        if (!mounted) return;
        const errorMessage = err instanceof Error ? err.message : 'Failed to embed view';
        setError(errorMessage);
        setLoading(false);
        onError?.(err instanceof Error ? err : new Error(errorMessage));
      }
    }

    embedView();

    return () => {
      mounted = false;
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
      vizRef.current = null;
    };
  }, [embedInfo, hideTabs, hideToolbar, device, onError]);

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
        <div className="absolute inset-0 flex items-center justify-center p-4 z-10">
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20 max-w-md">
            <p className="text-sm font-medium text-red-800 dark:text-red-200">
              Error loading view
            </p>
            <p className="mt-1 text-sm text-red-600 dark:text-red-300">{error}</p>
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
