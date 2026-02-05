'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { chatApi, chatContextApi } from '@/lib/api';
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
import { X, MessageSquare, GripVertical, Settings } from 'lucide-react';
import type { ChatContextObject, ConversationResponse } from '@/types';

interface AgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view') => void;
  onAddToContextRef?: (handler: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void) => void;
  onContextChange?: (context: ChatContextObject[]) => void;
  onWidthChange?: (width: number) => void;
}

const MIN_WIDTH = 384; // w-96 equivalent
const MAX_WIDTH = 1200; // Maximum width
const DEFAULT_WIDTH = 384;

export function AgentPanel({ isOpen, onClose, onAddToContext, onAddToContextRef, onContextChange, onWidthChange, onLoadQuery }: AgentPanelProps) {
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
    }
  }, [isOpen]);

  useEffect(() => {
    if (activeThreadId) {
      loadContext(activeThreadId);
    }
  }, [activeThreadId]);

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
      const newThread = await chatApi.createConversation();
      setThreads([newThread, ...threads]);
      setActiveThreadId(newThread.id);
      // Reload context for the new thread (will be empty initially)
      setContext([]);
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
        const newThread = await chatApi.createConversation();
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
            <MessageSquare className="h-5 w-5" />
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
                  onProviderChange={setProvider}
                  onModelChange={setModel}
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
            onAgentTypeChange={setAgentType}
            context={context}
            onRemoveContext={handleRemoveContext}
            onLoadQuery={onLoadQuery}
          />
        </div>
      )}
    </div>
  );
}
