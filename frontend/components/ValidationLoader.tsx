'use client';

import { useEffect } from 'react';

/**
 * ValidationLoader component
 * Makes validation schemas available globally in development for browser console testing
 */
export function ValidationLoader() {
  useEffect(() => {
    // Only load in development
    if (process.env.NODE_ENV === 'development') {
      import('@/lib/validation-test').catch((err) => {
        console.warn('Failed to load validation test utilities:', err);
      });
    }
  }, []);

  return null;
}
