'use client';

import { useEffect, useRef, useState } from 'react';
import { getViewEmbedUrl } from '@/lib/tableau';
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

        setEmbedInfo(embedData);
      } catch (err: any) {
        if (!mounted) return;
        
        // Check if this is a PAT authentication error
        const errorMessage = err instanceof Error ? err.message : 'Failed to load embed URL';
        const isPATError = errorMessage.includes('Personal Access Token') || 
                          errorMessage.includes('PAT') ||
                          (err?.response?.status === 400 && errorMessage.includes('embedding'));
        
        if (isPATError) {
          const patErrorMsg = 'View embedding is not supported when using Personal Access Token authentication. Please connect with Connected App to embed views.';
          setError(patErrorMsg);
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
        const height = containerRef.current.clientHeight || containerHeight || 600;

        // Create new tableau-viz web component using Tableau Embedding API v3
        const viz = document.createElement('tableau-viz') as HTMLElement;
        
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

        // Wait for the web component to load
        viz.addEventListener('firstinteractive', () => {
          if (mounted) {
            setLoading(false);
          }
        });

        // Handle errors from the web component
        viz.addEventListener('tabswitched', () => {
          // View loaded successfully
          if (mounted) {
            setLoading(false);
          }
        });

        // Listen for errors from the tableau-viz component
        viz.addEventListener('error', (event: any) => {
          if (!mounted) return;
          const errorDetail = event.detail || {};
          const errorMessage = errorDetail.message || errorDetail.error || 'Unknown error';
          
          // Check for SSL certificate errors
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
        });

        // Monitor network errors via window error handler
        const handleWindowError = (event: ErrorEvent) => {
          const errorMsg = event.message || '';
          if (errorMsg.includes('ERR_CERT') || 
              errorMsg.includes('net::ERR_CERT_COMMON_NAME_INVALID') ||
              errorMsg.includes('Failed to load resource')) {
            const certErrorMsg = 'SSL Certificate Error: The Tableau server\'s SSL certificate is invalid or doesn\'t match the hostname. ' +
              'This is a browser security restriction. Solutions: ' +
              '1) Configure your Tableau server with a valid SSL certificate, ' +
              '2) Use a reverse proxy (nginx/Apache) with a valid certificate, or ' +
              '3) Access the application over HTTP if security allows.';
            if (mounted) {
              setError(certErrorMsg);
              setLoading(false);
              onError?.(new Error(certErrorMsg));
            }
          }
        };

        window.addEventListener('error', handleWindowError);

        // Set loading to false after a timeout as fallback
        setTimeout(() => {
          if (mounted) {
            setLoading(false);
          }
        }, 5000);

        // Cleanup error handler
        return () => {
          window.removeEventListener('error', handleWindowError);
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
