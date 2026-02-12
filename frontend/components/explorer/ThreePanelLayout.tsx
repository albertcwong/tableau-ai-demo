'use client';

import { useState, useEffect, useRef } from 'react';
import { tableauExplorerApi, authApi } from '@/lib/api';
import { useAuth } from '@/components/auth/AuthContext';
import { DatasourceDetail } from './DatasourceDetail';
import { ViewDetail } from './ViewDetail';
import { MultiViewPanel } from './MultiViewPanel';
import { TableauConnectionError } from './TableauConnectionError';
import { TableauConnectionStatus } from './TableauConnectionStatus';
import type {
  TableauDatasource,
  TableauWorkbook,
  TableauView,
} from '@/types';
import type { TableauConfigOption } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { GripVertical, ChevronDown, ChevronRight, Server, Hash, Calendar, Type, CheckSquare, TextInitial, Sparkles, RefreshCw, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { DatasourceSchema, ColumnSchema } from '@/types';
import { WorkbookIcon, DatasourceIcon, ViewIcon } from '@/components/icons';
import { captureEmbeddedStateForViews } from '@/lib/tableauEmbeddedState';
import type { EmbeddedViewState } from '@/lib/tableauEmbeddedState';

type SelectedObject =
  | { type: 'datasource'; data: TableauDatasource }
  | { type: 'workbook'; data: TableauWorkbook; views?: TableauView[] }
  | { type: 'view'; data: TableauView }
  | null;

interface ThreePanelLayoutProps {
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void;
  contextObjects?: Array<{ object_id: string; object_type: 'datasource' | 'view' }>;
  onLoadQueryRef?: React.MutableRefObject<((datasourceId: string, query: Record<string, any>) => void) | null>;
  onCaptureEmbeddedStateRef?: React.MutableRefObject<((viewIds: string[]) => Promise<Record<string, EmbeddedViewState>>) | null>;
  onDatasourceSelect?: (datasource: TableauDatasource | null) => void;
  activeThreadId?: number | null;
  onRenderedStateChange?: (state: {
    selectedObject: SelectedObject | null;
    multiViews: Array<TableauView | null>;
  }) => void;
}

const MIN_LEFT_PANEL_WIDTH = 250;
const MAX_LEFT_PANEL_WIDTH = 600;
const DEFAULT_LEFT_PANEL_WIDTH = 320;

export function ThreePanelLayout({ onAddToContext, contextObjects = [], onLoadQueryRef, onCaptureEmbeddedStateRef, onDatasourceSelect, activeThreadId, onRenderedStateChange }: ThreePanelLayoutProps) {
  const { isAuthenticated } = useAuth();
  const [allDatasources, setAllDatasources] = useState<TableauDatasource[]>([]);
  const [allWorkbooks, setAllWorkbooks] = useState<TableauWorkbook[]>([]);
  const [expandedWorkbooks, setExpandedWorkbooks] = useState<Set<string>>(new Set());
  const [expandedDatasources, setExpandedDatasources] = useState<Set<string>>(new Set());
  const [datasourceSchemas, setDatasourceSchemas] = useState<Map<string, DatasourceSchema>>(new Map());
  const [loadingSchemas, setLoadingSchemas] = useState<Set<string>>(new Set());
  const [workbookViews, setWorkbookViews] = useState<Map<string, TableauView[]>>(new Map());
  const [selectedObject, setSelectedObject] = useState<SelectedObject>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectedConfig, setConnectedConfig] = useState<TableauConfigOption | undefined>();
  const [leftPanelWidth, setLeftPanelWidth] = useState(DEFAULT_LEFT_PANEL_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<HTMLDivElement>(null);
  const [gridWidth, setGridWidth] = useState(1);
  const [gridHeight, setGridHeight] = useState(1);
  const [multiViews, setMultiViews] = useState<Array<TableauView | null>>([null]);
  const [enrichedDatasourceIds, setEnrichedDatasourceIds] = useState<Set<string>>(new Set());
  
  // Pagination state
  const [datasourcePagination, setDatasourcePagination] = useState<{ pageNumber: number; totalAvailable: number } | null>(null);
  const [workbookPagination, setWorkbookPagination] = useState<{ pageNumber: number; totalAvailable: number } | null>(null);
  const [workbookViewsPagination, setWorkbookViewsPagination] = useState<Map<string, { pageNumber: number; totalAvailable: number }>>(new Map());
  
  // Search state
  const [datasourceSearchTerm, setDatasourceSearchTerm] = useState('');
  const [debouncedDatasourceSearch, setDebouncedDatasourceSearch] = useState('');
  const [workbookSearchTerm, setWorkbookSearchTerm] = useState('');
  const [debouncedWorkbookSearch, setDebouncedWorkbookSearch] = useState('');
  const [workbookViewSearchTerms, setWorkbookViewSearchTerms] = useState<Map<string, string>>(new Map());
  const [debouncedWorkbookViewSearchTerms, setDebouncedWorkbookViewSearchTerms] = useState<Map<string, string>>(new Map());
  
  // Request cancellation
  const datasourceAbortController = useRef<AbortController | null>(null);
  const workbookAbortController = useRef<AbortController | null>(null);
  const workbookViewsAbortControllers = useRef<Map<string, AbortController>>(new Map());

  // Expose capture function for AgentPanel
  useEffect(() => {
    if (!onCaptureEmbeddedStateRef) return;
    onCaptureEmbeddedStateRef.current = (viewIds: string[]) =>
      captureEmbeddedStateForViews(viewIds);
    return () => {
      onCaptureEmbeddedStateRef!.current = null;
    };
  }, [onCaptureEmbeddedStateRef]);

  // Check initial connection state - only restore if configs are available AND token is valid
  useEffect(() => {
    const checkAndRestoreConnection = async () => {
      // Skip if user is not authenticated
      if (!isAuthenticated) {
        return;
      }
      
      try {
        // First check if there are any Tableau configs available
        const configsList = await authApi.listTableauConfigs();
        
        // Only restore connection if:
        // 1. There are configs available
        // 2. There's a stored connection state
        // 3. The stored config ID exists in the available configs
        // 4. The token hasn't expired (if expiration is stored)
        const storedConnected = localStorage.getItem('tableau_connected');
        const storedConfigId = localStorage.getItem('tableau_config_id');
        const tokenExpiresAt = localStorage.getItem('tableau_token_expires_at');
        
        // Check if token has expired
        let tokenValid = true;
        if (tokenExpiresAt) {
          try {
            const expiresAt = new Date(tokenExpiresAt);
            if (expiresAt <= new Date()) {
              tokenValid = false;
            }
          } catch (e) {
            // If we can't parse the date, assume invalid
            tokenValid = false;
          }
        }
        
        if (storedConnected === 'true' && storedConfigId && configsList.length > 0 && tokenValid) {
          // Verify the stored config ID still exists
          const configExists = configsList.some((c) => c.id === Number(storedConfigId));
          if (configExists) {
            // Don't automatically restore - let TableauConnectionStatus handle it
            // This prevents automatic API calls on page load
            // setIsConnected(true);
            // setConnectedConfig(configsList.find((c) => c.id === Number(storedConfigId)));
          } else {
            // Config no longer exists, clear localStorage
            localStorage.removeItem('tableau_connected');
            localStorage.removeItem('tableau_config_id');
            localStorage.removeItem('tableau_token_expires_at');
          }
        } else {
          // Clear localStorage if conditions aren't met
          if (!tokenValid || configsList.length === 0) {
            localStorage.removeItem('tableau_connected');
            localStorage.removeItem('tableau_config_id');
            localStorage.removeItem('tableau_token_expires_at');
          }
        }
      } catch (err) {
        // If we can't check configs (e.g., user doesn't have access), don't restore connection
        console.error('Failed to check Tableau configs:', err);
        // Clear localStorage to prevent stale connection state
        localStorage.removeItem('tableau_connected');
        localStorage.removeItem('tableau_config_id');
        localStorage.removeItem('tableau_token_expires_at');
      }
    };
    
    checkAndRestoreConnection();
  }, [isAuthenticated]);

  // Load datasources and workbooks when connected
  // Only load when explicitly connected (not on initial mount)
  useEffect(() => {
    // Only load if connected AND we have a connected config
    // This prevents loading on initial mount when isConnected might be false
    if (isConnected && connectedConfig) {
      loadDatasourcesAndWorkbooks(1, false);
    } else if (!isConnected) {
      // Clear data when disconnected
      setAllDatasources([]);
      setAllWorkbooks([]);
      setExpandedWorkbooks(new Set());
      setExpandedDatasources(new Set());
      setDatasourceSchemas(new Map());
      setLoadingSchemas(new Set());
      setWorkbookViews(new Map());
      setSelectedObject(null);
      setError(null);
      setLoadingData(false);
      setDatasourcePagination(null);
      setWorkbookPagination(null);
      setWorkbookViewsPagination(new Map());
      setDatasourceSearchTerm('');
      setDebouncedDatasourceSearch('');
      setWorkbookSearchTerm('');
      setDebouncedWorkbookSearch('');
      setWorkbookViewSearchTerms(new Map());
      setDebouncedWorkbookViewSearchTerms(new Map());
    }
  }, [isConnected, connectedConfig]);

  // Debounce search terms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedDatasourceSearch(datasourceSearchTerm);
    }, 400);
    return () => clearTimeout(timer);
  }, [datasourceSearchTerm]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedWorkbookSearch(workbookSearchTerm);
    }, 400);
    return () => clearTimeout(timer);
  }, [workbookSearchTerm]);

  useEffect(() => {
    const timers: NodeJS.Timeout[] = [];
    workbookViewSearchTerms.forEach((term, workbookId) => {
      const timer = setTimeout(() => {
        setDebouncedWorkbookViewSearchTerms((prev) => {
          const next = new Map(prev);
          if (term) {
            next.set(workbookId, term);
          } else {
            next.delete(workbookId);
          }
          return next;
        });
      }, 400);
      timers.push(timer);
    });
    return () => timers.forEach(clearTimeout);
  }, [workbookViewSearchTerms]);

  const loadDatasources = async (pageNumber = 1, append = false) => {
    setLoadingData(true);
    setError(null);

    try {
      // Cancel previous request if any
      if (datasourceAbortController.current) {
        datasourceAbortController.current.abort();
      }

      const newAbortController = new AbortController();
      datasourceAbortController.current = newAbortController;

      // Only search if term length >= 2
      const search = debouncedDatasourceSearch.length >= 2 ? debouncedDatasourceSearch : undefined;

      const result = await tableauExplorerApi.listDatasources(6, pageNumber, search);

      // Check if request was aborted
      if (newAbortController.signal.aborted) {
        return;
      }

      if (append) {
        setAllDatasources((prev) => [...prev, ...result.datasources]);
      } else {
        setAllDatasources(result.datasources);
      }

      setDatasourcePagination({
        pageNumber: result.pagination.page_number,
        totalAvailable: result.pagination.total_available,
      });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return; // Ignore aborted requests
      }
      console.error('Failed to load datasources:', err);
      setError(err instanceof Error ? err.message : 'Failed to load datasources');
    } finally {
      setLoadingData(false);
    }
  };

  const loadWorkbooks = async (pageNumber = 1, append = false) => {
    setLoadingData(true);
    setError(null);

    try {
      // Cancel previous request if any
      if (workbookAbortController.current) {
        workbookAbortController.current.abort();
      }

      const newAbortController = new AbortController();
      workbookAbortController.current = newAbortController;

      // Only search if term length >= 2
      const search = debouncedWorkbookSearch.length >= 2 ? debouncedWorkbookSearch : undefined;

      const result = await tableauExplorerApi.listWorkbooks(6, pageNumber, search);

      // Check if request was aborted
      if (newAbortController.signal.aborted) {
        return;
      }

      if (append) {
        setAllWorkbooks((prev) => [...prev, ...result.workbooks]);
      } else {
        setAllWorkbooks(result.workbooks);
      }

      setWorkbookPagination({
        pageNumber: result.pagination.page_number,
        totalAvailable: result.pagination.total_available,
      });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return; // Ignore aborted requests
      }
      console.error('Failed to load workbooks:', err);
      setError(err instanceof Error ? err.message : 'Failed to load workbooks');
    } finally {
      setLoadingData(false);
    }
  };

  const loadDatasourcesAndWorkbooks = async () => {
    await Promise.all([loadDatasources(1, false), loadWorkbooks(1, false)]);
  };

  // Reload when search terms change (debounced)
  useEffect(() => {
    if (isConnected && connectedConfig) {
      loadDatasources(1, false);
    }
  }, [debouncedDatasourceSearch, isConnected, connectedConfig]);

  useEffect(() => {
    if (isConnected && connectedConfig) {
      loadWorkbooks(1, false);
    }
  }, [debouncedWorkbookSearch, isConnected, connectedConfig]);

  const loadWorkbookViews = async (workbookId: string, pageNumber = 1, append = false) => {
    try {
      // Cancel previous request if any
      const prevController = workbookViewsAbortControllers.current.get(workbookId);
      if (prevController) {
        prevController.abort();
      }

      const newAbortController = new AbortController();
      workbookViewsAbortControllers.current.set(workbookId, newAbortController);

      const searchTerm = debouncedWorkbookViewSearchTerms.get(workbookId);
      const search = searchTerm && searchTerm.length >= 2 ? searchTerm : undefined;

      const result = await tableauExplorerApi.listWorkbookViews(workbookId, 50, pageNumber, search);

      // Check if request was aborted
      if (newAbortController.signal.aborted) {
        return;
      }

      if (append) {
        setWorkbookViews((prev) => {
          const existing = prev.get(workbookId) || [];
          return new Map(prev).set(workbookId, [...existing, ...result.views]);
        });
      } else {
        setWorkbookViews((prev) => new Map(prev).set(workbookId, result.views));
      }

      setWorkbookViewsPagination((prev) =>
        new Map(prev).set(workbookId, {
          pageNumber: result.pagination.page_number,
          totalAvailable: result.pagination.total_available,
        })
      );
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return; // Ignore aborted requests
      }
      console.error(`Failed to load views for workbook ${workbookId}:`, err);
    }
  };

  const handleToggleWorkbook = async (workbook: TableauWorkbook) => {
    const isExpanded = expandedWorkbooks.has(workbook.id);
    const newExpanded = new Set(expandedWorkbooks);

    if (isExpanded) {
      newExpanded.delete(workbook.id);
    } else {
      newExpanded.add(workbook.id);
      // Load views if not already loaded
      if (!workbookViews.has(workbook.id)) {
        await loadWorkbookViews(workbook.id, 1, false);
      }
    }

    setExpandedWorkbooks(newExpanded);
  };

  // Reload workbook views when search term changes (debounced)
  useEffect(() => {
    expandedWorkbooks.forEach((workbookId) => {
      const searchTerm = debouncedWorkbookViewSearchTerms.get(workbookId);
      // Only reload if views are already loaded (search term changed)
      if (workbookViews.has(workbookId)) {
        loadWorkbookViews(workbookId, 1, false);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedWorkbookViewSearchTerms, expandedWorkbooks]);

  // Handle resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      
      const newWidth = e.clientX;
      const clampedWidth = Math.max(MIN_LEFT_PANEL_WIDTH, Math.min(MAX_LEFT_PANEL_WIDTH, newWidth));
      setLeftPanelWidth(clampedWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };

  const handleConnectionChange = (connected: boolean, config?: TableauConfigOption) => {
    // Only update connection state when explicitly changed via TableauConnectionStatus
    // This prevents automatic API calls on page load
    setIsConnected(connected);
    if (connected && config) {
      setConnectedConfig(config);
    } else {
      setConnectedConfig(undefined);
    }
    if (!connected) {
      setSelectedObject(null);
      setError(null);
      onDatasourceSelect?.(null);
    }
  };

  const fetchSchema = async (datasource: TableauDatasource, forceRefresh = false) => {
    if (loadingSchemas.has(datasource.id)) return;
    setLoadingSchemas((prev) => new Set([...prev, datasource.id]));
    try {
      const schema = await tableauExplorerApi.getDatasourceSchema(datasource.id, forceRefresh);
      setDatasourceSchemas((prev) => new Map(prev).set(datasource.id, schema));
    } catch (err) {
      console.error(`Failed to load schema for datasource ${datasource.id}:`, err);
    } finally {
      setLoadingSchemas((prev) => {
        const next = new Set(prev);
        next.delete(datasource.id);
        return next;
      });
    }
  };

  const handleToggleDatasource = async (datasource: TableauDatasource) => {
    const isExpanded = expandedDatasources.has(datasource.id);
    if (isExpanded) {
      const newExpanded = new Set(expandedDatasources);
      newExpanded.delete(datasource.id);
      setExpandedDatasources(newExpanded);
    } else {
      setExpandedDatasources(new Set([...expandedDatasources, datasource.id]));
      if (!datasourceSchemas.has(datasource.id) && !loadingSchemas.has(datasource.id)) {
        await fetchSchema(datasource);
      }
    }
  };

  const handleSelectDatasource = async (datasource: TableauDatasource) => {
    setSelectedObject({ type: 'datasource', data: datasource });
    onDatasourceSelect?.(datasource);
    if (!expandedDatasources.has(datasource.id)) {
      setExpandedDatasources((prev) => new Set([...prev, datasource.id]));
    }
    if (!datasourceSchemas.has(datasource.id) && !loadingSchemas.has(datasource.id)) {
      await fetchSchema(datasource);
    }
  };

  // Notify parent of rendered state changes
  useEffect(() => {
    onRenderedStateChange?.({
      selectedObject,
      multiViews,
    });
  }, [selectedObject, multiViews, onRenderedStateChange]);

  // Expose function to programmatically select datasource and load query
  useEffect(() => {
    if (onLoadQueryRef) {
      onLoadQueryRef.current = async (datasourceId: string, query: Record<string, any>) => {
        console.log('ThreePanelLayout loadQueryRef called:', { datasourceId, query, allDatasources: allDatasources.length, isConnected });
        // Store query in localStorage first (before selecting datasource)
        // Ensure query is properly stringified - JSON.stringify automatically escapes control characters
        try {
          const queryString = JSON.stringify(query, null, 2);
          localStorage.setItem(`vizql_query_${datasourceId}`, queryString);
        } catch (err) {
          console.error('Failed to stringify query:', err);
          // Fallback: try without formatting
          localStorage.setItem(`vizql_query_${datasourceId}`, JSON.stringify(query));
        }
        console.log('Stored query in localStorage with key:', `vizql_query_${datasourceId}`);
        
        // Find datasource in allDatasources
        let datasource = allDatasources.find(ds => ds.id === datasourceId);
        console.log('Found datasource:', datasource ? datasource.name : 'not found');
        
        // If datasource not found and we're connected, try to load datasources first
        if (!datasource && isConnected) {
          console.log('Datasource not found, loading datasources...');
          try {
            setLoadingData(true);
            const [datasourcesResult, workbooksResult] = await Promise.all([
              tableauExplorerApi.listDatasources(6),
              tableauExplorerApi.listWorkbooks(6),
            ]);
            setAllDatasources(datasourcesResult.datasources);
            setAllWorkbooks(workbooksResult.workbooks);
            setDatasourcePagination({
              pageNumber: datasourcesResult.pagination.page_number,
              totalAvailable: datasourcesResult.pagination.total_available,
            });
            setWorkbookPagination({
              pageNumber: workbooksResult.pagination.page_number,
              totalAvailable: workbooksResult.pagination.total_available,
            });
            console.log('Loaded datasources:', datasources.length);
            // Try again after loading
            datasource = datasourcesResult.datasources.find(ds => ds.id === datasourceId);
            console.log('After loading, found datasource:', datasource ? datasource.name : 'still not found');
          } catch (err) {
            console.error('Failed to load datasources:', err);
            setError(err instanceof Error ? err.message : 'Failed to load datasources');
          } finally {
            setLoadingData(false);
          }
        }
        
        if (datasource) {
          console.log('Selecting datasource:', datasource.name);
          // Select the datasource (this will trigger DatasourceDetail to load)
          handleSelectDatasource(datasource);
          // Dispatch event immediately after selecting (in case component is already mounted)
          // Use setTimeout to ensure state update completes first
          setTimeout(() => {
            window.dispatchEvent(new CustomEvent('clearQueryResults', { detail: { datasourceId } }));
            window.dispatchEvent(new CustomEvent('loadVizQLQuery', { 
              detail: { datasourceId, query } 
            }));
          }, 100);
        } else {
          console.warn(`Datasource ${datasourceId} not found in loaded datasources. Query stored in localStorage.`);
          // Still dispatch event in case datasource detail is already open
          window.dispatchEvent(new CustomEvent('clearQueryResults', { detail: { datasourceId } }));
          window.dispatchEvent(new CustomEvent('loadVizQLQuery', { 
            detail: { datasourceId, query } 
          }));
        }
      };
    }
    return () => {
      if (onLoadQueryRef) {
        onLoadQueryRef.current = null;
      }
    };
  }, [allDatasources, isConnected, onLoadQueryRef]);

  const getDataTypeIcon = (dataType?: string) => {
    if (!dataType) return <TextInitial className="h-3 w-3" />;
    const type = dataType.toLowerCase();
    if (type.includes('int') || type.includes('number') || type.includes('numeric')) {
      return <Hash className="h-3 w-3" />;
    }
    if (type.includes('float') || type.includes('double') || type.includes('decimal') || type.includes('real')) {
      return <Hash className="h-3 w-3" />;
    }
    if (type.includes('date') || type.includes('time')) {
      return <Calendar className="h-3 w-3" />;
    }
    if (type.includes('bool')) {
      return <CheckSquare className="h-3 w-3" />;
    }
    return <TextInitial className="h-3 w-3" />;
  };

  const handleSelectWorkbook = async (workbook: TableauWorkbook) => {
    setLoadingData(true);
    setError(null);
    try {
      const result = await tableauExplorerApi.listWorkbookViews(workbook.id);
      setSelectedObject({ type: 'workbook', data: workbook, views: result.views });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workbook views');
    } finally {
      setLoadingData(false);
    }
  };

  const handleSelectView = (view: TableauView) => {
    setSelectedObject({ type: 'view', data: view });
    // When a view is selected, add it to the first empty slot or replace the first slot
    const firstEmptyIndex = multiViews.findIndex(v => v === null);
    if (firstEmptyIndex !== -1) {
      const newViews = [...multiViews];
      newViews[firstEmptyIndex] = view;
      setMultiViews(newViews);
    } else if (multiViews.length > 0) {
      // Replace first slot if all slots are filled
      const newViews = [...multiViews];
      newViews[0] = view;
      setMultiViews(newViews);
    } else {
      setMultiViews([view]);
    }
  };

  // Only show error if connection was attempted (isConnected is true)
  // This prevents showing errors for users who haven't connected to Tableau
  if (error && isConnected && !selectedObject && allDatasources.length === 0 && allWorkbooks.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <TableauConnectionError 
          error={error} 
          onRetry={loadDatasourcesAndWorkbooks}
          onCancel={() => setError(null)}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Left Panel - Resizable */}
      <div 
        className="border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col relative"
        style={{ width: `${leftPanelWidth}px` }}
      >
        {/* Resize handle */}
        <div
          ref={resizeRef}
          onMouseDown={handleResizeStart}
          className="absolute right-0 top-0 h-full w-2 cursor-col-resize hover:bg-blue-200/50 dark:hover:bg-blue-700/50 active:bg-blue-300 dark:active:bg-blue-600 transition-colors z-10 group"
          style={{ touchAction: 'none' }}
          title="Drag to resize"
        >
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            <GripVertical className="h-5 w-5 text-gray-600 dark:text-gray-300" />
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-4 space-y-6">
            {/* Tableau Servers Section */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Server className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Tableau Servers</h3>
              </div>
              <TableauConnectionStatus
                onConnectionChange={handleConnectionChange}
                onSiteChange={() => loadDatasourcesAndWorkbooks()}
              />
            </div>

            {/* Datasources Section */}
            {isConnected && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <DatasourceIcon className="text-gray-500 dark:text-gray-400" width={18} height={18} />
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Datasources</h3>
                  {datasourcePagination && (
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      ({allDatasources.length}{datasourcePagination.totalAvailable > allDatasources.length ? ` / ${datasourcePagination.totalAvailable}` : ''})
                    </span>
                  )}
                </div>
                <div className="mb-2 relative">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                  <Input
                    type="text"
                    placeholder="Search datasources..."
                    value={datasourceSearchTerm}
                    onChange={(e) => setDatasourceSearchTerm(e.target.value)}
                    className="h-7 pl-7 pr-7 text-xs"
                  />
                  {datasourceSearchTerm && (
                    <button
                      onClick={() => setDatasourceSearchTerm('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                {loadingData ? (
                  <div className="space-y-2">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                ) : allDatasources.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">No datasources found</p>
                ) : (
                  <div className="space-y-1 max-h-[250px] overflow-y-auto">
                    {allDatasources.map((ds) => {
                      const isInContext = contextObjects.some(
                        (ctx) => ctx.object_id === ds.id && ctx.object_type === 'datasource'
                      );
                      const isExpanded = expandedDatasources.has(ds.id);
                      const schema = datasourceSchemas.get(ds.id);
                      const isLoadingSchema = loadingSchemas.has(ds.id);
                      const measures = schema?.columns.filter(col => col.is_measure) || [];
                      const dimensions = schema?.columns.filter(col => col.is_dimension) || [];
                      
                      return (
                        <Card
                          key={ds.id}
                          className={cn(
                            "hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors",
                            selectedObject?.type === 'datasource' && selectedObject.data.id === ds.id && "bg-blue-50 dark:bg-blue-900/20"
                          )}
                        >
                          <div
                            className="p-2 cursor-pointer"
                            onClick={() => handleSelectDatasource(ds)}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1 flex-1 min-w-0">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleToggleDatasource(ds);
                                  }}
                                  className="p-0.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                  title={isExpanded ? 'Collapse' : 'Expand'}
                                >
                                  {isExpanded ? (
                                    <ChevronDown className="h-3 w-3 text-gray-500" />
                                  ) : (
                                    <ChevronRight className="h-3 w-3 text-gray-500" />
                                  )}
                                </button>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <div className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">{ds.name}</div>
                                    {enrichedDatasourceIds.has(ds.id) && (
                                      <span className="px-1.5 py-0.5 text-[10px] font-medium bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded flex items-center gap-1" title="Schema enriched for AI">
                                        <Sparkles className="h-2.5 w-2.5" />
                                        Enriched
                                      </span>
                                    )}
                                  </div>
                                  {ds.project_name && (
                                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{ds.project_name}</div>
                                  )}
                                </div>
                              </div>
                              {onAddToContext && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (!isInContext) {
                                      onAddToContext(ds.id, 'datasource', ds.name);
                                    }
                                  }}
                                  disabled={isInContext}
                                  className="ml-2 h-6 px-2 text-xs"
                                  title={isInContext ? 'Already in context' : 'Add to Chat'}
                                >
                                  {isInContext ? '✓' : '+'}
                                </Button>
                              )}
                            </div>
                          </div>
                          
                          {isExpanded && (
                            <div className="px-2 pb-2 border-t border-gray-200 dark:border-gray-700 mt-1 pt-2 space-y-2">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-[10px] text-gray-500 dark:text-gray-400">Schema</span>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-5 px-1.5 text-xs"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    fetchSchema(ds, true);
                                  }}
                                  disabled={isLoadingSchema}
                                  title="Refresh schema (bypass cache, logs GraphQL/read-metadata)"
                                >
                                  <RefreshCw className={cn('h-3 w-3', isLoadingSchema && 'animate-spin')} />
                                </Button>
                              </div>
                              {isLoadingSchema ? (
                                <div className="space-y-2">
                                  <Skeleton className="h-4 w-full" />
                                  <Skeleton className="h-4 w-3/4" />
                                </div>
                              ) : schema ? (
                                <div className="space-y-3 text-xs">
                                  {dimensions.length > 0 && (
                                    <div>
                                      <div className="font-semibold text-gray-700 dark:text-gray-300 mb-1 flex items-center gap-1">
                                        <Type className="h-3 w-3" />
                                        Dimensions ({dimensions.length})
                                      </div>
                                      <div className="space-y-0.5 pl-4">
                                        {dimensions.map((col, idx) => {
                                          const dataType = col.data_type || col.remote_type || 'Unknown';
                                          return (
                                            <div 
                                              key={idx} 
                                              className="flex items-center gap-2 text-gray-600 dark:text-gray-400"
                                              title={`${col.name} (${dataType})`}
                                            >
                                              {getDataTypeIcon(dataType)}
                                              <span className="truncate">{col.name}</span>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  )}
                                  {measures.length > 0 && (
                                    <div>
                                      <div className="font-semibold text-gray-700 dark:text-gray-300 mb-1 flex items-center gap-1">
                                        <Hash className="h-3 w-3" />
                                        Measures ({measures.length})
                                      </div>
                                      <div className="space-y-0.5 pl-4">
                                        {measures.map((col, idx) => {
                                          const dataType = col.data_type || col.remote_type || 'Unknown';
                                          return (
                                            <div 
                                              key={idx} 
                                              className="flex items-center gap-2 text-gray-600 dark:text-gray-400"
                                              title={`${col.name} (${dataType})`}
                                            >
                                              {getDataTypeIcon(dataType)}
                                              <span className="truncate">{col.name}</span>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  )}
                                  {measures.length === 0 && dimensions.length === 0 && (
                                    <div className="text-gray-500 dark:text-gray-400 text-xs">No columns found</div>
                                  )}
                                </div>
                              ) : (
                                <div className="text-xs text-gray-500 dark:text-gray-400">Failed to load schema</div>
                              )}
                            </div>
                          )}
                        </Card>
                      );
                    })}
                    {datasourcePagination && datasourcePagination.totalAvailable > allDatasources.length && (
                      <div className="mt-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full h-7 text-xs"
                          onClick={() => loadDatasources((datasourcePagination.pageNumber || 0) + 1, true)}
                          disabled={loadingData}
                        >
                          Load More ({datasourcePagination.totalAvailable - allDatasources.length} remaining)
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Workbooks Section */}
            {isConnected && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <WorkbookIcon className="text-gray-500 dark:text-gray-400" width={18} height={18} />
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Workbooks</h3>
                  {workbookPagination && (
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      ({allWorkbooks.length}{workbookPagination.totalAvailable > allWorkbooks.length ? ` / ${workbookPagination.totalAvailable}` : ''})
                    </span>
                  )}
                </div>
                <div className="mb-2 relative">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                  <Input
                    type="text"
                    placeholder="Search workbooks..."
                    value={workbookSearchTerm}
                    onChange={(e) => setWorkbookSearchTerm(e.target.value)}
                    className="h-7 pl-7 pr-7 text-xs"
                  />
                  {workbookSearchTerm && (
                    <button
                      onClick={() => setWorkbookSearchTerm('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                {loadingData ? (
                  <div className="space-y-2">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                ) : allWorkbooks.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">No workbooks found</p>
                ) : (
                  <div className="space-y-1 max-h-[250px] overflow-y-auto">
                    {allWorkbooks.map((wb) => {
                      const isExpanded = expandedWorkbooks.has(wb.id);
                      const views = workbookViews.get(wb.id) || [];
                      return (
                        <Card
                          key={wb.id}
                          className={cn(
                            "hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors",
                            selectedObject?.type === 'workbook' && selectedObject.data.id === wb.id && "bg-blue-50 dark:bg-blue-900/20"
                          )}
                        >
                          <div
                            className="p-2 cursor-pointer"
                            onClick={() => handleSelectWorkbook(wb)}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1 flex-1 min-w-0">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleToggleWorkbook(wb);
                                  }}
                                  className="p-0.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                  title={isExpanded ? 'Collapse' : 'Expand'}
                                >
                                  {isExpanded ? (
                                    <ChevronDown className="h-3 w-3 text-gray-500" />
                                  ) : (
                                    <ChevronRight className="h-3 w-3 text-gray-500" />
                                  )}
                                </button>
                                <div className="flex-1 min-w-0">
                                  <div className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">{wb.name}</div>
                                  {wb.project_name && (
                                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{wb.project_name}</div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                          
                          {isExpanded && (
                            <div className="px-2 pb-2 border-t border-gray-200 dark:border-gray-700 mt-1 pt-2">
                              <div className="mb-2 relative">
                                <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400" />
                                <Input
                                  type="text"
                                  placeholder="Search views..."
                                  value={workbookViewSearchTerms.get(wb.id) || ''}
                                  onChange={(e) => {
                                    const newTerms = new Map(workbookViewSearchTerms);
                                    if (e.target.value) {
                                      newTerms.set(wb.id, e.target.value);
                                    } else {
                                      newTerms.delete(wb.id);
                                    }
                                    setWorkbookViewSearchTerms(newTerms);
                                  }}
                                  className="h-6 pl-6 pr-6 text-xs"
                                />
                                {workbookViewSearchTerms.get(wb.id) && (
                                  <button
                                    onClick={() => {
                                      const newTerms = new Map(workbookViewSearchTerms);
                                      newTerms.delete(wb.id);
                                      setWorkbookViewSearchTerms(newTerms);
                                    }}
                                    className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                                  >
                                    <X className="h-3 w-3" />
                                  </button>
                                )}
                              </div>
                              {views.length === 0 ? (
                                <div className="text-xs text-gray-500 dark:text-gray-400">No views found</div>
                              ) : (
                                <div className="space-y-0.5">
                                  {views.map((view) => {
                                    const viewInContext = contextObjects.some(
                                      (ctx) => ctx.object_id === view.id && ctx.object_type === 'view'
                                    );
                                    return (
                                      <div
                                        key={view.id}
                                        className={cn(
                                          "p-1.5 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-grab active:cursor-grabbing transition-colors rounded",
                                          selectedObject?.type === 'view' && selectedObject.data.id === view.id && "bg-blue-50 dark:bg-blue-900/20"
                                        )}
                                        onClick={() => handleSelectView(view)}
                                        draggable
                                        onDragStart={(e) => {
                                          e.dataTransfer.setData('application/json', JSON.stringify(view));
                                          e.dataTransfer.effectAllowed = 'move';
                                          e.currentTarget.style.opacity = '0.5';
                                        }}
                                        onDragEnd={(e) => {
                                          e.currentTarget.style.opacity = '1';
                                        }}
                                      >
                                        <div className="flex items-center justify-between">
                                          <div className="flex items-center gap-2 flex-1 min-w-0">
                                            <div className="shrink-0 flex items-center">
                                              <ViewIcon className="text-gray-500 dark:text-gray-400" width={16} height={16} />
                                            </div>
                                            <div className="font-medium text-xs text-gray-900 dark:text-gray-100 truncate">{view.name}</div>
                                          </div>
                                          {onAddToContext && (
                                            <Button
                                              variant="ghost"
                                              size="sm"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                if (!viewInContext) {
                                                  onAddToContext(view.id, 'view', view.name);
                                                }
                                              }}
                                              disabled={viewInContext}
                                              className="ml-2 h-5 px-1.5 text-xs"
                                              title={viewInContext ? 'Already in context' : 'Add to Chat'}
                                            >
                                              {viewInContext ? '✓' : '+'}
                                            </Button>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                              {(() => {
                                const pagination = workbookViewsPagination.get(wb.id);
                                return pagination && pagination.totalAvailable > views.length ? (
                                  <div className="mt-2">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="w-full h-6 text-xs"
                                      onClick={() => loadWorkbookViews(wb.id, (pagination.pageNumber || 0) + 1, true)}
                                      disabled={loadingData}
                                    >
                                      Load More ({pagination.totalAvailable - views.length} remaining)
                                    </Button>
                                  </div>
                                ) : null;
                              })()}
                            </div>
                          )}
                        </Card>
                      );
                    })}
                    {workbookPagination && workbookPagination.totalAvailable > allWorkbooks.length && (
                      <div className="mt-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full h-7 text-xs"
                          onClick={() => loadWorkbooks((workbookPagination.pageNumber || 0) + 1, true)}
                          disabled={loadingData}
                        >
                          Load More ({workbookPagination.totalAvailable - allWorkbooks.length} remaining)
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Main Panel - Content Display */}
      <div className="flex-1 overflow-hidden bg-gray-50 dark:bg-gray-900 flex flex-col min-w-0">
        {!isConnected ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500 dark:text-gray-400 max-w-md">
              <p className="text-lg mb-2">Not Connected</p>
              <p className="text-sm">
                Select a Tableau server configuration and click Connect to start browsing objects.
              </p>
            </div>
          </div>
        ) : selectedObject?.type === 'datasource' ? (
          <div className="flex-1 overflow-y-auto p-6">
            <DatasourceDetail
              datasourceId={selectedObject.data.id}
              datasourceName={selectedObject.data.name}
              onAddToContext={onAddToContext}
              contextObjects={contextObjects}
              onEnriched={(result) => {
                setEnrichedDatasourceIds(prev => new Set([...prev, result.datasource_id]));
              }}
            />
          </div>
        ) : (
          <MultiViewPanel
            gridWidth={gridWidth}
            gridHeight={gridHeight}
            onGridChange={(width, height) => {
              setGridWidth(width);
              setGridHeight(height);
            }}
            views={multiViews}
            onViewsChange={setMultiViews}
            onAddToContext={onAddToContext}
            contextObjects={contextObjects}
          />
        )}
      </div>
    </div>
  );
}
