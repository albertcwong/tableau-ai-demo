'use client';

import { Button } from '@/components/ui/button';
import { ChevronRight } from 'lucide-react';

export interface BreadcrumbItem {
  id: string;
  name: string;
  type: 'project' | 'workbook' | 'root';
}

interface BreadcrumbNavProps {
  items: BreadcrumbItem[];
  onNavigate: (item: BreadcrumbItem) => void;
}

export function BreadcrumbNav({ items, onNavigate }: BreadcrumbNavProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <nav className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 mb-4">
      {items.map((item, index) => (
        <div key={`${item.type}-${index}-${item.id}`} className="flex items-center gap-2">
          {index > 0 && <ChevronRight className="h-4 w-4" />}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigate(item)}
            className="h-auto p-0 font-normal text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
          >
            {item.name}
          </Button>
        </div>
      ))}
    </nav>
  );
}
