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

  useEffect(() => {
    let mounted = true;

    async function loadEmbedUrl() {
      try {
        setLoading(true);
        setError(null);

        const embedData = await getViewEmbedUrl(viewId, filters);
        if (!mounted) return;

        setEmbedInfo(embedData);
      } catch (err) {
        if (!mounted) return;
        const errorMessage = err instanceof Error ? err.message : 'Failed to load embed URL';
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
        viz.setAttribute('height', '600px');

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

        // Set loading to false after a timeout as fallback
        setTimeout(() => {
          if (mounted) {
            setLoading(false);
          }
        }, 5000);

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
    <div className={`relative w-full ${className}`}>
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50 dark:bg-gray-900 z-10">
          <div className="text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">Loading view...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
          <p className="text-sm font-medium text-red-800 dark:text-red-200">
            Error loading view
          </p>
          <p className="mt-1 text-sm text-red-600 dark:text-red-300">{error}</p>
        </div>
      )}

      <div
        ref={containerRef}
        className={`w-full ${loading || error ? 'hidden' : ''}`}
        style={{ minHeight: '400px' }}
      />
    </div>
  );
}
