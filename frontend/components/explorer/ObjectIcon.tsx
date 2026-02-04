'use client';

import { Folder, Database, FileText, Layout } from 'lucide-react';

export type ObjectType = 'project' | 'datasource' | 'workbook' | 'view';

interface ObjectIconProps {
  type: ObjectType;
  className?: string;
}

export function ObjectIcon({ type, className = 'h-5 w-5' }: ObjectIconProps) {
  switch (type) {
    case 'project':
      return <Folder className={className} />;
    case 'datasource':
      return <Database className={className} />;
    case 'workbook':
      return <FileText className={className} />;
    case 'view':
      return <Layout className={className} />;
    default:
      return null;
  }
}
