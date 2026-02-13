'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import { ChevronDown, ChevronUp, Brain, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

interface StepWithTiming {
  text: string;
  duration: number; // Duration in milliseconds
  startTime: number; // Start time relative to stream start
  nodeName?: string; // LangGraph node name (e.g., "data_fetcher", "analyzer")
  toolCalls?: string[]; // Tool calls made in this step
  tokens?: { prompt?: number; completion?: number; total?: number }; // Token usage
  queryDraft?: Record<string, any>; // VizQL query draft for build_query steps
  toolResultSummary?: string; // Optional summary of tool results
}

interface ReasoningStepsProps {
  reasoningSteps: string;
  stepTimings?: StepWithTiming[];
  className?: string;
  isReasoningActive?: boolean; // When true, expand by default; when false, collapse
  streamStartTime?: number | null; // When streaming started (for calculating elapsed time)
  totalTimeMs?: number | null; // Total time from message (includes all processing time)
}

function parseReasoningSteps(steps: string): string[] {
  if (!steps || steps.trim().length === 0) {
    return [];
  }

  // Common action verbs that typically start a new reasoning step
  const actionVerbs = [
    'Parsed', 'Fetched', 'Built', 'Validation', 'Query', 'Retrieved', 
    'Analyzed', 'Generated', 'Executed', 'Validated', 'Processed',
    'Identified', 'Selected', 'Created', 'Updated', 'Checked', 'The'
  ];

  // Strategy 1: Split by periods/question marks/exclamation followed by space and capital letter
  let parts = steps.split(/(?<=[.!?])\s+(?=[A-Z])/);
  
  // Strategy 2: If that didn't work, split by space followed by capital letter (word boundary)
  // But preserve sentences that end with punctuation
  if (parts.length <= 1) {
    // Split by capital letters that start words, but keep sentences together
    parts = steps.split(/\s+(?=[A-Z][a-z])/);
  }

  const refined: string[] = [];
  
  for (let part of parts) {
    part = part.trim();
    if (!part) continue;
    
    // Check if this part contains multiple action verbs (indicating multiple steps)
    const words = part.split(/\s+/);
    const actionIndices: number[] = [];
    
    words.forEach((word, index) => {
      if (actionVerbs.some(action => word === action || word.startsWith(action))) {
        actionIndices.push(index);
      }
    });
    
    // If we found multiple action verbs, split at those points
    if (actionIndices.length > 1) {
      for (let i = 0; i < actionIndices.length; i++) {
        const start = actionIndices[i];
        const end = actionIndices[i + 1] || words.length;
        const step = words.slice(start, end).join(' ').trim();
        if (step) {
          refined.push(step);
        }
      }
    } else {
      refined.push(part);
    }
  }

  // Strategy 3: If still only one item, split directly by action verbs
  if (refined.length <= 1) {
    const words = steps.split(/\s+/);
    const stepsList: string[] = [];
    let currentStep = '';
    
    for (const word of words) {
      const isActionVerb = actionVerbs.some(action => 
        word === action || word.startsWith(action)
      );
      
      // If we hit an action verb and have accumulated content, save current step
      if (isActionVerb && currentStep.trim()) {
        stepsList.push(currentStep.trim());
        currentStep = word;
      } else {
        currentStep += (currentStep ? ' ' : '') + word;
      }
    }
    
    if (currentStep.trim()) {
      stepsList.push(currentStep.trim());
    }
    
    return stepsList.length > 1 ? stepsList : [steps];
  }

  return refined.filter(step => step.trim().length > 0);
}

function formatDuration(ms: number): string {
  // Always display in seconds with up to 2 decimal places
  const seconds = (ms / 1000).toFixed(2);
  return `${seconds}s`;
}

interface StreamingTextAreaProps {
  content: string;
  isActive: boolean;
  label: string;
  className?: string;
}

const LINE_HEIGHT_REM = 1.5;
const MAX_LINES = 7;

