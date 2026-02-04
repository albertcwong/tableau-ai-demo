'use client';

import { useState } from 'react';
import { ConversationResponse, chatApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MessageSquare, Plus, ChevronDown, ChevronUp, Edit2, Check, X } from 'lucide-react';

// Simple date formatting without date-fns
const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric'});
};

// Get display name for thread
const getDisplayName = (thread: ConversationResponse): string => {
  if (thread.name) {
    return thread.name;
  }
  // Fallback to "Chat {id}" if no name
  return `Chat ${thread.id}`;
};

interface ThreadListProps {
  threads: ConversationResponse[];
  activeThreadId?: number;
  onSelectThread: (threadId: number) => void;
  onCreateThread: () => void;
  onThreadsChange?: () => void;
}

export function ThreadList({
  threads,
  activeThreadId,
  onSelectThread,
  onCreateThread,
  onThreadsChange,
}: ThreadListProps) {
  const [expanded, setExpanded] = useState(false);
  const [editingThreadId, setEditingThreadId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);

  const handleStartEdit = (thread: ConversationResponse, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent thread selection
    setEditingThreadId(thread.id);
    setEditName(thread.name || getDisplayName(thread));
  };

  const handleCancelEdit = () => {
    setEditingThreadId(null);
    setEditName('');
  };

  const handleSaveEdit = async (threadId: number, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation(); // Prevent thread selection
    }
    
    if (!editName.trim()) {
      handleCancelEdit();
      return;
    }

    setIsRenaming(true);
    try {
      await chatApi.renameConversation(threadId, editName.trim());
      setEditingThreadId(null);
      setEditName('');
      // Refresh threads list
      if (onThreadsChange) {
        onThreadsChange();
      }
    } catch (err) {
      console.error('Failed to rename thread:', err);
    } finally {
      setIsRenaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, threadId: number) => {
    if (e.key === 'Enter') {
      handleSaveEdit(threadId);
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  return (
    <div className="space-y-2">
      <Button
        variant="outline"
        className="w-full"
        onClick={onCreateThread}
      >
        <Plus className="h-4 w-4 mr-2" />
        New Chat
      </Button>
      
      <div>
        <Button
          variant="ghost"
          onClick={() => setExpanded(!expanded)}
          className="w-full justify-between"
        >
          <span className="text-sm font-medium">Chat History ({threads.length})</span>
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </Button>
        
        {expanded && (
          <div className="mt-2 space-y-1 max-h-96 overflow-y-auto">
            {threads.map((thread) => {
              const isEditing = editingThreadId === thread.id;
              const displayName = getDisplayName(thread);
              
              return (
                <Card
                  key={thread.id}
                  className={`p-3 cursor-pointer transition-colors group ${
                    activeThreadId === thread.id
                      ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                  }`}
                  onClick={() => !isEditing && onSelectThread(thread.id)}
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare className="h-4 w-4 mt-0.5 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      {isEditing ? (
                        <div className="flex items-center gap-1">
                          <Input
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            onKeyDown={(e) => handleKeyDown(e, thread.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="h-7 text-sm flex-1"
                            autoFocus
                            maxLength={255}
                          />
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0"
                            onClick={(e) => handleSaveEdit(thread.id, e)}
                            disabled={isRenaming}
                          >
                            <Check className="h-3 w-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0"
                            onClick={handleCancelEdit}
                            disabled={isRenaming}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium truncate">
                              {displayName}
                            </div>
                            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                              <span>{formatDate(thread.created_at)}</span>
                              {thread.message_count > 0 && (
                                <span>• {thread.message_count} {thread.message_count === 1 ? 'message' : 'messages'}</span>
                              )}
                            </div>
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 hover:opacity-100 flex-shrink-0"
                            onClick={(e) => handleStartEdit(thread, e)}
                            title="Rename thread"
                          >
                            <Edit2 className="h-3 w-3" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
