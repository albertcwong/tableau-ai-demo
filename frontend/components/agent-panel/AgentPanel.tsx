'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { chatApi, chatContextApi, authApi } from '@/lib/api';
import { AgentSelector, AgentType } from './AgentSelector';
import { ContextManager } from './ContextManager';
import { ModelSettings } from './ModelSettings';
import { ThreadList } from './ThreadList';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { X, GripVertical, Settings } from 'lucide-react';
import type { ChatContextObject, ConversationResponse } from '@/types';

interface RenderedState {
  selectedObject: {
    type: 'datasource' | 'view' | 'workbook';
    data: { id: string; name: string; [key: string]: any };
  } | null;
  multiViews: Array<{ id: string; name: string; [key: string]: any } | null>;
}

interface AgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view') => void;
  onAddToContextRef?: (handler: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void) => void;
  onContextChange?: (context: ChatContextObject[]) => void;
  onWidthChange?: (width: number) => void;
  onLoadQuery?: (datasourceId: string, query: Record<string, any>) => void;
  selectedDatasource?: { id: string; name: string } | null;
  onActiveThreadChange?: (threadId: number | null) => void;
  renderedState?: RenderedState | null;
}

const MIN_WIDTH = 384; // w-96 equivalent
const MAX_WIDTH = 1200; // Maximum width
const DEFAULT_WIDTH = 384;

