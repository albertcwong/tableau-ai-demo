'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export type AgentType = 'vizql' | 'summary' | 'general';

interface AgentSelectorProps {
  value: AgentType;
  onValueChange: (value: AgentType) => void;
  className?: string;
}

const agentLabels: Record<AgentType, string> = {
  vizql: 'VizQL Agent',
  summary: 'Summary Agent',
  general: 'General Agent',
};

const agentDescriptions: Record<AgentType, string> = {
  vizql: 'VizQL query construction and execution',
  summary: 'Multi-view export and summarization',
  general: 'General Tableau queries and exploration',
};

export function AgentSelector({ value, onValueChange, className }: AgentSelectorProps) {
  return (
    <div className={className}>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select agent...">
            {agentLabels[value]}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="general">
            <div className="flex flex-col py-1">
              <span className="font-medium">General Agent</span>
              <span className="text-xs text-muted-foreground">General Tableau queries and exploration</span>
            </div>
          </SelectItem>
          <SelectItem value="vizql">
            <div className="flex flex-col py-1">
              <span className="font-medium">VizQL Agent</span>
              <span className="text-xs text-muted-foreground">VizQL query construction and execution</span>
            </div>
          </SelectItem>
          <SelectItem value="summary">
            <div className="flex flex-col py-1">
              <span className="font-medium">Summary Agent</span>
              <span className="text-xs text-muted-foreground">Multi-view export and summarization</span>
            </div>
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
