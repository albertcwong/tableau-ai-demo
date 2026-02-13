'use client';

import { useState } from 'react';
import { ConversationResponse, chatApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MessageSquare, Plus, ChevronDown, ChevronUp, Edit2, Check, X, Trash2 } from 'lucide-react';

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
  onDeleteThread?: (threadId: number) => void;
}

export function ThreadList({
  threads,
  activeThreadId,
  onSelectThread,
  onCreateThread,
  onThreadsChange,
  onDeleteThread,
}: ThreadListProps) {
  const [expanded, setExpanded] = useState(false);
  const [editingThreadId, setEditingThreadId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);
  const [deletingThreadId, setDeletingThreadId] = useState<number | null>(null);
  const [isDeletingAll, setIsDeletingAll] = useState(false);

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

  const handleDeleteThread = async (threadId: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent thread selection
    
    if (!confirm('Are you sure you want to delete this chat thread? This action cannot be undone.')) {
      return;
    }

    setDeletingThreadId(threadId);
    try {
      await chatApi.deleteConversation(threadId);
      // Notify parent component about deletion
      if (onDeleteThread) {
        onDeleteThread(threadId);
      }
      // Refresh threads list
      if (onThreadsChange) {
        onThreadsChange();
      }
    } catch (err) {
      console.error('Failed to delete thread:', err);
      alert('Failed to delete thread. Please try again.');
    } finally {
      setDeletingThreadId(null);
    }
  };

  const handleDeleteAll = async () => {
    if (threads.length === 0) {
      return;
    }

    const confirmed = confirm(
      `Are you sure you want to delete all ${threads.length} chat thread(s)? This action cannot be undone.`
    );
    
    if (!confirmed) {
      return;
    }

    setIsDeletingAll(true);
    try {
      const result = await chatApi.deleteAllConversations();
      // Refresh threads list
      if (onThreadsChange) {
        onThreadsChange();
      }
      // Clear active thread if it was deleted
      if (activeThreadId) {
        onSelectThread(0);
      }
      alert(result.message);
    } catch (err) {
      console.error('Failed to delete all threads:', err);
      alert('Failed to delete all threads. Please try again.');
    } finally {
      setIsDeletingAll(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Button
          variant="outline"
          className="flex-1"
          onClick={onCreateThread}
        >
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
        <Button
          variant="ghost"
          onClick={() => setExpanded(!expanded)}
          className="flex-1 justify-between"
        >
          <span className="text-sm font-medium">History ({threads.length})</span>
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </Button>
      </div>
      
      <div>
        
        {expanded && (
          <div className="mt-2 space-y-1">
            {threads.length > 0 && (
              <div className="mb-2 px-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20"
                  onClick={handleDeleteAll}
                  disabled={isDeletingAll}
                >
                  <Trash2 className="h-3 w-3 mr-2" />
                  {isDeletingAll ? 'Deleting...' : `Delete All (${threads.length})`}
                </Button>
              </div>
            )}
            <div className="space-y-1 max-h-96 overflow-y-auto">
              {threads.map((thread) => {
              const isEditing = editingThreadId === thread.id;
              const displayName = getDisplayName(thread);
              
              return (
                <Card
                  key={thread.id}
                  className={`p-3 cursor-pointer transition-colors group rounded-none border-0 shadow-none ${
                    activeThreadId === thread.id
                      ? 'bg-blue-50 dark:bg-blue-900/20'
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
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 hover:opacity-100">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0 flex-shrink-0"
                              onClick={(e) => handleStartEdit(thread, e)}
                              title="Rename thread"
                            >
                              <Edit2 className="h-3 w-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0 flex-shrink-0 text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                              onClick={(e) => handleDeleteThread(thread.id, e)}
                              disabled={deletingThreadId === thread.id}
                              title="Delete thread"
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