function StreamingTextArea({ content, isActive, label, className }: StreamingTextAreaProps) {
  const [displayedLength, setDisplayedLength] = useState(0);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const prevContentRef = useRef(content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Reset displayed length when content changes
  useEffect(() => {
    if (content !== prevContentRef.current) {
      setDisplayedLength(0);
      setIsCollapsed(false);
      prevContentRef.current = content;
    }
  }, [content]);

  // Streaming effect: animate text appearing when active
  useEffect(() => {
    if (!content || content.length === 0) {
      setDisplayedLength(0);
      return;
    }

    if (isActive && displayedLength < content.length) {
      const step = Math.max(1, Math.ceil(content.length / 50)); // ~50 frames for full content
      const interval = setInterval(() => {
        setDisplayedLength((prev) => {
          const next = Math.min(prev + step, content.length);
          return next;
        });
      }, 30); // ~30ms per frame = ~1.5s for full content
      return () => clearInterval(interval);
    } else if (!isActive && displayedLength < content.length) {
      // If becomes inactive before streaming completes, show all immediately
      setDisplayedLength(content.length);
    }
  }, [content, isActive, displayedLength]);

  // Auto-grow textarea to fit content, max 7 lines
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const maxHeight = LINE_HEIGHT_REM * MAX_LINES * 16; // rem to px (16px base)
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, [displayedLength, content]);

  if (!content || content.length === 0) {
    return null;
  }

  const displayedText = content.slice(0, displayedLength);

  return (
    <div className={cn('mt-1 transition-all duration-300', className)}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-semibold text-gray-600 dark:text-gray-400">{label}</span>
        {!isActive && displayedLength >= content.length && (
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="text-[10px] text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
          >
            {isCollapsed ? 'Show' : 'Hide'}
          </button>
        )}
      </div>
      <div
        className={cn(
          'transition-all duration-300 overflow-hidden',
          isCollapsed ? 'max-h-0' : 'max-h-[10.5rem]'
        )}
      >
        <textarea
          ref={textareaRef}
          readOnly
          rows={1}
          value={displayedText}
          className={cn(
            'w-full resize-none min-h-[1.5rem] text-[10px] font-mono bg-gray-50 dark:bg-gray-800',
            'border border-gray-200 dark:border-gray-700 rounded',
            'px-2 py-1 text-gray-800 dark:text-gray-200',
            'overflow-y-auto',
            className
          )}
        />
        {isActive && displayedLength < content.length && (
          <span className="inline-block ml-1 animate-pulse text-gray-400">▋</span>
        )}
      </div>
    </div>
  );
}

interface ReasoningStepItemProps {
  step: { text: string; duration: number; startTime: number };
  stepTiming?: StepWithTiming;
  index: number;
  isReasoningActive: boolean;
  currentStepElapsed: number;
  stepTimings?: StepWithTiming[];
}

