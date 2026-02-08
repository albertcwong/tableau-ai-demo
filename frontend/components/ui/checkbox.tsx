'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  onCheckedChange?: (checked: boolean) => void;
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, onCheckedChange, onChange, ...props }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (onCheckedChange) {
        onCheckedChange(e.target.checked);
      }
      if (onChange) {
        onChange(e);
      }
    };

    return (
      <input
        type="checkbox"
        ref={ref}
        className={cn(
          'h-4 w-4 rounded border-gray-300 dark:border-gray-700',
          'text-blue-600 focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400',
          'dark:bg-gray-800 dark:checked:bg-blue-600',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'cursor-pointer',
          className
        )}
        onChange={handleChange}
        {...props}
      />
    );
  }
);
Checkbox.displayName = 'Checkbox';

export { Checkbox };
