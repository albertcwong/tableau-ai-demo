'use client';

import { Select } from '@/components/ui/select';

export type AgentType = 'vizql' | 'summary' | 'general';

interface AgentSelectorProps {
  value: AgentType;
  onValueChange: (value: AgentType) => void;
}

export function AgentSelector({ value, onValueChange }: AgentSelectorProps) {
  return (
    <Select
      value={value}
      onChange={(e) => onValueChange(e.target.value as AgentType)}
      className="w-full"
    >
      <option value="vizql">VizQL Agent</option>
      <option value="summary">Summary Agent</option>
      <option value="general">General Agent</option>
    </Select>
  );
}
