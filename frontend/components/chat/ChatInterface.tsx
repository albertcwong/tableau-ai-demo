'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ModelSelector } from './ModelSelector';
import { ErrorDisplay } from './ErrorDisplay';
import { ChatSkeleton } from './LoadingSkeleton';
import { DarkModeToggle } from './DarkModeToggle';
import { ConversationManager } from './ConversationManager';
import { ReasoningSteps } from './ReasoningSteps';
import { AgentSelector } from '@/components/agent-panel/AgentSelector';
import { ContextManager } from '@/components/agent-panel/ContextManager';
import { chatApi } from '@/lib/api';
import type { Message, MessageRole, AgentMessageChunk, ChatContextObject } from '@/types';
import { cn } from '@/lib/utils';

// Text parsing functions removed - we now use structured messages from the backend
// The backend sends AgentMessageChunk objects with message_type ('reasoning' or 'final_answer')
// which allows the frontend to handle them appropriately without text parsing

export interface ChatInterfaceProps {
  conversationId?: number;
  className?: string;
  defaultModel?: string;
  hideModelSelector?: boolean;
  agentType?: 'summary' | 'vizql' | 'general';
  onAgentTypeChange?: (agentType: 'summary' | 'vizql' | 'general') => void;
  context?: ChatContextObject[];
  onRemoveContext?: (objectId: string) => void;
  onLoadQuery?: (datasourceId: string, query: Record<string, any>) => void;
}

const DEFAULT_MODEL = 'gpt-4';

