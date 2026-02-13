'use client';

import { useState, FormEvent, forwardRef, useImperativeHandle, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Send, X } from 'lucide-react';

export interface MessageInputProps {
  onSend: (message: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export interface MessageInputRef {
  focus: () => void;
}

export const MessageInput = forwardRef<MessageInputRef, MessageInputProps>(function MessageInput({
  onSend,
  onCancel,
  disabled = false,
  placeholder = 'Type a message...',
  className,
}, ref) {
  const [message, setMessage] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => inputRef.current?.focus(),
  }), []);

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmedMessage = message.trim();
    if (trimmedMessage && !disabled) {
      onSend(trimmedMessage);
      setMessage('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    // Cmd/Ctrl+Enter or Enter (without Shift) to send
    if ((e.key === 'Enter' && (e.metaKey || e.ctrlKey)) || (e.key === 'Enter' && !e.shiftKey)) {
      e.preventDefault();
      const trimmedMessage = message.trim();
      if (trimmedMessage && !disabled) {
        onSend(trimmedMessage);
        setMessage('');
      }
    }
    // Escape to clear input
    if (e.key === 'Escape') {
      setMessage('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className={className}>
      <div className="flex gap-2">
        <Input
          ref={inputRef}
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="flex-1"
        />
        {onCancel ? (
          <Button
            type="button"
            onClick={onCancel}
            variant="outline"
            size="icon"
            title="Cancel message"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Cancel message</span>
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={disabled || !message.trim()}
            size="icon"
            title="Press Enter to send, Cmd/Ctrl+Enter for new line, Esc to clear"
          >
            <Send className="h-4 w-4" />
            <span className="sr-only">Send message</span>
          </Button>
        )}
      </div>
    </form>
  );
});
