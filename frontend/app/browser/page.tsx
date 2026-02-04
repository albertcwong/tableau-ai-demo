'use client';

import { useState, useRef } from 'react';
import { ObjectExplorer } from '@/components/explorer';
import { AgentPanel } from '@/components/agent-panel';
import { Button } from '@/components/ui/button';
import { MessageSquare } from 'lucide-react';
import type { ChatContextObject } from '@/types';

export default function BrowserPage() {
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(false);
  const [contextObjects, setContextObjects] = useState<ChatContextObject[]>([]);
  const addToContextRef = useRef<((objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void) | null>(null);

  const handleAddToContext = (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => {
    // Call the AgentPanel's handler if it's available
    if (addToContextRef.current) {
      addToContextRef.current(objectId, objectType, objectName);
    } else {
      console.warn('AgentPanel not ready to add context. Make sure the Agent Assistant panel is open.');
    }
  };

  const handleContextChange = (context: ChatContextObject[]) => {
    setContextObjects(context);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="flex h-screen">
        {/* Main Content Area */}
        <div className={`flex-1 transition-all duration-300 ${isAgentPanelOpen ? 'mr-96' : ''}`}>
          <div className="h-full overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                Tableau Object Explorer
              </h1>
              <Button
                onClick={() => setIsAgentPanelOpen(!isAgentPanelOpen)}
                variant={isAgentPanelOpen ? 'default' : 'outline'}
              >
                <MessageSquare className="h-4 w-4 mr-2" />
                {isAgentPanelOpen ? 'Close' : 'Open'} Agent Assistant
              </Button>
            </div>
            
            <ObjectExplorer 
              onAddToContext={handleAddToContext}
              contextObjects={contextObjects}
            />
          </div>
        </div>

        {/* Agent Panel Sidebar */}
        <AgentPanel
          isOpen={isAgentPanelOpen}
          onClose={() => setIsAgentPanelOpen(false)}
          onAddToContextRef={(handler) => {
            addToContextRef.current = handler;
          }}
          onContextChange={handleContextChange}
        />
      </div>
    </div>
  );
}