function ReasoningStepItem({ step, stepTiming, index, isReasoningActive, currentStepElapsed, stepTimings }: ReasoningStepItemProps) {
  const isBuildQueryStep = stepTiming?.nodeName === 'build_query' || stepTiming?.nodeName === 'query_builder';
  const isCurrentStep = isReasoningActive && index === (stepTimings?.length || 0) - 1;
  const hasToolCalls = stepTiming?.toolCalls && stepTiming.toolCalls.length > 0;
  const hasQueryDraft = stepTiming?.queryDraft;
  const hasToolResultSummary = stepTiming?.toolResultSummary;
  
  // Build tool summary text
  const toolSummaryText = useMemo(() => {
    if (hasToolResultSummary) {
      return stepTiming.toolResultSummary;
    }
    if (hasToolCalls && stepTiming?.toolCalls) {
      return `Tools used: ${stepTiming.toolCalls.join(', ')}`;
    }
    return '';
  }, [hasToolCalls, hasToolResultSummary, stepTiming?.toolCalls, stepTiming?.toolResultSummary]);

  // Build VizQL query text
  const queryText = useMemo(() => {
    if (hasQueryDraft) {
      return JSON.stringify(stepTiming.queryDraft, null, 2);
    }
    return '';
  }, [hasQueryDraft, stepTiming?.queryDraft]);
  
  return (
    <div className="flex gap-2 items-start text-xs text-gray-700 dark:text-gray-300">
      <div className="flex-shrink-0 mt-0.5">
        <CheckCircle2 className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
      </div>
      <div className="flex-1 break-words">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <span className="font-medium text-gray-900 dark:text-gray-100">
              Step {index + 1}:
            </span>{' '}
            <span>{step.text.trim()}</span>
          </div>
          {stepTimings && stepTimings.length > 0 && (
            <div className={cn(
              'flex-shrink-0 text-xs font-mono whitespace-nowrap',
              (isReasoningActive && index === (stepTimings?.length || 0) - 1 && currentStepElapsed > 0)
                ? 'text-blue-800 dark:text-blue-200 font-bold'
                : 'text-gray-500 dark:text-gray-400'
            )}>
              {step.duration > 0 
                ? formatDuration(step.duration) 
                : (isReasoningActive && index === (stepTimings?.length || 0) - 1 && currentStepElapsed > 0)
                  ? formatDuration(currentStepElapsed)
                  : '—'}
            </div>
          )}
        </div>
        {(hasToolCalls || hasToolResultSummary || hasQueryDraft || stepTiming?.tokens) && (
          <div className="mt-1 pl-0 space-y-1">
            {stepTiming?.tokens && (
              <div className="text-[10px] text-gray-600 dark:text-gray-400 font-mono">
                <span className="font-semibold">Tokens:</span>{' '}
                {stepTiming.tokens.prompt && `${stepTiming.tokens.prompt} in`}
                {stepTiming.tokens.prompt && stepTiming.tokens.completion && ' / '}
                {stepTiming.tokens.completion && `${stepTiming.tokens.completion} out`}
                {stepTiming.tokens.total && ` (${stepTiming.tokens.total} total)`}
              </div>
            )}
            {toolSummaryText && (
              <StreamingTextArea
                content={toolSummaryText}
                isActive={isCurrentStep && isReasoningActive}
                label="Tool Summary"
              />
            )}
            {queryText && (
              <StreamingTextArea
                content={queryText}
                isActive={isCurrentStep && isReasoningActive}
                label="VizQL Query"
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function ReasoningSteps({ reasoningSteps, stepTimings, className, isReasoningActive = false, streamStartTime, totalTimeMs }: ReasoningStepsProps) {
  const [isExpanded, setIsExpanded] = useState(isReasoningActive);
  const prevIsReasoningActiveRef = useRef(isReasoningActive);
  const [currentStepElapsed, setCurrentStepElapsed] = useState<number>(0);
  
  // Update expansion state when reasoning becomes active or inactive
  useEffect(() => {
    const prevIsReasoningActive = prevIsReasoningActiveRef.current;
    
    if (isReasoningActive && !prevIsReasoningActive) {
      setIsExpanded(true);
    } else if (!isReasoningActive && prevIsReasoningActive) {
      setIsExpanded(false);
    }
    prevIsReasoningActiveRef.current = isReasoningActive;
  }, [isReasoningActive]);
  
  // Track elapsed time for the current (last) step when reasoning is active
  useEffect(() => {
    if (!isReasoningActive || !stepTimings || stepTimings.length === 0 || !streamStartTime) {
      setCurrentStepElapsed(0);
      return;
    }
    
    const lastStep = stepTimings[stepTimings.length - 1];
    if (lastStep.duration > 0) {
      // Step already has a duration, no need to track
      setCurrentStepElapsed(0);
      return;
    }
    
    // Calculate elapsed time since the last step started
    // startTime is relative to streamStartTime, so elapsed = current time - (streamStartTime + startTime)
    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = now - (streamStartTime + lastStep.startTime);
      setCurrentStepElapsed(Math.max(0, elapsed));
    }, 100); // Update every 100ms for smooth updates
    
    return () => clearInterval(interval);
  }, [isReasoningActive, stepTimings, streamStartTime]);

  // Track total elapsed time in real time when streaming
  const [liveTotalMs, setLiveTotalMs] = useState<number | null>(null);
  useEffect(() => {
    if (!isReasoningActive || !streamStartTime) {
      setLiveTotalMs(null);
      return;
    }
    const interval = setInterval(() => {
      setLiveTotalMs(Date.now() - streamStartTime);
    }, 100);
    return () => clearInterval(interval);
  }, [isReasoningActive, streamStartTime]);

  const organizedSteps = useMemo(() => {
    // If we have step timings with node names, use them directly (one step per node)
    // This aligns with LangGraph nodes and avoids text parsing issues
    if (stepTimings && stepTimings.length > 0 && stepTimings.some(s => s.nodeName)) {
      // Use step timings directly - they already represent one step per LangGraph node
      return stepTimings.map(timing => ({
        text: timing.text,
        duration: timing.duration || 0,
        startTime: timing.startTime || 0,
      }));
    }
    
    // Fallback: parse reasoning steps text (for backward compatibility or when node names aren't available)
    const steps = parseReasoningSteps(reasoningSteps);
    
    // If we have step timings, try to match them with parsed steps
    if (stepTimings && stepTimings.length > 0) {
      // Match timing data with parsed steps by finding the best match
      const matchedSteps = steps.map((parsedStep, index) => {
        // Try to find matching timing data
        // First try exact match (case-insensitive, trimmed)
        const parsedNormalized = parsedStep.toLowerCase().trim();
        let timing = stepTimings.find(t => 
          t.text.toLowerCase().trim() === parsedNormalized
        );
        
        // If no exact match, try to find by index
        if (!timing && stepTimings[index]) {
          timing = stepTimings[index];
        }
        
        // If still no match, try partial match (step text contains timing text or vice versa)
        if (!timing) {
          timing = stepTimings.find(t => {
            const tNormalized = t.text.toLowerCase().trim();
            return parsedNormalized.includes(tNormalized) || 
                   tNormalized.includes(parsedNormalized) ||
                   parsedNormalized.startsWith(tNormalized.split(' ')[0]) ||
                   tNormalized.startsWith(parsedNormalized.split(' ')[0]);
          });
        }
        
        return {
          text: parsedStep,
          duration: timing?.duration || 0,
          startTime: timing?.startTime || 0,
        };
      });
      
      // Debug logging
      if (matchedSteps.some(s => s.duration > 0)) {
        console.log('Step timings matched:', matchedSteps);
      }
      
      return matchedSteps;
    }
    
    // Fallback: return steps without timing
    return steps.map((text, index) => ({
      text,
      duration: 0,
      startTime: 0,
    }));
  }, [reasoningSteps, stepTimings]);

  if (!reasoningSteps || reasoningSteps.trim().length === 0 || organizedSteps.length === 0) {
    return null;
  }

  // Calculate total time - when streaming use live elapsed; when done use totalTimeMs or sum of steps
  const totalTime = useMemo(() => {
    if (isReasoningActive && liveTotalMs !== null) {
      return liveTotalMs;
    }
    if (totalTimeMs !== null && totalTimeMs !== undefined) {
      return totalTimeMs;
    }
    return organizedSteps.reduce((sum, step) => sum + (step.duration || 0), 0);
  }, [organizedSteps, totalTimeMs, isReasoningActive, liveTotalMs]);

  return (
    <Card className={cn('border-gray-200 dark:border-gray-800', className)}>
      <Button
        variant="ghost"
        className="w-full justify-between p-3 h-auto hover:bg-gray-50 dark:hover:bg-gray-800"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Reasoning Steps ({organizedSteps.length})
          </span>
          {((stepTimings && stepTimings.length > 0) || (isReasoningActive && liveTotalMs)) && totalTime > 0 && (
            <span className={cn(
              'text-xs font-mono',
              isReasoningActive && liveTotalMs !== null ? 'text-blue-800 dark:text-blue-200 font-bold' : 'text-gray-500 dark:text-gray-400'
            )}>
              • {formatDuration(totalTime)}
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-gray-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-500" />
        )}
      </Button>
      {isExpanded && (
        <div className="border-t border-gray-200 dark:border-gray-800">
          <ScrollArea className="max-h-[50vh]">
            <div className="p-3 space-y-2">
              {organizedSteps.map((step, index) => {
                const stepTiming = stepTimings && stepTimings[index];
                return (
                  <ReasoningStepItem
                    key={index}
                    step={step}
                    stepTiming={stepTiming}
                    index={index}
                    isReasoningActive={isReasoningActive}
                    currentStepElapsed={currentStepElapsed}
                    stepTimings={stepTimings}
                  />
                );
              })}
              {(((stepTimings && stepTimings.length > 0) || (isReasoningActive && liveTotalMs)) && totalTime > 0) && (
                <div className="pt-2 mt-2 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      Total Time:
                    </span>
                    <span className={cn(
                      'font-mono',
                      isReasoningActive && liveTotalMs !== null ? 'text-blue-800 dark:text-blue-200 font-bold' : 'text-gray-500 dark:text-gray-400'
                    )}>
                      {formatDuration(totalTime)}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      )}
    </Card>
  );
}
