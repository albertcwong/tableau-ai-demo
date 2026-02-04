'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreVertical, Edit2, Trash2, Download, MessageSquare } from 'lucide-react';
import { chatApi, type ConversationResponse } from '@/lib/api';
import type { Message } from '@/types';

export interface ConversationManagerProps {
  conversationId: number;
  conversation?: ConversationResponse;
  onRename?: (id: number, name: string) => void;
  onDelete?: (id: number) => void;
  onExport?: (messages: Message[]) => void;
}

export function ConversationManager({
  conversationId,
  conversation,
  onRename,
  onDelete,
  onExport,
}: ConversationManagerProps) {
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');

  const handleRename = async () => {
    if (renameValue.trim() && onRename) {
      onRename(conversationId, renameValue.trim());
      setRenameDialogOpen(false);
      setRenameValue('');
    }
  };

  const handleDelete = async () => {
    if (confirm('Are you sure you want to delete this conversation? This cannot be undone.')) {
      try {
        await chatApi.deleteConversation(conversationId);
        if (onDelete) {
          onDelete(conversationId);
        }
      } catch (error) {
        console.error('Failed to delete conversation:', error);
        alert('Failed to delete conversation. Please try again.');
      }
    }
  };

  const handleExport = async () => {
    try {
      const messages = await chatApi.getMessages(conversationId);
      const formattedMessages: Message[] = messages.map((msg) => ({
        id: msg.id.toString(),
        role: msg.role.toLowerCase() as 'user' | 'assistant' | 'system',
        content: msg.content,
        createdAt: new Date(msg.created_at),
        modelUsed: msg.model_used,
      }));

      if (onExport) {
        onExport(formattedMessages);
      } else {
        // Default export: download as JSON
        const dataStr = JSON.stringify(formattedMessages, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `conversation-${conversationId}-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Failed to export conversation:', error);
      alert('Failed to export conversation. Please try again.');
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <MoreVertical className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setRenameDialogOpen(true)}>
          <Edit2 className="h-4 w-4 mr-2" />
          Rename
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleExport}>
          <Download className="h-4 w-4 mr-2" />
          Export
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleDelete} className="text-destructive">
          <Trash2 className="h-4 w-4 mr-2" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>

      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename Conversation</DialogTitle>
            <DialogDescription>
              Enter a new name for this conversation.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            placeholder="Conversation name"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleRename();
              }
            }}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleRename}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DropdownMenu>
  );
}
