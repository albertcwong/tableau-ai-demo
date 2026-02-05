'use client';

import { useState, useEffect } from 'react';
import { ThumbsUp, ThumbsDown, Copy, Check, Code2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { chatApi } from '@/lib/api';

interface MessageActionBarProps {
  messageId: number;
  content: string;
  feedback?: string | null;
  totalTimeMs?: number | null;
  vizqlQuery?: Record<string, any> | null;
  onFeedbackChange?: (feedback: string | null) => void;
  onLoadQuery?: (query: Record<string, any>) => void;
}

export function MessageActionBar({
  messageId,
  content,
  feedback: initialFeedback,
  totalTimeMs,
  vizqlQuery,
  onFeedbackChange,
  onLoadQuery,
}: MessageActionBarProps) {
  const [isCopying, setIsCopying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<string | null | undefined>(initialFeedback);
  
  // Sync local state with prop changes
  useEffect(() => {
    setFeedback(initialFeedback);
  }, [initialFeedback]);

  const handleThumbsUp = async () => {
    try {
      const newFeedback = feedback === 'thumbs_up' ? null : 'thumbs_up';
      // Optimistically update UI
      setFeedback(newFeedback);
      await chatApi.updateMessageFeedback(messageId, newFeedback);
      onFeedbackChange?.(newFeedback);
    } catch (error) {
      console.error('Failed to update feedback:', error);
      // Revert on error
      setFeedback(initialFeedback);
    }
  };

  const handleThumbsDown = async () => {
    try {
      const newFeedback = feedback === 'thumbs_down' ? null : 'thumbs_down';
      // Optimistically update UI
      setFeedback(newFeedback);
      await chatApi.updateMessageFeedback(messageId, newFeedback);
      onFeedbackChange?.(newFeedback);
    } catch (error) {
      console.error('Failed to update feedback:', error);
      // Revert on error
      setFeedback(initialFeedback);
    }
  };

  const handleCopy = async () => {
    try {
      setIsCopying(true);
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => {
        setCopied(false);
        setIsCopying(false);
      }, 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
      setIsCopying(false);
    }
  };

  const handleLoadQuery = () => {
    console.log('Load Query clicked, vizqlQuery:', vizqlQuery, 'onLoadQuery:', onLoadQuery);
    if (vizqlQuery && onLoadQuery) {
      onLoadQuery(vizqlQuery);
    } else {
      console.warn('Cannot load query - vizqlQuery:', vizqlQuery, 'onLoadQuery:', onLoadQuery);
    }
  };

  const formatTime = (ms: number | null | undefined): string => {
    if (!ms) return '';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            'h-7 px-2',
            feedback === 'thumbs_up' && 'bg-green-100 dark:bg-green-900'
          )}
          onClick={handleThumbsUp}
          title="Thumbs up"
        >
          <ThumbsUp 
            className={cn(
              'h-3.5 w-3.5 transition-all',
              feedback === 'thumbs_up' 
                ? 'text-green-700 dark:text-green-300 stroke-[3] opacity-100' 
                : 'text-gray-600 dark:text-gray-400 stroke-[1.5] opacity-70'
            )} 
          />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            'h-7 px-2',
            feedback === 'thumbs_down' && 'bg-red-100 dark:bg-red-900'
          )}
          onClick={handleThumbsDown}
          title="Thumbs down"
        >
          <ThumbsDown 
            className={cn(
              'h-3.5 w-3.5 transition-all',
              feedback === 'thumbs_down' 
                ? 'text-red-700 dark:text-red-300 stroke-[3] opacity-100' 
                : 'text-gray-600 dark:text-gray-400 stroke-[1.5] opacity-70'
            )} 
          />
        </Button>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 px-2"
        onClick={handleCopy}
        disabled={isCopying}
        title={copied ? "Copied!" : "Copy"}
      >
        {copied ? (
          <Check className="h-3.5 w-3.5" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </Button>
      {vizqlQuery && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2"
          onClick={handleLoadQuery}
          title="Load Query"
        >
          <Code2 className="h-3.5 w-3.5" />
        </Button>
      )}
      {totalTimeMs && (
        <span className="text-xs text-gray-500 dark:text-gray-400 ml-auto">
          {formatTime(totalTimeMs)}
        </span>
      )}
    </div>
  );
}
