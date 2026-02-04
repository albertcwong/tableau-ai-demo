'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { VizQLPanel } from '@/components/agents/VizQLPanel';
import { SummaryPanel } from '@/components/agents/SummaryPanel';
import { ChatInterface } from '@/components/chat';
import { AgentContext } from '@/components/agents/AgentContext';
import type { AgentType, TableauDatasource } from '@/types';
import { cn } from '@/lib/utils';

export default function AgentsPage() {
  const [activeAgent, setActiveAgent] = useState<AgentType>('analyst');
  const [selectedDatasource, setSelectedDatasource] = useState<TableauDatasource | null>(null);
  const [selectedViews, setSelectedViews] = useState<string[]>([]);

  const agents: Array<{ id: AgentType; label: string; description: string }> = [
    { id: 'analyst', label: 'Analyst Agent', description: 'General Tableau queries and exploration' },
    { id: 'vizql', label: 'VizQL Agent', description: 'VizQL query construction and execution' },
    { id: 'summary', label: 'Summary Agent', description: 'Multi-view export and summarization' },
  ];

  return (
    <AgentContext.Provider
      value={{
        selectedDatasource,
        setSelectedDatasource,
        selectedViews,
        setSelectedViews,
      }}
    >
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="container mx-auto px-4 py-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Multi-Agent Dashboard
            </h1>
            <div className="flex gap-2">
              <Link href="/">
                <Button variant="outline">Component Testing</Button>
              </Link>
              <Link href="/chat-test">
                <Button variant="outline">Chat Test</Button>
              </Link>
              <Link href="/mcp-test">
                <Button variant="outline">MCP Test</Button>
              </Link>
            </div>
          </div>

          {/* Agent Selector */}
          <div className="mb-6">
            <div className="flex flex-wrap gap-2">
              {agents.map((agent) => (
                <Button
                  key={agent.id}
                  onClick={() => setActiveAgent(agent.id)}
                  variant={activeAgent === agent.id ? 'default' : 'outline'}
                  className={cn(
                    'transition-colors',
                    activeAgent === agent.id &&
                      'bg-blue-600 hover:bg-blue-700 text-white'
                  )}
                >
                  {agent.label}
                </Button>
              ))}
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
              {agents.find((a) => a.id === activeAgent)?.description}
            </p>
          </div>

          {/* Active Agent Panel */}
          <Card className="p-6">
            {activeAgent === 'analyst' && (
              <div data-testid="analyst-panel">
                <h2 className="text-xl font-semibold mb-4">Analyst Agent</h2>
                <ChatInterface />
              </div>
            )}

            {activeAgent === 'vizql' && (
              <div data-testid="vizql-panel">
                <VizQLPanel />
              </div>
            )}

            {activeAgent === 'summary' && (
              <div data-testid="summary-panel">
                <SummaryPanel />
              </div>
            )}
          </Card>
        </div>
      </div>
    </AgentContext.Provider>
  );
}
