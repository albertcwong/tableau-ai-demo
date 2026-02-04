'use client';

import { ObjectList } from './ObjectList';
import type { ProjectContents } from '@/types';

interface ProjectDetailProps {
  contents: ProjectContents;
  onSelectProject?: (projectId: string) => void;
  onSelectDatasource?: (datasourceId: string) => void;
  onSelectWorkbook?: (workbookId: string) => void;
  onSelectView?: (viewId: string) => void;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view') => void;
  contextObjects?: Array<{ object_id: string; object_type: 'datasource' | 'view' }>;
}

export function ProjectDetail({
  contents,
  onSelectProject,
  onSelectDatasource,
  onSelectWorkbook,
  onSelectView,
  onAddToContext,
  contextObjects = [],
}: ProjectDetailProps) {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Project: {contents.project_id}</h2>
      <ObjectList
        projects={contents.projects}
        datasources={contents.datasources}
        workbooks={contents.workbooks}
        onSelectProject={(p) => onSelectProject?.(p.id)}
        onSelectDatasource={(d) => onSelectDatasource?.(d.id)}
        onSelectWorkbook={(w) => onSelectWorkbook?.(w.id)}
        onSelectView={(v) => onSelectView?.(v.id)}
        onAddToContext={onAddToContext}
        contextObjects={contextObjects}
      />
    </div>
  );
}
