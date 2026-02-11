'use client';

import { useState, useEffect } from 'react';
import { tableauExplorerApi, authApi } from '@/lib/api';
import { useAuth } from '@/components/auth/AuthContext';
import { BreadcrumbNav, type BreadcrumbItem } from './BreadcrumbNav';
import { ObjectList } from './ObjectList';
import { DatasourceDetail } from './DatasourceDetail';
import { ViewDetail } from './ViewDetail';
import { ProjectDetail } from './ProjectDetail';
import type {
  TableauProject,
  TableauDatasource,
  TableauWorkbook,
  TableauView,
  ProjectContents,
} from '@/types';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { TableauConnectionError } from './TableauConnectionError';

type SelectedObject =
  | { type: 'project'; data: TableauProject; contents?: ProjectContents }
  | { type: 'datasource'; data: TableauDatasource }
  | { type: 'workbook'; data: TableauWorkbook; views?: TableauView[] }
  | { type: 'view'; data: TableauView }
  | null;

interface ObjectExplorerProps {
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void;
  contextObjects?: Array<{ object_id: string; object_type: 'datasource' | 'view' }>;
}

export function ObjectExplorer({ onAddToContext, contextObjects = [] }: ObjectExplorerProps) {
  const { isAuthenticated } = useAuth();
  const [projects, setProjects] = useState<TableauProject[]>([]);
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([]);
  const [selectedObject, setSelectedObject] = useState<SelectedObject>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Check initial connection state - only restore if configs are available
  useEffect(() => {
    const checkAndRestoreConnection = async () => {
      // Skip if user is not authenticated
      if (!isAuthenticated) {
        setLoading(false);
        return;
      }
      
      try {
        // First check if there are any Tableau configs available
        const configsList = await authApi.listTableauConfigs();
        
        // Only restore connection if:
        // 1. There are configs available
        // 2. There's a stored connection state
        // 3. The stored config ID exists in the available configs
        const storedConnected = localStorage.getItem('tableau_connected');
        const storedConfigId = localStorage.getItem('tableau_config_id');
        
        if (storedConnected === 'true' && storedConfigId && configsList.length > 0) {
          // Verify the stored config ID still exists
          const configExists = configsList.some((c) => c.id === Number(storedConfigId));
          if (configExists) {
            setIsConnected(true);
          } else {
            // Config no longer exists, clear localStorage
            localStorage.removeItem('tableau_connected');
            localStorage.removeItem('tableau_config_id');
            localStorage.removeItem('tableau_token_expires_at');
            setIsConnected(false);
          }
        } else if (configsList.length === 0) {
          // No configs available, clear any stored connection state
          localStorage.removeItem('tableau_connected');
          localStorage.removeItem('tableau_config_id');
          localStorage.removeItem('tableau_token_expires_at');
          setIsConnected(false);
        } else {
          setIsConnected(false);
        }
      } catch (err) {
        // If we can't check configs (e.g., user doesn't have access), don't restore connection
        console.error('Failed to check Tableau configs:', err);
        // Clear localStorage to prevent stale connection state
        localStorage.removeItem('tableau_connected');
        localStorage.removeItem('tableau_config_id');
        localStorage.removeItem('tableau_token_expires_at');
        setIsConnected(false);
      } finally {
        setLoading(false);
      }
    };
    
    checkAndRestoreConnection();
  }, [isAuthenticated]);

  useEffect(() => {
    // Only load projects if connected
    if (isConnected) {
      loadRootProjects();
    } else {
      setError(null);
    }
  }, [isConnected]);

  const loadRootProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const rootProjects = await tableauExplorerApi.listProjects();
      setProjects(rootProjects);
      setBreadcrumbs([{ id: 'root', name: 'Root', type: 'root' }]);
      setSelectedObject(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectProject = async (project: TableauProject) => {
    setLoading(true);
    setError(null);
    try {
      const contents = await tableauExplorerApi.getProjectContents(project.id);
      setSelectedObject({ type: 'project', data: project, contents });
      setBreadcrumbs([
        ...breadcrumbs,
        { id: project.id, name: project.name, type: 'project' },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load project contents');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDatasource = (datasource: TableauDatasource) => {
    setSelectedObject({ type: 'datasource', data: datasource });
  };

  const handleSelectWorkbook = async (workbook: TableauWorkbook) => {
    setLoading(true);
    setError(null);
    try {
      const result = await tableauExplorerApi.listWorkbookViews(workbook.id);
      const views = result.views;
      setSelectedObject({ type: 'workbook', data: workbook, views });
      setBreadcrumbs([
        ...breadcrumbs,
        { id: workbook.id, name: workbook.name, type: 'workbook' },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workbook views');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectView = (view: TableauView) => {
    setSelectedObject({ type: 'view', data: view });
  };

  const handleBreadcrumbNavigate = async (item: BreadcrumbItem) => {
    if (item.type === 'root') {
      await loadRootProjects();
      return;
    }

    if (item.type === 'project') {
      const project = projects.find((p) => p.id === item.id);
      if (project) {
        await handleSelectProject(project);
      }
    } else if (item.type === 'workbook') {
      // Find workbook in current project contents or reload
      // For now, we'll need to reload from the project
      // This is a simplified approach - in a full implementation, we'd store workbook references
      const workbook: TableauWorkbook = {
        id: item.id,
        name: item.name,
        project_id: breadcrumbs.find(b => b.type === 'project')?.id,
        project_name: breadcrumbs.find(b => b.type === 'project')?.name,
      };
      await handleSelectWorkbook(workbook);
    }
  };

  if (loading && !selectedObject) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  // Only show error if connection was attempted (isConnected is true)
  // This prevents showing errors for users who haven't connected to Tableau
  if (error && isConnected && !selectedObject) {
    return (
      <TableauConnectionError 
        error={error} 
        onRetry={loadRootProjects}
        onCancel={() => setError(null)}
      />
    );
  }

  // If not connected, show nothing (or a message to connect)
  if (!isConnected && !loading) {
    return null;
  }

  return (
    <div className="space-y-4">
      <BreadcrumbNav items={breadcrumbs} onNavigate={handleBreadcrumbNavigate} />

      {selectedObject ? (
        <div className="space-y-4">
          {selectedObject.type === 'project' && selectedObject.contents && (
            <ProjectDetail
              contents={selectedObject.contents}
              onSelectProject={(id) => {
                const project = selectedObject.contents?.projects.find((p) => p.id === id);
                if (project) handleSelectProject(project);
              }}
              onSelectDatasource={(id) => {
                const datasource = selectedObject.contents?.datasources.find((d) => d.id === id);
                if (datasource) handleSelectDatasource(datasource);
              }}
              onSelectWorkbook={(id) => {
                const workbook = selectedObject.contents?.workbooks.find((w) => w.id === id);
                if (workbook) handleSelectWorkbook(workbook);
              }}
              onSelectView={(id) => {
                // Would need to load views from workbook first
              }}
              onAddToContext={onAddToContext}
              contextObjects={contextObjects}
            />
          )}
          {selectedObject.type === 'datasource' && (
            <DatasourceDetail
              datasourceId={selectedObject.data.id}
              datasourceName={selectedObject.data.name}
              onAddToContext={onAddToContext}
              contextObjects={contextObjects}
            />
          )}
          {selectedObject.type === 'view' && (
            <ViewDetail 
              viewId={selectedObject.data.id} 
              viewName={selectedObject.data.name}
              onAddToContext={onAddToContext}
              contextObjects={contextObjects}
            />
          )}
          {selectedObject.type === 'workbook' && (
            <div className="space-y-4">
              <h2 className="text-2xl font-bold">Workbook: {selectedObject.data.name}</h2>
              {selectedObject.views && selectedObject.views.length > 0 ? (
                <ObjectList
                  views={selectedObject.views}
                  onSelectView={(view) => handleSelectView(view)}
                  onAddToContext={onAddToContext}
                  contextObjects={contextObjects}
                />
              ) : (
                <Card className="p-4">
                  <p className="text-gray-600 dark:text-gray-400">
                    No views found in this workbook.
                  </p>
                </Card>
              )}
            </div>
          )}
        </div>
      ) : (
        <ObjectList
          projects={projects}
          onSelectProject={handleSelectProject}
          onSelectDatasource={handleSelectDatasource}
          onSelectWorkbook={handleSelectWorkbook}
          onSelectView={handleSelectView}
          onAddToContext={onAddToContext}
          contextObjects={contextObjects}
        />
      )}
    </div>
  );
}
