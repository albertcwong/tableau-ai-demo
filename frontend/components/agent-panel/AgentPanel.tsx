'use client';

import { useState, useEffect, useCallback } from 'react';
import { chatApi, chatContextApi } from '@/lib/api';
import { AgentSelector, AgentType } from './AgentSelector';
import { ContextManager } from './ContextManager';
import { ModelSettings } from './ModelSettings';
import { ThreadList } from './ThreadList';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { X, MessageSquare } from 'lucide-react';
import type { ChatContextObject, ConversationResponse } from '@/types';

interface AgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onAddToContext?: (objectId: string, objectType: 'datasource' | 'view') => void;
  onAddToContextRef?: (handler: (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void) => void;
  onContextChange?: (context: ChatContextObject[]) => void;
}

export function AgentPanel({ isOpen, onClose, onAddToContext, onAddToContextRef, onContextChange }: AgentPanelProps) {
  const [agentType, setAgentType] = useState<AgentType>('general');
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('gpt-4');
  const [threads, setThreads] = useState<ConversationResponse[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null);
  const [context, setContext] = useState<ChatContextObject[]>([]);
  const [loading, setLoading] = useState(false);

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

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 shadow-lg z-50 flex flex-col">
      <div className="p-4 border-b border-gray-200 dark:border-gray-800 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Agent Assistant
          </h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <AgentSelector value={agentType} onValueChange={setAgentType} />
      </div>

      <div className="overflow-y-auto p-4 space-y-4 border-b border-gray-200 dark:border-gray-800 max-h-[40vh] shrink-0">
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

        <div>
          <h3 className="text-sm font-medium mb-2">Context</h3>
          <ContextManager objects={context} onRemove={handleRemoveContext} />
        </div>

        <ModelSettings
          provider={provider}
          model={model}
          onProviderChange={setProvider}
          onModelChange={setModel}
        />
      </div>

      {activeThreadId && (
        <div className="border-t border-gray-200 dark:border-gray-800 flex-1 flex flex-col min-h-0">
          <ChatInterface
            conversationId={activeThreadId}
            defaultModel={model}
            hideModelSelector={true}
            agentType={agentType}
          />
        </div>
      )}
    </div>
  );
}
