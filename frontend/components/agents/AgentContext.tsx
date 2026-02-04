'use client';

import { createContext, useContext } from 'react';
import type { TableauDatasource } from '@/types';

interface AgentContextType {
  selectedDatasource: TableauDatasource | null;
  setSelectedDatasource: (ds: TableauDatasource | null) => void;
  selectedViews: string[];
  setSelectedViews: (views: string[]) => void;
}

export const AgentContext = createContext<AgentContextType | undefined>(undefined);

export function useAgentContext() {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgentContext must be used within AgentDashboard');
  }
  return context;
}
