'use client';

import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { Message } from '@/types';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { Bot, Edit2, Trash2, X, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreVertical } from 'lucide-react';
import { MessageActionBar } from './MessageActionBar';
import { useAuth } from '@/components/auth/AuthContext';

export interface MessageListProps {
  messages: Message[];
  className?: string;
  onEdit?: (messageId: string, newContent: string) => void;
  onDelete?: (messageId: string) => void;
  onFeedbackChange?: (messageId: string, feedback: 'thumbs_up' | 'thumbs_down' | null, feedbackText?: string | null) => void;
  onLoadQuery?: (datasourceId: string, query: Record<string, any>) => void;
  editable?: boolean;
  streamingMessageId?: string;
}

function MessageItem({
  message,
  onEdit,
  onDelete,
  onFeedbackChange,
  onLoadQuery,
  editable,
  isStreaming = false,
}: {
  message: Message;
  onEdit?: (messageId: string, newContent: string) => void;
  onDelete?: (messageId: string) => void;
  onFeedbackChange?: (messageId: string, feedback: 'thumbs_up' | 'thumbs_down' | null, feedbackText?: string | null) => void;
  onLoadQuery?: (datasourceId: string, query: Record<string, any>) => void;
  editable?: boolean;
  isStreaming?: boolean;
}) {
  const { user } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  
  // Get first letter of username, fallback to 'U' if no user
  const userInitial = user?.username ? user.username.charAt(0).toUpperCase() : 'U';

  const handleSave = () => {
    if (editContent.trim() && editContent !== message.content && onEdit) {
      onEdit(message.id, editContent.trim());
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  const handleDelete = () => {
    if (onDelete && confirm('Are you sure you want to delete this message?')) {
      onDelete(message.id);
    }
  };

  return (
    <div
      className={cn(
        'flex gap-2 group',
        message.role === 'user' ? 'justify-end' : 'justify-start'
      )}
    >
      {message.role === 'assistant' && (
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="w-6 h-6 rounded-full flex items-center justify-center overflow-hidden">
            <img 
              src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTAgMTZDMCA3LjE2MzQ0IDcuMTYzNDQgMCAxNiAwQzI0LjgzNjYgMCAzMiA3LjE2MzQ0IDMyIDE2QzMyIDI0LjgzNjYgMjQuODM2NiAzMiAxNiAzMkM3LjE2MzQ0IDMyIDAgMjQuODM2NiAwIDE2WiIgZmlsbD0iI0NGRTlGRSIvPgo8cGF0aCBkPSJNMTguMTExNSAxNi42MjMxSDE4LjExOTJDMTcuODAzOCAxNi42NSAxNy41MjMxIDE2LjcwMzkgMTcuMjgwOCAxNi43ODA4QzE3LjI4MDggMTYuNzgwOCAxNi45MjY5IDE2Ljg5MjMgMTYuMzg0NiAxNi45NjkyQzE2LjI1NzcgMTYuOTg4NSAxNi4wOTYyIDE2Ljk4ODUgMTYuMDA3NyAxNi45ODg1SDE1Ljk0MjNDMTUuODUzOCAxNi45ODg1IDE1LjY4ODUgMTYuOTgwOCAxNS41NjU0IDE2Ljk2MTVDMTUuMDIzMSAxNi44NzMxIDE0LjY3MzEgMTYuNzUgMTQuNjczMSAxNi43NUMxNC40MzA4IDE2LjY3MzEgMTQuMTUgMTYuNjE1NCAxMy44MzQ2IDE2LjU4MDhDMTIuMTA3NyAxNi40MDM5IDExLjM2MTUgMTcuMDYxNSAxMS4zMTkyIDE3LjE4NDZDMTEuMjc2OSAxNy4zMDc3IDExLjQ2NTQgMTguOTA3NyAxMS42MDM4IDE5LjE2MTVDMTEuNzM4NSAxOS40MTE1IDExLjk0NjIgMTkuNTU3NyAxMi4xMzQ2IDE5LjYzODVDMTIuMzI2OSAxOS43MTkyIDEzLjkwNzcgMTkuODc2OSAxNC40MzQ2IDE5LjgwMzlDMTQuOTYxNSAxOS43MzA4IDE1LjA0MjMgMTkuNTUzOSAxNS4xODQ2IDE5LjI4NDZDMTUuMjg0NiAxOS4wOTIzIDE1LjU0MjMgMTguMjIzMSAxNS42ODQ2IDE3LjcxMTVDMTUuNzE5MiAxNy42MTE1IDE1LjcyMzEgMTcuNDExNSAxNS45NjU0IDE3LjM5NjJDMTYuMjA3NyAxNy40MTU0IDE2LjIxMTUgMTcuNjE5MiAxNi4yNDIzIDE3LjcxOTJDMTYuMzgwOCAxOC4yMzA4IDE2LjYyMzEgMTkuMTA3NyAxNi43MTkyIDE5LjNDMTYuODUzOCAxOS41NzMxIDE2LjkzNDYgMTkuNzUgMTcuNDYxNSAxOS44MzQ2QzE3Ljk4NDYgMTkuOTE1NCAxOS41NjkyIDE5Ljc4ODUgMTkuNzYxNSAxOS43MTE1QzE5Ljk1MzggMTkuNjM0NiAyMC4xNjE1IDE5LjQ5MjMgMjAuMyAxOS4yNDIzQzIwLjQzODUgMTguOTkyMyAyMC42NTM4IDE3LjM5NjIgMjAuNjE1NCAxNy4yNzMxQzIwLjU3NjkgMTcuMTQ2MiAxOS44NDIzIDE2LjQ3NjkgMTguMTExNSAxNi42MjMxWiIgZmlsbD0iIzAxNzZEMyIvPgo8cGF0aCBkPSJNMjMuNTA3NyAxMS41OTYySDIzLjUxMTVDMjMuMDMwOCAxMC45ODQ2IDIyLjQ2MTUgMTAuNDQyMyAyMS44MzA4IDkuOTc2OTNDMjIuNDg0NiA5Ljg2MTU1IDIyLjk4MDggOS4yOTIzMiAyMi45ODA4IDguNjA3N0MyMi45ODA4IDcuODM4NDcgMjIuMzU3NyA3LjIxMTU1IDIxLjU4NDYgNy4yMTE1NUMyMC44MTE1IDcuMjExNTUgMjAuMTg4NSA3LjgzNDYyIDIwLjE4ODUgOC42MDc3QzIwLjE4ODUgOC43NjE1NSAyMC4yMTkyIDguOTA3NyAyMC4yNjU0IDkuMDQ2MTZDMTkuMjczMSA4LjU3NjkzIDE4LjE4ODUgOC4yNjkyNCAxNy4wNTM4IDguMTUwMDFDMTUuMTUzOCA3Ljk1MDAxIDEzLjMxOTIgOC4yODg0NyAxMS43Mzg1IDkuMDM0NjJDMTEuNzgwOCA4LjkwMDAxIDExLjgxMTUgOC43NTc3IDExLjgxMTUgOC42MDc3QzExLjgxMTUgNy44Mzg0NyAxMS4xODg1IDcuMjExNTUgMTAuNDE1NCA3LjIxMTU1QzkuNjQyMzEgNy4yMTE1NSA5LjAxOTIzIDcuODM0NjIgOS4wMTkyMyA4LjYwNzdDOS4wMTkyMyA5LjI5MjMyIDkuNTExNTQgOS44NTc3IDEwLjE1NzcgOS45NzY5M0M4LjM2NTM4IDExLjMgNy4xMTUzOCAxMy4yMjY5IDYuODMwNzcgMTUuNDYxNUM2LjU2NTM4IDE3LjUyNjkgNy4xNTM4NCAxOS41OTYyIDguNDkyMzEgMjEuMjg4NUMxMC4wMDc3IDIzLjIwMzkgMTIuMzYxNSAyNC40NjE1IDE0Ljk0NjIgMjQuNzM0NkMxNS4zMDc3IDI0Ljc3MzEgMTUuNjY1NCAyNC43OTIzIDE2LjAxOTIgMjQuNzkyM0MyMC42MzA4IDI0Ljc5MjMgMjQuNjIzMSAyMS42NjE1IDI1LjE2OTIgMTcuNDIzMUMyNS40MzQ2IDE1LjM1NzcgMjQuODQ2MiAxMy4yODg1IDIzLjUwNzcgMTEuNTk2MlpNMTYuMDA3NyAyMi40MDc3SDE2LjAwMzhDMTIuNTM0NiAyMi40MDM5IDkuNzExNTQgMjAuMDg4NSA5LjcxMTU0IDE3LjI0MjNDOS43MTE1NCAxNi4zODQ2IDkuOTczMDggMTUuNTYxNSAxMC40NDYyIDE0LjgzMDhDMTAuNDg4NSAxNS4wOTIzIDEwLjU2NTQgMTUuMzE5MiAxMC42NSAxNS40ODg1QzEwLjc2NTQgMTUuNzE5MiAxMC45OTYyIDE1Ljg1MzkgMTEuMjM4NSAxNS44NTM5QzExLjMzNDYgMTUuODUzOSAxMS40MzQ2IDE1LjgzNDYgMTEuNTI2OSAxNS43ODg1QzExLjg1MzggMTUuNjMwOCAxMS45ODg1IDE1LjIzODUgMTEuODM4NSAxNC45MTE1QzExLjc1NzcgMTQuNzM4NSAxMS41NSAxNC4xNjU0IDEyLjA1MzggMTMuNzI2OUMxMi41NDIzIDE0LjE2OTIgMTMuMjQyMyAxNC42ODg1IDE0LjAzMDggMTQuOTQyM0MxNS41IDE1LjQwNzcgMTYuNjExNSAxNS4xMzQ2IDE2LjY1NzcgMTUuMTIzMUMxNi44ODA4IDE1LjA2NTQgMTcuMDUzOCAxNC45IDE3LjEyMzEgMTQuNjgwOEMxNy4xOTIzIDE0LjQ2MTUgMTcuMTQyMyAxNC4yMjMxIDE2Ljk5MjMgMTQuMDUzOUMxNi4yNSAxMy4yIDE1Ljg5NjIgMTIuNTc2OSAxNS43NDIzIDEyLjJDMTguNzUgMTIuNjA3NyAxOS4zMjY5IDE1LjAwMzkgMTkuMzUgMTUuMTExNUMxOS40MTU0IDE1LjQxOTIgMTkuNjg4NSAxNS42MzA4IDE5Ljk5MjMgMTUuNjMwOEMyMC4wMzg1IDE1LjYzMDggMjAuMDgwOCAxNS42MjY5IDIwLjEyNjkgMTUuNjE1NEMyMC40ODQ2IDE1LjU0MjMgMjAuNzExNSAxNS4xOTIzIDIwLjYzODUgMTQuODM0NkMyMC41NDYyIDE0LjM4ODUgMjAuMzAzOCAxMy43ODQ2IDE5Ljg3MzEgMTMuMTgwOEMyMS4zNDYyIDE0LjEyNjkgMjIuMyAxNS41OTYyIDIyLjMgMTcuMjQ2MkMyMi4zIDIwLjA5MjMgMTkuNDc2OSAyMi40MDc3IDE2LjAwNzcgMjIuNDA3N1oiIGZpbGw9IiMwMTc2RDMiLz4KPC9zdmc+Cg==" 
              alt="AI assistant" 
              className="w-full h-full object-contain"
            />
          </div>
          {isStreaming && (
            <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
              <span>Working on it</span>
              <span className="flex gap-0.5">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
              </span>
            </div>
          )}
        </div>
      )}
      {/* Hide message bubble during reasoning phase (when content is "..." or empty) */}
      {!(isStreaming && message.role === 'assistant' && (!message.content || message.content.trim() === '' || message.content.trim() === '...')) && (
        <div
          className={cn(
            'rounded-lg px-2 py-1.5 sm:px-3 max-w-[85%] sm:max-w-[80%] relative overflow-hidden',
            message.role === 'user'
              ? 'text-black'
              : 'bg-muted text-foreground'
          )}
          style={{ border: 'none', outline: 'none', boxShadow: 'none' }}
        >
        {isEditing ? (
          <div className="space-y-2">
            <Input
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="text-foreground bg-background"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  handleSave();
                } else if (e.key === 'Escape') {
                  handleCancel();
                }
              }}
              autoFocus
            />
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={handleSave}>
                <Check className="h-3 w-3 mr-1" />
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={handleCancel}>
                <X className="h-3 w-3 mr-1" />
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <>
            {isStreaming ? (
              // Render streaming content as plain text with preserved line breaks
              <div className={cn(
                'prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap break-words',
                message.role === 'user' && 'text-black'
              )} style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
                {message.content}
                {/* Only show cursor when there's actual content (final answer), not during reasoning phase */}
                {message.content && message.content.trim() !== '...' && message.content.trim().length > 0 && (
                  <span className="animate-pulse">▋</span>
                )}
              </div>
            ) : (
              // Render complete messages with full markdown support
              <div className={cn(
                'prose prose-sm dark:prose-invert max-w-none break-words',
                message.role === 'user' && '[&_*]:!text-black',
                '[&_p]:break-words [&_li]:break-words [&_td]:break-words [&_th]:break-words'
              )} style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Headings
                    h1: ({ children, ...props }: any) => (
                      <h1 className="text-2xl font-bold mt-4 mb-2 first:mt-0" {...props}>
                        {children}
                      </h1>
                    ),
                    h2: ({ children, ...props }: any) => (
                      <h2 className="text-xl font-bold mt-4 mb-2 first:mt-0" {...props}>
                        {children}
                      </h2>
                    ),
                    h3: ({ children, ...props }: any) => (
                      <h3 className="text-lg font-semibold mt-4 mb-2 first:mt-0" {...props}>
                        {children}
                      </h3>
                    ),
                    h4: ({ children, ...props }: any) => (
                      <h4 className="text-base font-semibold mt-3 mb-2 first:mt-0" {...props}>
                        {children}
                      </h4>
                    ),
                    h5: ({ children, ...props }: any) => (
                      <h5 className="text-sm font-semibold mt-3 mb-2 first:mt-0" {...props}>
                        {children}
                      </h5>
                    ),
                    h6: ({ children, ...props }: any) => (
                      <h6 className="text-xs font-semibold mt-3 mb-2 first:mt-0" {...props}>
                        {children}
                      </h6>
                    ),
                    // Paragraphs
                    p: ({ children, ...props }: any) => (
                      <p className="mb-4 last:mb-0 break-words" {...props}>
                        {children}
                      </p>
                    ),
                    // Lists
                    ul: ({ children, ...props }: any) => (
                      <ul className="list-disc pl-6 mb-4 space-y-1" {...props}>
                        {children}
                      </ul>
                    ),
                    ol: ({ children, ...props }: any) => (
                      <ol className="list-decimal pl-6 mb-4 space-y-1" {...props}>
                        {children}
                      </ol>
                    ),
                    li: ({ children, ...props }: any) => (
                      <li className="mb-1 break-words" {...props}>
                        {children}
                      </li>
                    ),
                    // Links
                    a: ({ href, children, ...props }: any) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary underline hover:text-primary/80 break-words"
                        {...props}
                      >
                        {children}
                      </a>
                    ),
                    // Code blocks and inline code
                    code: ({ className, children, ...props }: any) => {
                      const match = /language-(\w+)/.exec(className || '');
                      const isInline = !match;
                      return !isInline && match ? (
                        <SyntaxHighlighter
                          style={oneDark as any}
                          language={match[1]}
                          PreTag="div"
                          className="rounded-md overflow-x-auto max-w-full my-4"
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      ) : (
                        <code
                          className={cn(
                            'bg-muted px-1.5 py-0.5 rounded text-sm font-mono break-words',
                            className
                          )}
                          {...props}
                          style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}
                        >
                          {children}
                        </code>
                      );
                    },
                    // Pre blocks (handled by SyntaxHighlighter, but fallback)
                    pre: ({ children, ...props }: any) => (
                      <pre className="bg-muted rounded-md p-4 overflow-x-auto mb-4" {...props}>
                        {children}
                      </pre>
                    ),
                    // Blockquotes
                    blockquote: ({ children, ...props }: any) => (
                      <blockquote
                        className="border-l-4 border-muted-foreground pl-4 italic my-4 text-muted-foreground"
                        {...props}
                      >
                        {children}
                      </blockquote>
                    ),
                    // Tables
                    table: ({ children, ...props }: any) => (
                      <div className="overflow-x-auto my-4">
                        <table className="w-full border-collapse border border-border" {...props}>
                          {children}
                        </table>
                      </div>
                    ),
                    thead: ({ children, ...props }: any) => (
                      <thead className="bg-muted" {...props}>
                        {children}
                      </thead>
                    ),
                    tbody: ({ children, ...props }: any) => (
                      <tbody {...props}>
                        {children}
                      </tbody>
                    ),
                    tr: ({ children, ...props }: any) => (
                      <tr className="border-b border-border" {...props}>
                        {children}
                      </tr>
                    ),
                    th: ({ children, ...props }: any) => (
                      <th
                        className="border border-border px-4 py-2 text-left font-semibold break-words"
                        {...props}
                      >
                        {children}
                      </th>
                    ),
                    td: ({ children, ...props }: any) => (
                      <td
                        className="border border-border px-4 py-2 break-words"
                        {...props}
                      >
                        {children}
                      </td>
                    ),
                    // Horizontal rule
                    hr: ({ ...props }: any) => (
                      <hr className="my-6 border-t border-border" {...props} />
                    ),
                    // Images
                    img: ({ src, alt, ...props }: any) => (
                      <img
                        src={src}
                        alt={alt}
                        className="max-w-full h-auto rounded-md my-4"
                        {...props}
                      />
                    ),
                    // Strong/Bold
                    strong: ({ children, ...props }: any) => (
                      <strong className="font-bold" {...props}>
                        {children}
                      </strong>
                    ),
                    // Emphasis/Italic
                    em: ({ children, ...props }: any) => (
                      <em className="italic" {...props}>
                        {children}
                      </em>
                    ),
                    // Task lists (from remark-gfm)
                    input: ({ checked, ...props }: any) => (
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled
                        className="mr-2"
                        {...props}
                      />
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
            {message.role === 'assistant' && !isStreaming && !message.extraMetadata?.is_greeting && (
              <MessageActionBar
                messageId={parseInt(message.id)}
                content={message.content}
                feedback={message.feedback}
                feedbackText={message.feedbackText}
                totalTimeMs={message.totalTimeMs}
                vizqlQuery={message.vizqlQuery}
                onFeedbackChange={(newFeedback, newFeedbackText) => {
                  onFeedbackChange?.(message.id, newFeedback, newFeedbackText);
                }}
                onLoadQuery={(query) => {
                  console.log('MessageList onLoadQuery called with query:', query);
                  // Extract datasource ID from query - try multiple possible structures
                  let datasourceId = query?.datasource?.datasourceLuid;
                  if (!datasourceId && query?.datasource) {
                    // Try direct datasource string or other structures
                    datasourceId = typeof query.datasource === 'string' ? query.datasource : query.datasource.id || query.datasource.luid;
                  }
                  console.log('Extracted datasourceId:', datasourceId, 'onLoadQuery prop:', onLoadQuery);
                  if (datasourceId && onLoadQuery) {
                    // Call the parent's onLoadQuery handler to navigate and load
                    console.log('Calling onLoadQuery with datasourceId and query');
                    onLoadQuery(datasourceId, query);
                  } else if (datasourceId) {
                    // Fallback: store in localStorage and dispatch event
                    console.log('Using fallback: storing in localStorage and dispatching event');
                    localStorage.setItem(`vizql_query_${datasourceId}`, JSON.stringify(query, null, 2));
                    window.dispatchEvent(new CustomEvent('loadVizQLQuery', { 
                      detail: { datasourceId, query } 
                    }));
                  } else {
                    console.warn('No datasource ID found in query. Query structure:', JSON.stringify(query, null, 2));
                  }
                }}
              />
            )}
            {editable && message.role === 'user' && (
              <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical className="h-3 w-3" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => setIsEditing(true)}>
                      <Edit2 className="h-4 w-4 mr-2" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={handleDelete} className="text-destructive">
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}
          </>
        )}
        </div>
      )}
      {message.role === 'user' && (
        <div className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgb(42,87,117)' }}>
          <span className="text-xs font-semibold text-white">
            {userInitial}
          </span>
        </div>
      )}
    </div>
  );
}

export function MessageList({
  messages,
  className,
  onEdit,
  onDelete,
  onFeedbackChange,
  onLoadQuery,
  editable = false,
  streamingMessageId,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // For streaming content, use instant scroll for smoother updates
    // For new messages, use smooth scroll
    if (streamingMessageId) {
      // Instant scroll during streaming for better performance
      requestAnimationFrame(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'auto' });
      });
    } else {
      // Smooth scroll for new complete messages
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, streamingMessageId]);

  if (messages.length === 0) {
    return (
      <div className={cn('flex items-center justify-center h-full text-muted-foreground', className)}>
        <p className="text-sm">No messages yet. Start a conversation!</p>
      </div>
    );
  }

  return (
    <ScrollArea className={cn('h-full', className)}>
      <div className="space-y-4 sm:space-y-5 p-1 sm:p-2">
        {messages.map((message) => (
          <MessageItem
            key={message.id}
            message={message}
            onEdit={onEdit}
            onDelete={onDelete}
            onFeedbackChange={onFeedbackChange}
            onLoadQuery={onLoadQuery}
            editable={editable}
            isStreaming={streamingMessageId === message.id}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