export function AgentPanel({ isOpen, onClose, onAddToContext, onAddToContextRef, onContextChange, onWidthChange, onLoadQuery, selectedDatasource, onActiveThreadChange, renderedState }: AgentPanelProps) {
  const [agentType, setAgentType] = useState<AgentType>('general');
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('gpt-4');
  const [threads, setThreads] = useState<ConversationResponse[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null);
  const [context, setContext] = useState<ChatContextObject[]>([]);
  const [loading, setLoading] = useState(false);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      loadThreads();
      loadUserPreferences();
    }
  }, [isOpen]);

  const loadUserPreferences = async () => {
    try {
      const user = await authApi.getCurrentUser();
      if (user.preferred_provider) {
        setProvider(user.preferred_provider);
      }
      if (user.preferred_model) {
        setModel(user.preferred_model);
      }
      if (user.preferred_agent_type) {
        setAgentType(user.preferred_agent_type as AgentType);
      }
    } catch (err) {
      console.error('Failed to load user preferences:', err);
    }
  };

  const savePreferences = async (preferences: {
    preferred_provider?: string;
    preferred_model?: string;
    preferred_agent_type?: string;
  }) => {
    try {
      await authApi.updatePreferences(preferences);
    } catch (err) {
      console.error('Failed to save user preferences:', err);
    }
  };

  useEffect(() => {
    if (activeThreadId) {
      loadContext(activeThreadId);
    }
  }, [activeThreadId]);

  // Notify parent of active thread changes separately to avoid infinite loops
  useEffect(() => {
    onActiveThreadChange?.(activeThreadId);
  }, [activeThreadId, onActiveThreadChange]);

  const loadThreads = async () => {
    try {
      const threadList = await chatApi.listConversations();
      setThreads(threadList);
      if (threadList.length > 0 && !activeThreadId) {
        setActiveThreadId(threadList[0].id);
      }
    } catch (err) {
      console.error('Failed to load threads:', err);
    }
  };
  
  const handleThreadsChange = () => {
    loadThreads();
  };

  const handleDeleteThread = async (threadId: number) => {
    // Reload threads to get updated list
    const updatedThreads = await chatApi.listConversations();
    setThreads(updatedThreads);
    
    // If the deleted thread was active, switch to another thread or clear active
    if (activeThreadId === threadId) {
      if (updatedThreads.length > 0) {
        setActiveThreadId(updatedThreads[0].id);
      } else {
        setActiveThreadId(null);
        setContext([]);
        onContextChange?.([]);
      }
    }
  };

  const loadContext = async (conversationId: number) => {
    try {
      const ctx = await chatContextApi.getContext(conversationId);
      setContext(ctx.objects);
      onContextChange?.(ctx.objects);
    } catch (err) {
      console.error('Failed to load context:', err);
    }
  };

  const handleCreateThread = async () => {
    try {
      // Store current thread's context before creating new thread
      const currentThreadContext = activeThreadId && context.length > 0 ? [...context] : [];
      
      const newThread = await chatApi.createConversation(agentType);
      setThreads([newThread, ...threads]);
      setActiveThreadId(newThread.id);
      // Reload context for the new thread (will be empty initially)
      setContext([]);
      
      // Restore context based on what's currently rendered and what was in previous thread
      if (renderedState && currentThreadContext.length > 0) {
        const contextToAdd: ChatContextObject[] = [];
        
        // Check if datasource is rendered and was in previous context
        if (renderedState.selectedObject?.type === 'datasource') {
          const datasourceId = renderedState.selectedObject.data.id;
          const wasInContext = currentThreadContext.some(
            (ctx) => ctx.object_id === datasourceId && ctx.object_type === 'datasource'
          );
          if (wasInContext) {
            try {
              const obj = await chatContextApi.addContext({
                conversation_id: newThread.id,
                object_id: datasourceId,
                object_type: 'datasource',
                object_name: renderedState.selectedObject.data.name,
              });
              contextToAdd.push(obj);
            } catch (err) {
              console.error('Failed to add datasource to context:', err);
            }
          }
        }
        
        // Check if views are rendered and were in previous context
        if (renderedState.multiViews && renderedState.multiViews.length > 0) {
          for (const view of renderedState.multiViews) {
            if (view) {
              const wasInContext = currentThreadContext.some(
                (ctx) => ctx.object_id === view.id && ctx.object_type === 'view'
              );
              if (wasInContext) {
                try {
                  const obj = await chatContextApi.addContext({
                    conversation_id: newThread.id,
                    object_id: view.id,
                    object_type: 'view',
                    object_name: view.name,
                  });
                  contextToAdd.push(obj);
                } catch (err) {
                  console.error('Failed to add view to context:', err);
                }
              }
            }
          }
        }
        
        if (contextToAdd.length > 0) {
          setContext(contextToAdd);
          onContextChange?.(contextToAdd);
          // Notify parent of context additions
          contextToAdd.forEach((obj) => {
            onAddToContext?.(obj.object_id, obj.object_type);
          });
        }
      }
    } catch (err) {
      console.error('Failed to create thread:', err);
    }
  };

  const handleRemoveContext = async (objectId: string) => {
    if (!activeThreadId) return;
    try {
      await chatContextApi.removeContext({
        conversation_id: activeThreadId,
        object_id: objectId,
      });
      const updatedContext = context.filter((obj) => obj.object_id !== objectId);
      setContext(updatedContext);
      onContextChange?.(updatedContext);
    } catch (err) {
      console.error('Failed to remove context:', err);
    }
  };

  const handleAddToContext = useCallback(async (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => {
    // Check if object is already in context
    const alreadyInContext = context.some(
      (obj) => obj.object_id === objectId && obj.object_type === objectType
    );
    
    if (alreadyInContext) {
      console.log(`Object ${objectId} (${objectType}) is already in context`);
      return;
    }

    // If no active thread, create one first
    let threadId = activeThreadId;
    if (!threadId) {
      try {
        const newThread = await chatApi.createConversation(agentType);
        setThreads((prev) => [newThread, ...prev]);
        threadId = newThread.id;
        setActiveThreadId(threadId);
        setContext([]); // Initialize empty context for new thread
        onContextChange?.([]);
        onContextChange?.([]);
      } catch (err) {
        console.error('Failed to create thread:', err);
        return;
      }
    }
    
    try {
      const obj = await chatContextApi.addContext({
        conversation_id: threadId,
        object_id: objectId,
        object_type: objectType,
        object_name: objectName,
      });
      // Update context state with the new object
      const updatedContext = [...context, obj];
      setContext(updatedContext);
      onContextChange?.(updatedContext);
      onAddToContext?.(objectId, objectType);
    } catch (err) {
      console.error('Failed to add context:', err);
    }
  }, [activeThreadId, context, onAddToContext]);

  // Expose handleAddToContext to parent via ref callback
  useEffect(() => {
    if (onAddToContextRef) {
      onAddToContextRef(handleAddToContext);
    }
  }, [onAddToContextRef, handleAddToContext]);

  // Handle resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      
      const newWidth = window.innerWidth - e.clientX;
      const clampedWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newWidth));
      setWidth(clampedWidth);
      onWidthChange?.(clampedWidth);
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
  }, [isResizing, onWidthChange]);

  // Notify parent of width changes
  useEffect(() => {
    onWidthChange?.(width);
  }, [width, onWidthChange]);

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed right-0 top-0 h-full bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 shadow-lg z-50 flex flex-col"
      style={{ width: `${width}px` }}
    >
      {/* Resize handle */}
      <div
        ref={resizeRef}
        onMouseDown={handleResizeStart}
        className="absolute left-0 top-0 h-full w-2 cursor-col-resize hover:bg-blue-200/50 dark:hover:bg-blue-700/50 active:bg-blue-300 dark:active:bg-blue-600 transition-colors z-10 group"
        style={{ touchAction: 'none' }}
        title="Drag to resize"
      >
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
          <GripVertical className="h-5 w-5 text-gray-600 dark:text-gray-300" />
        </div>
      </div>
      <div className="p-4 border-b border-gray-200 dark:border-gray-800 shrink-0">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <div className="w-5 h-5 flex-shrink-0">
              <img 
                src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTAgMTZDMCA3LjE2MzQ0IDcuMTYzNDQgMCAxNiAwQzI0LjgzNjYgMCAzMiA3LjE2MzQ0IDMyIDE2QzMyIDI0LjgzNjYgMjQuODM2NiAzMiAxNiAzMkM3LjE2MzQ0IDMyIDAgMjQuODM2NiAwIDE2WiIgZmlsbD0iI0NGRTlGRSIvPgo8cGF0aCBkPSJNMTguMTExNSAxNi42MjMxSDE4LjExOTJDMTcuODAzOCAxNi42NSAxNy41MjMxIDE2LjcwMzkgMTcuMjgwOCAxNi43ODA4QzE3LjI4MDggMTYuNzgwOCAxNi45MjY5IDE2Ljg5MjMgMTYuMzg0NiAxNi45NjkyQzE2LjI1NzcgMTYuOTg4NSAxNi4wOTYyIDE2Ljk4ODUgMTYuMDA3NyAxNi45ODg1SDE1Ljk0MjNDMTUuODUzOCAxNi45ODg1IDE1LjY4ODUgMTYuOTgwOCAxNS41NjU0IDE2Ljk2MTVDMTUuMDIzMSAxNi44NzMxIDE0LjY3MzEgMTYuNzUgMTQuNjczMSAxNi43NUMxNC40MzA4IDE2LjY3MzEgMTQuMTUgMTYuNjE1NCAxMy44MzQ2IDE2LjU4MDhDMTIuMTA3NyAxNi40MDM5IDExLjM2MTUgMTcuMDYxNSAxMS4zMTkyIDE3LjE4NDZDMTEuMjc2OSAxNy4zMDc3IDExLjQ2NTQgMTguOTA3NyAxMS42MDM4IDE5LjE2MTVDMTEuNzM4NSAxOS40MTE1IDExLjk0NjIgMTkuNTU3NyAxMi4xMzQ2IDE5LjYzODVDMTIuMzI2OSAxOS43MTkyIDEzLjkwNzcgMTkuODc2OSAxNC40MzQ2IDE5LjgwMzlDMTQuOTYxNSAxOS43MzA4IDE1LjA0MjMgMTkuNTUzOSAxNS4xODQ2IDE5LjI4NDZDMTUuMjg0NiAxOS4wOTIzIDE1LjU0MjMgMTguMjIzMSAxNS42ODQ2IDE3LjcxMTVDMTUuNzE5MiAxNy42MTE1IDE1LjcyMzEgMTcuNDExNSAxNS45NjU0IDE3LjM5NjJDMTYuMjA3NyAxNy40MTU0IDE2LjIxMTUgMTcuNjE5MiAxNi4yNDIzIDE3LjcxOTJDMTYuMzgwOCAxOC4yMzA4IDE2LjYyMzEgMTkuMTA3NyAxNi43MTkyIDE5LjNDMTYuODUzOCAxOS41NzMxIDE2LjkzNDYgMTkuNzUgMTcuNDYxNSAxOS44MzQ2QzE3Ljk4NDYgMTkuOTE1NCAxOS41NjkyIDE5Ljc4ODUgMTkuNzYxNSAxOS43MTE1QzE5Ljk1MzggMTkuNjM0NiAyMC4xNjE1IDE5LjQ5MjMgMjAuMyAxOS4yNDIzQzIwLjQzODUgMTguOTkyMyAyMC42NTM4IDE3LjM5NjIgMjAuNjE1NCAxNy4yNzMxQzIwLjU3NjkgMTcuMTQ2MiAxOS44NDIzIDE2LjQ3NjkgMTguMTExNSAxNi42MjMxWiIgZmlsbD0iIzAxNzZEMyIvPgo8cGF0aCBkPSJNMjMuNTA3NyAxMS41OTYySDIzLjUxMTVDMjMuMDMwOCAxMC45ODQ2IDIyLjQ2MTUgMTAuNDQyMyAyMS44MzA4IDkuOTc2OTNDMjIuNDg0NiA5Ljg2MTU1IDIyLjk4MDggOS4yOTIzMiAyMi45ODA4IDguNjA3N0MyMi45ODA4IDcuODM4NDcgMjIuMzU3NyA3LjIxMTU1IDIxLjU4NDYgNy4yMTE1NUMyMC44MTE1IDcuMjExNTUgMjAuMTg4NSA3LjgzNDYyIDIwLjE4ODUgOC42MDc3QzIwLjE4ODUgOC43NjE1NSAyMC4yMTkyIDguOTA3NyAyMC4yNjU0IDkuMDQ2MTZDMTkuMjczMSA4LjU3NjkzIDE4LjE4ODUgOC4yNjkyNCAxNy4wNTM4IDguMTUwMDFDMTUuMTUzOCA3Ljk1MDAxIDEzLjMxOTIgOC4yODg0NyAxMS43Mzg1IDkuMDM0NjJDMTEuNzgwOCA4LjkwMDAxIDExLjgxMTUgOC43NTc3IDExLjgxMTUgOC42MDc3QzExLjgxMTUgNy44Mzg0NyAxMS4xODg1IDcuMjExNTUgMTAuNDE1NCA3LjIxMTU1QzkuNjQyMzEgNy4yMTE1NSA5LjAxOTIzIDcuODM0NjIgOS4wMTkyMyA4LjYwNzdDOS4wMTkyMyA5LjI5MjMyIDkuNTExNTQgOS44NTc3IDEwLjE1NTcgOS45NzY5M0M4LjM2NTM4IDExLjMgNy4xMTUzOCAxMy4yMjY5IDYuODMwNzcgMTUuNDYxNUM2LjU2NTM4IDE3LjUyNjkgNy4xNTM4NCAxOS41OTYyIDguNDkyMzEgMjEuMjg4NUMxMC4wMDc3IDIzLjIwMzkgMTIuMzYxNSAyNC40NjE1IDE0Ljk0NjIgMjQuNzM0NkMxNS4zMDc3IDI0Ljc3MzEgMTUuNjY1NCAyNC43OTIzIDE2LjAxOTIgMjQuNzkyM0MyMC42MzA4IDI0Ljc5MjMgMjQuNjIzMSAyMS42NjE1IDI1LjE2OTIgMTcuNDIzMUMyNS40MzQ2IDE1LjM1NzcgMjQuODQ2MiAxMy4yODg1IDIzLjUwNzcgMTEuNTk2MlpNMTYuMDA3NyAyMi40MDc3SDE2LjAwMzhDMTIuNTM0NiAyMi40MDM5IDkuNzExNTQgMjAuMDg4NSA5LjcxMTU0IDE3LjI0MjNDOS43MTE1NCAxNi4zODQ2IDkuOTczMDggMTUuNTYxNSAxMC40NDYyIDE0LjgzMDhDMTAuNDg4NSAxNS4wOTIzIDEwLjU2NTQgMTUuMzE5MiAxMC42NSAxNS40ODg1QzEwLjc2NTQgMTUuNzE5MiAxMC45OTYyIDE1Ljg1MzkgMTEuMjM4NSAxNS44NTM5QzExLjMzNDYgMTUuODUzOSAxMS40MzQ2IDE1LjgzNDYgMTEuNTI2OSAxNS43ODg1QzExLjg1MzggMTUuNjMwOCAxMS45ODg1IDE1LjIzODUgMTEuODM4NSAxNC45MTE1QzExLjc1NzcgMTQuNzM4NSAxMS41NSAxNC4xNjU0IDEyLjA1MzggMTMuNzI2OUMxMi41NDIzIDE0LjE2OTIgMTMuMjQyMyAxNC42ODg1IDE0LjAzMDggMTQuOTQyM0MxNS41IDE1LjQwNzcgMTYuNjExNSAxNS4xMzQ2IDE2LjY1NzcgMTUuMTIzMUMxNi44ODA4IDE1LjA2NTQgMTcuMDUzOCAxNC45IDE3LjEyMzEgMTQuNjgwOEMxNy4xOTIzIDE0LjQ2MTUgMTcuMTQyMyAxNC4yMjMxIDE2Ljk5MjMgMTQuMDUzOUMxNi4yNSAxMy4yIDE1Ljg5NjIgMTIuNTc2OSAxNS43NDIzIDEyLjJDMTguNzUgMTIuNjA3NyAxOS4zMjY5IDE1LjAwMzkgMTkuMzUgMTUuMTExNUMxOS40MTU0IDE1LjQxOTIgMTkuNjg4NSAxNS42MzA4IDE5Ljk5MjMgMTUuNjMwOEMyMC4wMzg1IDE1LjYzMDggMjAuMDgwOCAxNS42MjY5IDIwLjEyNjkgMTUuNjE1NEMyMC40ODQ2IDE1LjU0MjMgMjAuNzExNSAxNS4xOTIzIDIwLjYzODUgMTQuODM0NkMyMC41NDYyIDE0LjM4ODUgMjAuMzAzOCAxMy43ODQ2IDE5Ljg3MzEgMTMuMTgwOEMyMS4zNDYyIDE0LjEyNjkgMjIuMyAxNS41OTYyIDIyLjMgMTcuMjQ2MkMyMi4zIDIwLjA5MjMgMTkuNDc2OSAyMi40MDc3IDE2LjAwNzcgMjIuNDA3N1oiIGZpbGw9IiMwMTc2RDMiLz4KPC9zdmc+Cg==" 
                alt="AI assistant" 
                className="w-full h-full object-contain"
              />
            </div>
            Agent Assistant
          </h2>
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <Settings className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80 p-4">
                <ModelSettings
                  provider={provider}
                  model={model}
                  onProviderChange={(newProvider) => {
                    setProvider(newProvider);
                    savePreferences({ preferred_provider: newProvider });
                  }}
                  onModelChange={(newModel) => {
                    setModel(newModel);
                    savePreferences({ preferred_model: newModel });
                  }}
                />
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="overflow-y-auto p-4 border-b border-gray-200 dark:border-gray-800 max-h-[40vh] shrink-0">
        <div>
          <h3 className="text-sm font-medium mb-2">Chat Threads</h3>
          <ThreadList
            threads={threads}
            activeThreadId={activeThreadId || undefined}
            onSelectThread={setActiveThreadId}
            onCreateThread={handleCreateThread}
            onThreadsChange={handleThreadsChange}
            onDeleteThread={handleDeleteThread}
          />
        </div>
      </div>

      {activeThreadId && (
        <div className="border-t border-gray-200 dark:border-gray-800 flex-1 flex flex-col min-h-0">
          <ChatInterface
            conversationId={activeThreadId}
            defaultModel={model}
            hideModelSelector={true}
            agentType={agentType}
            onAgentTypeChange={(newAgentType) => {
              setAgentType(newAgentType);
              savePreferences({ preferred_agent_type: newAgentType });
            }}
            context={context}
            onRemoveContext={handleRemoveContext}
            onLoadQuery={onLoadQuery}
          />
        </div>
      )}
    </div>
  );
}