export function ChatInterface({
  conversationId: initialConversationId,
  className,
  defaultModel = DEFAULT_MODEL,
  hideModelSelector = false,
  agentType = 'general',
  onAgentTypeChange,
  context = [],
  onRemoveContext,
  onLoadQuery,
}: ChatInterfaceProps) {
  const [conversationId, setConversationId] = useState<number | null>(
    initialConversationId || null
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>(defaultModel);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [lastReasoningSteps, setLastReasoningSteps] = useState<string>('');
  const [stepTimings, setStepTimings] = useState<Array<{ text: string; duration: number; startTime: number; nodeName?: string; stepIndex?: number; toolCalls?: string[]; tokens?: { prompt?: number; completion?: number; total?: number } }>>([]);
  const [streamStartTime, setStreamStartTime] = useState<number | null>(null);
  const [reasoningTotalTimeMs, setReasoningTotalTimeMs] = useState<number | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

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
          feedback: msg.feedback,
          feedbackText: msg.feedback_text,
          totalTimeMs: msg.total_time_ms,
          vizqlQuery: msg.vizql_query,
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

  const handleCancelMessage = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setIsLoading(false);
    setStreamingContent('');
    setLastReasoningSteps('');
    setStepTimings([]);
    setStreamStartTime(null);
    setReasoningTotalTimeMs(null);
    // Remove the temporary user message if it exists
    setMessages((prev) => prev.filter((msg) => !msg.id.startsWith('temp-')));
  }, []);

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!conversationId || isLoading) return;

      // Create new AbortController for this request
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      const startTime = Date.now();
      setIsLoading(true);
      setIsStreaming(true);
      setStreamingContent('');
      setLastReasoningSteps(''); // Clear previous reasoning steps
      setStepTimings([]); // Clear previous step timings
      setStreamStartTime(startTime); // Track when streaming starts
      setReasoningTotalTimeMs(null); // Clear previous total time
      setError(null);
      
      // Track reasoning steps and final answer separately
      let reasoningStepsText = '';
      let finalAnswerText = '';
      // Track steps by step_index to handle multiple steps from same node
      let finalStepTimings: Array<{ text: string; duration: number; startTime: number; nodeName?: string; stepIndex?: number; toolCalls?: string[]; tokens?: { prompt?: number; completion?: number; total?: number } }> = [];
      let reasoningStepIndex = 0;
      let storedVizqlQuery: Record<string, any> | null = null; // Store vizql_query from metadata
      let firstReasoningStepTime: number | null = null; // Track when first reasoning step arrives
      let finalAnswerStartTime: number | null = null; // Track when final answer starts
      
      // Map node names to human-readable step names
      const nodeNameMap: Record<string, string> = {
        // Summary agent nodes
        'data_fetcher': 'Fetching view data',
        'analyzer': 'Analyzing data',
        'insight_gen': 'Generating insights',
        'summarizer': 'Generating summary',
        // VizQL agent nodes (graph-based)
        'planner': 'Planning query',
        'schema_fetch': 'Fetching schema',
        'query_builder': 'Building query',
        'validator': 'Validating query',
        'refiner': 'Refining query',
        'executor': 'Executing query',
        'formatter': 'Formatting results',
        'error_handler': 'Handling errors',
        // Tool-use VizQL agent nodes
        'start': 'Starting analysis',
        'get_data': 'Retrieving data',
        'summarize': 'Generating response',
      };

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
        // Stream the response with structured message handling
        await chatApi.sendMessageStream(
          {
            conversation_id: conversationId,
            content,
            model: selectedModel,
            agent_type: agentType,
            stream: true,
          },
          (chunk: string) => {
            // Legacy text chunk handler (for backward compatibility)
            // This should not be called if structured chunks are being used
            // If we receive legacy chunks, treat them as final_answer
            console.warn('Received legacy text chunk:', chunk);
            if (chunk && chunk.trim()) {
              finalAnswerText += chunk;
              setStreamingContent(finalAnswerText);
            }
          },
          async () => {
            // onComplete - finalize step timings and reload messages
            try {
              // Finalize step timings - calculate durations between steps
              const finalTime = Date.now() - startTime;
              
              // Store finalized timings in a variable accessible throughout this function
              let finalizedTimings: Array<{ text: string; duration: number; startTime: number; nodeName?: string; stepIndex?: number; toolCalls?: string[]; tokens?: { prompt?: number; completion?: number; total?: number } }> = [];
              
              if (finalStepTimings.length > 0 && finalTime > 0) {
                // Most durations should already be calculated correctly during streaming
                // Only fix edge cases where durations are missing or incorrect
                finalizedTimings = finalStepTimings.map((timing, index) => {
                  // If duration is already set and reasonable, use it
                  if (timing.duration > 0) {
                    return timing;
                  }
                  
                  // Duration is 0 or missing - calculate it based on completion times
                  if (index === finalStepTimings.length - 1) {
                    // Last reasoning step: duration from its start to when final answer started
                    // (or end of streaming if final answer never started)
                    const endTime = finalAnswerStartTime !== null ? finalAnswerStartTime : finalTime;
                    const duration = Math.max(50, endTime - timing.startTime);
                    return { ...timing, duration };
                  }
                  
                  // Middle step: duration from start to when next step started
                  // Next step's start time = when this step completed
                  const nextStep = finalStepTimings[index + 1];
                  if (nextStep) {
                    // Next step started when this step completed
                    const duration = Math.max(50, nextStep.startTime - timing.startTime);
                    return { ...timing, duration };
                  }
                  
                  // Fallback: use a minimal duration
                  return { ...timing, duration: 50 };
                });
                
                // Verify and adjust the last step's duration if needed
                if (finalizedTimings.length > 0) {
                  const lastStepIndex = finalizedTimings.length - 1;
                  const lastStep = finalizedTimings[lastStepIndex];
                  const endTime = finalAnswerStartTime !== null ? finalAnswerStartTime : finalTime;
                  const expectedLastStepDuration = endTime - lastStep.startTime;
                  
                  // If last step duration is less than expected, adjust it
                  if (lastStep.duration < expectedLastStepDuration) {
                    finalizedTimings[lastStepIndex] = {
                      ...lastStep,
                      duration: expectedLastStepDuration,
                    };
                  }
                }
                
                // Add a step for final answer generation time if we have final answer start time
                if (finalAnswerStartTime !== null && finalTime > finalAnswerStartTime) {
                  const answerGenTime = finalTime - finalAnswerStartTime;
                  if (answerGenTime > 50) { // Only add if significant (>50ms)
                    finalizedTimings.push({
                      text: "Generating final answer",
                      duration: answerGenTime,
                      startTime: finalAnswerStartTime,
                    });
                  }
                }
              } else {
                // If no timings to finalize, use the original step timings
                finalizedTimings = [...finalStepTimings];
              }
              
              // Set finalized timings immediately
              setStepTimings(finalizedTimings);
              
              // Reload messages to get the final assistant message
              const apiMessages = await chatApi.getMessages(conversationId);
              const formattedMessages: Message[] = apiMessages.map((msg, index) => {
                // Use storedVizqlQuery only for the last message (the one we just streamed)
                // All historical messages should use their own vizql_query from the API
                const isLastMessage = index === apiMessages.length - 1;
                const vizqlQuery = (isLastMessage && storedVizqlQuery) ? storedVizqlQuery : msg.vizql_query;
                return {
                  id: msg.id.toString(),
                  role: msg.role.toLowerCase() as MessageRole,
                  content: msg.content,
                  createdAt: new Date(msg.created_at),
                  modelUsed: msg.model_used,
                  feedback: msg.feedback,
                  feedbackText: msg.feedback_text,
                  totalTimeMs: msg.total_time_ms,
                  vizqlQuery: vizqlQuery,
                };
              });
              setMessages(formattedMessages);
              
              // Preserve reasoning steps, step timings, and total time
              if (reasoningStepsText && reasoningStepsText.trim()) {
                setLastReasoningSteps(reasoningStepsText);
                // Preserve finalized step timings (not the original unfinalized ones)
                if (finalizedTimings.length > 0) {
                  setStepTimings([...finalizedTimings]);
                }
                // Use the total_time_ms from the last assistant message (most recent)
                const lastAssistantMessage = formattedMessages
                  .filter(m => m.role === 'assistant')
                  .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime())[0];
                if (lastAssistantMessage?.totalTimeMs) {
                  setReasoningTotalTimeMs(lastAssistantMessage.totalTimeMs);
                }
              }
              
              setIsLoading(false);
              setIsStreaming(false);
              abortControllerRef.current = null;
            } catch (error) {
              console.error('Error completing stream:', error);
              setError(error instanceof Error ? error : new Error('Failed to complete stream'));
              setIsLoading(false);
              setIsStreaming(false);
              abortControllerRef.current = null;
            }
          },
          (error: Error) => {
            // Don't set error for abort errors
            if (error.name !== 'AbortError') {
              setError(error);
            }
            setIsLoading(false);
            setIsStreaming(false);
            abortControllerRef.current = null;
          },
          (structuredChunk: AgentMessageChunk) => {
            // Handle structured message chunks
            console.log('Received structured chunk:', structuredChunk);
            
            // Convert backend timestamp (seconds) to milliseconds, or use current time
            const chunkTimestamp = structuredChunk.timestamp 
              ? (structuredChunk.timestamp * 1000) // Convert seconds to milliseconds
              : Date.now();
            const elapsedTime = chunkTimestamp - startTime;
            
            if (structuredChunk.message_type === 'reasoning') {
              // Track when first reasoning step arrives
              if (firstReasoningStepTime === null) {
                firstReasoningStepTime = elapsedTime;
              }
              
              // Handle reasoning step - use step_index to uniquely identify steps
              // Multiple steps can come from the same node (e.g., multiple tool calls)
              const stepText = typeof structuredChunk.content.data === 'string' 
                ? structuredChunk.content.data 
                : JSON.stringify(structuredChunk.content.data);
              const nodeName = structuredChunk.step_name || 'unknown';
              const stepIndex = structuredChunk.step_index ?? finalStepTimings.length; // Use provided index or fallback to length
              
              // Use node name to get human-readable step name
              const stepDisplayName = nodeNameMap[nodeName] || nodeName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
              
              // Extract metadata (tool calls, tokens) from the chunk
              const stepMetadata = structuredChunk.metadata || {};
              const toolCalls = stepMetadata.tool_calls || [];
              const tokens = stepMetadata.tokens || null;
              
              reasoningStepsText += (reasoningStepsText ? ' ' : '') + stepText;
              
              // CRITICAL: The timestamp represents when the step COMPLETED, not when it started
              // We need to calculate the step's start time and duration correctly
              
              // Check if this step already exists by step_index (not just node name)
              const existingStepIndex = finalStepTimings.findIndex(
                t => t.stepIndex === stepIndex
              );
              
              if (existingStepIndex >= 0) {
                // Step already exists - update its completion time and duration
                const existingStep = finalStepTimings[existingStepIndex];
                // Duration = completion time - start time
                const stepDuration = elapsedTime - existingStep.startTime;
                finalStepTimings[existingStepIndex] = {
                  ...existingStep,
                  duration: Math.max(50, stepDuration),
                  toolCalls: toolCalls.length > 0 ? toolCalls : existingStep.toolCalls,
                  tokens: tokens ? {
                    prompt: tokens.prompt,
                    completion: tokens.completion,
                    total: tokens.total
                  } : existingStep.tokens,
                };
              } else {
                // New step - calculate when it started and its duration
                let stepStartTime: number;
                let stepDuration: number;
                
                if (finalStepTimings.length > 0) {
                  // This step started when the previous step completed
                  // The timestamp (elapsedTime) represents when THIS step completed
                  // So the previous step completed at elapsedTime (when this step started)
                  const previousStep = finalStepTimings[finalStepTimings.length - 1];
                  
                  // If previous step doesn't have a duration yet, calculate it now
                  // Duration = time from previous step's start to when current step arrived (= previous completion)
                  if (previousStep.duration === 0 || previousStep.duration < 50) {
                    previousStep.duration = Math.max(50, elapsedTime - previousStep.startTime);
                    finalStepTimings[finalStepTimings.length - 1] = previousStep;
                  }
                  
                  // Current step started when previous step completed
                  const previousCompletionTime = previousStep.startTime + previousStep.duration;
                  stepStartTime = previousCompletionTime;
                  stepDuration = 0; // Will be calculated when next step arrives or on finalization
                } else {
                  // First step - started when streaming began
                  stepStartTime = 0;
                  stepDuration = elapsedTime - stepStartTime;
                }
                
                // Add new step with calculated start time and duration
                // Don't enforce minimum duration here - it will be calculated when next step arrives
                finalStepTimings.push({
                  text: stepDisplayName,
                  duration: stepDuration,
                  startTime: stepStartTime,
                  nodeName: nodeName,
                  stepIndex: stepIndex,
                  toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
                  tokens: tokens ? {
                    prompt: tokens.prompt,
                    completion: tokens.completion,
                    total: tokens.total
                  } : undefined,
                });
              }
              
              reasoningStepIndex++;
              
              // Update reasoning steps state immediately so timings display as steps complete
              setLastReasoningSteps(reasoningStepsText);
              setStepTimings([...finalStepTimings]);
            } else if (structuredChunk.message_type === 'final_answer') {
              // Track when final answer starts (to account for answer generation time)
              if (finalAnswerStartTime === null) {
                finalAnswerStartTime = elapsedTime;
                
                // Finalize the last reasoning step's duration when final answer arrives
                if (finalStepTimings.length > 0) {
                  const lastStep = finalStepTimings[finalStepTimings.length - 1];
                  // Calculate when the last step completed
                  const lastStepCompletionTime = lastStep.startTime + (lastStep.duration || 0);
                  
                  // If the last step's duration is 0 or less than expected, update it
                  // Duration = final answer start time - step start time
                  const expectedDuration = elapsedTime - lastStep.startTime;
                  if (lastStep.duration === 0 || lastStep.duration < expectedDuration) {
                    finalStepTimings[finalStepTimings.length - 1] = {
                      ...lastStep,
                      duration: Math.max(50, expectedDuration),
                    };
                  }
                }
              }
              
              // Handle final answer - only show this in message bubble
              const answerText = typeof structuredChunk.content.data === 'string' 
                ? structuredChunk.content.data 
                : JSON.stringify(structuredChunk.content.data);
              
              finalAnswerText += answerText;
              
              // Update streaming content (only final answer, no reasoning steps)
              setStreamingContent(finalAnswerText);
            } else if (structuredChunk.message_type === 'error') {
              // Handle error
              const errorText = typeof structuredChunk.content.data === 'string' 
                ? structuredChunk.content.data 
                : JSON.stringify(structuredChunk.content.data);
              setError(new Error(errorText));
            } else if (structuredChunk.message_type === 'metadata') {
              // Handle metadata (e.g., vizql_query)
              const metadata = typeof structuredChunk.content.data === 'object' 
                ? structuredChunk.content.data 
                : (typeof structuredChunk.content.data === 'string' 
                  ? JSON.parse(structuredChunk.content.data) 
                  : {});
              if (metadata.vizql_query) {
                // Store vizql_query to be added to the message when streaming completes
                storedVizqlQuery = metadata.vizql_query;
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastMessage = updated[updated.length - 1];
                  if (lastMessage && lastMessage.role === 'assistant') {
                    updated[updated.length - 1] = {
                      ...lastMessage,
                      vizqlQuery: metadata.vizql_query,
                    };
                  }
                  return updated;
                });
                
                // Automatically load the query into the editor if onLoadQuery handler is available
                if (onLoadQuery && metadata.vizql_query) {
                  console.log('Auto-loading query into editor:', metadata.vizql_query);
                  // Extract datasource ID from query
                  const datasourceId = metadata.vizql_query?.datasource?.datasourceLuid;
                  if (datasourceId) {
                    console.log('Calling onLoadQuery with datasourceId:', datasourceId);
                    onLoadQuery(datasourceId, metadata.vizql_query);
                  } else {
                    console.warn('No datasourceId found in vizql_query metadata');
                  }
                }
              }
            }
          },
          abortController.signal
        );
        // Clear abort controller ref after successful completion
        abortControllerRef.current = null;
      } catch (error) {
        // Don't treat abort errors as real errors
        if (error instanceof Error && error.name === 'AbortError') {
          console.log('Message send cancelled by user');
          // Cleanup already handled by handleCancelMessage
          return;
        }
        console.error('Failed to send message:', error);
        setError(error instanceof Error ? error : new Error('Failed to send message'));
        setIsStreaming(false);
        setStreamingContent('');
        setIsLoading(false);
        abortControllerRef.current = null;
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
            feedback: msg.feedback,
            feedbackText: msg.feedback_text,
            totalTimeMs: msg.total_time_ms,
            vizqlQuery: msg.vizql_query,
          }));
          setMessages(formattedMessages);
        })
        .catch((error) => {
          setError(error instanceof Error ? error : new Error('Failed to reload messages'));
        });
    }
  }, [conversationId]);

  // Display streaming content
  // With structured messages, streamingContent only contains final_answer (no reasoning steps)
  // Reasoning steps are handled separately via lastReasoningSteps state
  const displayMessages = useMemo(() => {
    const baseMessages = messages;
    
    if (isStreaming && (streamingContent || isLoading)) {
      return [
        ...baseMessages,
        {
          id: 'streaming',
          role: 'assistant' as MessageRole,
          content: streamingContent || '...',
          createdAt: new Date(),
        },
      ];
    }
    
    return baseMessages;
  }, [messages, isStreaming, streamingContent, isLoading]);

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
            onFeedbackChange={(messageId, feedback, feedbackText) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === messageId ? { ...msg, feedback, feedbackText } : msg
                )
              );
            }}
            onLoadQuery={onLoadQuery}
            editable={true}
            streamingMessageId={isStreaming ? 'streaming' : undefined}
          />
        )}
      </div>
      {lastReasoningSteps && (
        <div className="px-2 sm:px-4 pt-2 sm:pt-4 mb-2">
          <ReasoningSteps 
            reasoningSteps={lastReasoningSteps} 
            stepTimings={stepTimings}
            isReasoningActive={isStreaming}
            streamStartTime={streamStartTime}
            totalTimeMs={reasoningTotalTimeMs}
          />
        </div>
      )}
      <div className="p-2 sm:p-4 border-t space-y-2">
        <MessageInput
          onSend={handleSendMessage}
          onCancel={isStreaming ? handleCancelMessage : undefined}
          disabled={isLoading || !conversationId}
        />
        <div className="flex gap-4 pt-1">
          {onAgentTypeChange && (
            <div className="flex-1">
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                Agent Type
              </label>
              <AgentSelector
                value={agentType}
                onValueChange={onAgentTypeChange}
              />
            </div>
          )}
          {onRemoveContext && (
            <div className="flex-1">
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                Context {context && context.length > 0 && `(${context.length})`}
              </label>
              <div className="max-h-32 overflow-y-auto">
                <ContextManager objects={context || []} onRemove={onRemoveContext} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
