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

export function ReasoningSteps({ reasoningSteps, stepTimings, className, isReasoningActive = false, streamStartTime, totalTimeMs }: ReasoningStepsProps) {
  const [isExpanded, setIsExpanded] = useState(isReasoningActive);
  const prevIsReasoningActiveRef = useRef(isReasoningActive);
  const [currentStepElapsed, setCurrentStepElapsed] = useState<number>(0);
  
  // Update expansion state when reasoning becomes active or inactive
  useEffect(() => {
    const prevIsReasoningActive = prevIsReasoningActiveRef.current;
    
    // Only auto-toggle when the state actually changes
    if (isReasoningActive && !prevIsReasoningActive) {
      // Reasoning just became active - expand
      setIsExpanded(true);
    } else if (!isReasoningActive && prevIsReasoningActive) {
      // Reasoning just became inactive (final answer returned) - collapse
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

  // Calculate total time - use totalTimeMs from message if available (more accurate),
  // otherwise sum step durations
  const totalTime = useMemo(() => {
    if (totalTimeMs !== null && totalTimeMs !== undefined) {
      // Use the actual total time from the message (includes all processing time)
      return totalTimeMs;
    }
    // Fallback to summing step durations
    return organizedSteps.reduce((sum, step) => sum + (step.duration || 0), 0);
  }, [organizedSteps, totalTimeMs]);

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
          {stepTimings && stepTimings.length > 0 && totalTime > 0 && (
            <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
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
          <ScrollArea className="max-h-64">
            <div className="p-3 space-y-2">
              {organizedSteps.map((step, index) => (
                <div
                  key={index}
                  className="flex gap-2 items-start text-xs text-gray-700 dark:text-gray-300"
                >
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
                        <div className="flex-shrink-0 text-xs text-gray-500 dark:text-gray-400 font-mono whitespace-nowrap">
                          {step.duration > 0 
                            ? formatDuration(step.duration) 
                            : (isReasoningActive && index === organizedSteps.length - 1 && currentStepElapsed > 0)
                              ? formatDuration(currentStepElapsed)
                              : '—'}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {stepTimings && stepTimings.length > 0 && totalTime > 0 && (
                <div className="pt-2 mt-2 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      Total Time:
                    </span>
                    <span className="text-gray-500 dark:text-gray-400 font-mono">
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
