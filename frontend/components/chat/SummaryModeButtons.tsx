'use client';

import { Button } from '@/components/ui/button';
import type { SummaryMode } from '@/lib/api';

interface SummaryModeButtonsProps {
  onSelect: (mode: SummaryMode) => void;
  hasViews: boolean;
  disabled?: boolean;
}

export function SummaryModeButtons({ onSelect, hasViews, disabled }: SummaryModeButtonsProps) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <Button
        size="sm"
        variant="outline"
        onClick={() => onSelect('brief')}
        disabled={disabled || !hasViews}
        title={!hasViews ? 'Add views to context first' : '2–3 sentence executive summary'}
      >
        Brief Summary
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => onSelect('full')}
        disabled={disabled || !hasViews}
        title={!hasViews ? 'Add views to context first' : 'Comprehensive analysis'}
      >
        Full Analysis
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => onSelect('custom')}
        disabled={disabled}
        title="Type your own instructions below"
      >
        Custom Instructions
      </Button>
    </div>
  );
}
