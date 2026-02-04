'use client';

import { useEffect } from 'react';

/**
 * Component to load Tableau Embedding API v3 script
 * Must be loaded as ES6 module per Tableau documentation
 */
export function TableauScriptLoader() {
  useEffect(() => {
    // Check if script is already loaded
    const existingScript = document.querySelector(
      'script[src*="tableau.embedding.3"]'
    );
    
    if (existingScript) {
      return;
    }

    // Create and append script tag
    const script = document.createElement('script');
    script.type = 'module';
    script.src = 'https://public.tableau.com/javascripts/api/tableau.embedding.3.latest.min.js';
    script.async = true;
    
    document.head.appendChild(script);

    return () => {
      // Cleanup on unmount
      const scriptToRemove = document.querySelector(
        'script[src*="tableau.embedding.3"]'
      );
      if (scriptToRemove) {
        scriptToRemove.remove();
      }
    };
  }, []);

  return null;
}
