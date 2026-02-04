'use client';

import { useState, useEffect, useCallback } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ModelSelector } from './ModelSelector';
import { ErrorDisplay } from './ErrorDisplay';
import { ChatSkeleton } from './LoadingSkeleton';
import { DarkModeToggle } from './DarkModeToggle';
import { ConversationManager } from './ConversationManager';
import { chatApi } from '@/lib/api';
import type { Message, MessageRole } from '@/types';
import { cn } from '@/lib/utils';

export interface ChatInterfaceProps {
  conversationId?: number;
  className?: string;
  defaultModel?: string;
  hideModelSelector?: boolean;
  agentType?: 'summary' | 'vizql' | 'general';
}

const DEFAULT_MODEL = 'gpt-4';

export function ChatInterface({
  conversationId: initialConversationId,
  className,
  defaultModel = DEFAULT_MODEL,
  hideModelSelector = false,
  agentType,
}: ChatInterfaceProps) {
  const [conversationId, setConversationId] = useState<number | null>(
    initialConversationId || null
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>(defaultModel);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  // Sync selectedModel when defaultModel prop changes
  useEffect(() => {
    if (defaultModel) {
      setSelectedModel(defaultModel);
    }
  }, [defaultModel]);

  // Initialize conversation - only create if no ID provided
  useEffect(() => {
    const initConversation = async () => {
      if (!conversationId && !initialConversationId) {
        try {
          const conv = await chatApi.createConversation();
          setConversationId(conv.id);
        } catch (error) {
          console.error('Failed to create conversation:', error);
        }
      } else if (initialConversationId && conversationId !== initialConversationId) {
        // Sync conversationId when prop changes
        setConversationId(initialConversationId);
      }
    };

    initConversation();
  }, [initialConversationId]); // Only depend on prop, not conversationId to avoid loops

  // Load messages when conversation changes
  useEffect(() => {
    const loadMessages = async () => {
      if (!conversationId) {
        // Clear messages if no conversation
        setMessages([]);
        return;
      }
      
      setIsLoadingMessages(true);
      setError(null);
      try {
        const apiMessages = await chatApi.getMessages(conversationId);
        const formattedMessages: Message[] = apiMessages.map((msg) => ({
          id: msg.id.toString(),
          role: msg.role.toLowerCase() as MessageRole,
          content: msg.content,
          createdAt: new Date(msg.created_at),
          modelUsed: msg.model_used,
        }));
        setMessages(formattedMessages);
      } catch (error) {
        console.error('Failed to load messages:', error);
        setError(error instanceof Error ? error : new Error('Failed to load messages'));
        setMessages([]); // Clear messages on error
      } finally {
        setIsLoadingMessages(false);
      }
    };

    loadMessages();
  }, [conversationId]);

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!conversationId || isLoading) return;

      setIsLoading(true);
      setIsStreaming(true);
      setStreamingContent('');
      setError(null);

      // Add user message immediately
      const userMessage: Message = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content,
        createdAt: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);

      try {
        console.log('Starting stream for conversation:', conversationId, 'model:', selectedModel);
        // Stream the response
        await chatApi.sendMessageStream(
          {
            conversation_id: conversationId,
            content,
            model: selectedModel,
            agent_type: agentType,
            stream: true,
          },
          (chunk: string) => {
            console.log('Received chunk:', chunk);
            setStreamingContent((prev) => {
              // Handle token-level chunks that may not include spaces
              // LLM streaming tokens often arrive without spaces between words
              if (!prev) {
                return chunk;
              }
              
              if (!chunk) {
                return prev;
              }
              
              // Get the actual content boundaries (ignoring trailing/leading whitespace)
              const prevTrimmed = prev.trimEnd();
              const chunkTrimmed = chunk.trimStart();
              
              if (!prevTrimmed || !chunkTrimmed) {
                return prev + chunk;
              }
              
              const prevLastChar = prevTrimmed[prevTrimmed.length - 1];
              const chunkFirstChar = chunkTrimmed[0];
              
              // Check character types
              const prevIsAlphanumeric = /[a-zA-Z0-9]/.test(prevLastChar);
              const chunkIsAlphanumeric = /[a-zA-Z0-9]/.test(chunkFirstChar);
              const prevIsLowercase = /[a-z]/.test(prevLastChar);
              const chunkIsUppercase = /[A-Z]/.test(chunkFirstChar);
              const prevEndsWithSpace = /\s$/.test(prev);
              const prevEndsWithPunctuation = /[.,!?;:()\[\]{}"'`\-]/.test(prevLastChar);
              const chunkStartsWithPunctuation = /[.,!?;:()\[\]{}"'`\-]/.test(chunkFirstChar);
              
              // Add space if:
              // 1. Both are alphanumeric (potential word boundary)
              // 2. Previous doesn't already end with space or punctuation
              // 3. Chunk doesn't start with punctuation
              // 4. Special case: lowercase -> uppercase is definitely a new word
              const definitelyNewWord = prevIsLowercase && chunkIsUppercase;
              const likelyNewWord = prevIsAlphanumeric && chunkIsAlphanumeric;
              
              const needsSpace = 
                !prevEndsWithSpace &&
                !prevEndsWithPunctuation &&
                !chunkStartsWithPunctuation &&
                (definitelyNewWord || likelyNewWord);
              
              return needsSpace ? prev + ' ' + chunk : prev + chunk;
            });
          },
          async () => {
            // Reload messages to get the final assistant message
            try {
              const apiMessages = await chatApi.getMessages(conversationId);
              const formattedMessages: Message[] = apiMessages.map((msg) => ({
                id: msg.id.toString(),
                role: msg.role.toLowerCase() as MessageRole,
                content: msg.content,
                createdAt: new Date(msg.created_at),
                modelUsed: msg.model_used,
              }));
              setMessages(formattedMessages);
            } catch (error) {
              console.error('Failed to reload messages:', error);
              setError(error instanceof Error ? error : new Error('Failed to reload messages'));
            }
            setIsStreaming(false);
            setStreamingContent('');
            setIsLoading(false);
          },
          (error: Error) => {
            console.error('Streaming error:', error);
            setError(error);
            setIsStreaming(false);
            setStreamingContent('');
            setIsLoading(false);
            // Try non-streaming as fallback
            console.log('Attempting non-streaming fallback...');
            chatApi.sendMessage({
              conversation_id: conversationId,
              content,
              model: selectedModel,
              agent_type: agentType,
              stream: false,
            })
              .then((response) => {
                // Reload messages to get the assistant response
                return chatApi.getMessages(conversationId);
              })
              .then((apiMessages) => {
                const formattedMessages: Message[] = apiMessages.map((msg) => ({
                  id: msg.id.toString(),
                  role: msg.role.toLowerCase() as MessageRole,
                  content: msg.content,
                  createdAt: new Date(msg.created_at),
                  modelUsed: msg.model_used,
                }));
                setMessages(formattedMessages);
                setIsLoading(false);
                setError(null);
              })
              .catch((fallbackError) => {
                console.error('Fallback also failed:', fallbackError);
                setError(fallbackError instanceof Error ? fallbackError : new Error('Failed to send message'));
                // Remove the user message on error
                setMessages((prev) => prev.filter((msg) => msg.id !== userMessage.id));
              });
          }
        );
      } catch (error) {
        console.error('Failed to send message:', error);
        setError(error instanceof Error ? error : new Error('Failed to send message'));
        setIsStreaming(false);
        setStreamingContent('');
        setIsLoading(false);
        // Remove the user message on error
        setMessages((prev) => prev.filter((msg) => msg.id !== userMessage.id));
      }
    },
    [conversationId, selectedModel, isLoading, agentType]
  );

  const handleEditMessage = useCallback(
    async (messageId: string, newContent: string) => {
      // TODO: Implement message editing API endpoint
      console.log('Edit message:', messageId, newContent);
      // For now, just update locally
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId ? { ...msg, content: newContent } : msg
        )
      );
    },
    []
  );

  const handleDeleteMessage = useCallback(
    async (messageId: string) => {
      // TODO: Implement message deletion API endpoint
      console.log('Delete message:', messageId);
      // For now, just remove locally
      setMessages((prev) => prev.filter((msg) => msg.id !== messageId));
    },
    []
  );

  const handleRetry = useCallback(() => {
    setError(null);
    // Reload messages
    if (conversationId) {
      chatApi.getMessages(conversationId)
        .then((apiMessages) => {
          const formattedMessages: Message[] = apiMessages.map((msg) => ({
            id: msg.id.toString(),
            role: msg.role.toLowerCase() as MessageRole,
            content: msg.content,
            createdAt: new Date(msg.created_at),
            modelUsed: msg.model_used,
          }));
          setMessages(formattedMessages);
        })
        .catch((error) => {
          setError(error instanceof Error ? error : new Error('Failed to reload messages'));
        });
    }
  }, [conversationId]);

  // Display streaming content
  const displayMessages = isStreaming && (streamingContent || isLoading)
    ? [
        ...messages,
        {
          id: 'streaming',
          role: 'assistant' as MessageRole,
          content: streamingContent || '...',
          createdAt: new Date(),
        },
      ]
    : messages;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {!hideModelSelector && (
        <div className="p-2 sm:p-4 border-b flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 sm:gap-4">
          <div className="flex-1 min-w-0">
            <ModelSelector
              selected={selectedModel}
              onSelect={setSelectedModel}
              showProvider={true}
            />
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {conversationId && (
              <ConversationManager
                conversationId={conversationId}
                onDelete={() => {
                  setConversationId(null);
                  setMessages([]);
                }}
              />
            )}
            <DarkModeToggle />
          </div>
        </div>
      )}
      <div className="flex-1 overflow-hidden relative min-h-0">
        {isLoadingMessages ? (
          <ChatSkeleton />
        ) : error ? (
          <ErrorDisplay error={error} onRetry={handleRetry} />
        ) : (
          <MessageList
            messages={displayMessages}
            onEdit={handleEditMessage}
            onDelete={handleDeleteMessage}
            editable={true}
            streamingMessageId={isStreaming ? 'streaming' : undefined}
          />
        )}
      </div>
      <div className="p-2 sm:p-4 border-t">
        <MessageInput
          onSend={handleSendMessage}
          disabled={isLoading || !conversationId}
        />
      </div>
    </div>
  );
}
