'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/components/auth/AuthContext';
import { AgentContext } from '@/components/agents/AgentContext';
import { ThreePanelLayout } from '@/components/explorer';
import { AgentPanel } from '@/components/agent-panel';
import { MessageSquare, GripVertical, Home as HomeIcon, Settings } from 'lucide-react';
import type { TableauDatasource, ChatContextObject } from '@/types';
import { cn } from '@/lib/utils';

function HomeContent() {
  const router = useRouter();
  const pathname = usePathname();
  const { logout, user, loading, isAdmin } = useAuth();
  const [selectedDatasource, setSelectedDatasource] = useState<TableauDatasource | null>(null);
  const [selectedViews, setSelectedViews] = useState<string[]>([]);
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(false);
  const [contextObjects, setContextObjects] = useState<ChatContextObject[]>([]);
  const [agentPanelWidth, setAgentPanelWidth] = useState(384);
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null);
  const addToContextRef = useRef<((objectId: string, objectType: 'datasource' | 'view', objectName?: string) => void) | null>(null);
  const loadQueryRef = useRef<((datasourceId: string, query: Record<string, any>) => void) | null>(null);

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 dark:border-gray-100 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  const handleAddToContext = (objectId: string, objectType: 'datasource' | 'view', objectName?: string) => {
    if (addToContextRef.current) {
      addToContextRef.current(objectId, objectType, objectName);
    } else {
      console.warn('AgentPanel not ready to add context.');
    }
  };

  const handleContextChange = useCallback((context: ChatContextObject[]) => {
    setContextObjects(context);
  }, []);

  const handleActiveThreadChange = useCallback((threadId: number | null) => {
    setActiveThreadId(threadId);
  }, []);

  return (
    <AgentContext.Provider
      value={{
        selectedDatasource,
        setSelectedDatasource,
        selectedViews,
        setSelectedViews,
      }}
    >
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
        {/* Header */}
        <header className="shrink-0 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {/* Logo placeholder - blank for now */}
                <div className="w-8 h-8"></div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  Tableau AI
                </h1>
              </div>
              <div className="flex items-center gap-2">
                {/* Navigation Tabs */}
                <div className="flex items-center gap-1 mr-4">
                  <Link href="/">
                    <Button
                      variant={pathname === '/' ? 'default' : 'ghost'}
                      size="sm"
                      className="flex items-center gap-2"
                    >
                      <HomeIcon className="h-4 w-4" />
                      Home
                    </Button>
                  </Link>
                  {isAdmin && (
                    <Link href="/admin">
                      <Button
                        variant={pathname === '/admin' ? 'default' : 'ghost'}
                        size="sm"
                        className="flex items-center gap-2"
                      >
                        <Settings className="h-4 w-4" />
                        Admin Console
                      </Button>
                    </Link>
                  )}
                </div>
                {user && (
                  <span className="text-sm text-gray-600 dark:text-gray-400 mr-2">
                    {user.username} ({user.role})
                  </span>
                )}
                <Button variant="outline" size="sm" onClick={handleLogout}>
                  {user ? 'Logout' : 'Login'}
                </Button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <div className="flex-1 overflow-hidden flex min-h-0">
          {/* Main Content */}
          <div 
            className="flex-1 transition-all duration-300 overflow-hidden min-h-0"
            style={{ marginRight: isAgentPanelOpen ? `${agentPanelWidth}px` : '0' }}
          >
            <ThreePanelLayout 
              onAddToContext={handleAddToContext}
              contextObjects={contextObjects}
              onLoadQueryRef={loadQueryRef}
              onDatasourceSelect={setSelectedDatasource}
              activeThreadId={activeThreadId}
            />
          </div>

          {/* Assistant Panel */}
          <AgentPanel
            isOpen={isAgentPanelOpen}
            onClose={() => setIsAgentPanelOpen(false)}
            onAddToContextRef={(handler) => {
              addToContextRef.current = handler;
            }}
            onContextChange={handleContextChange}
            onWidthChange={setAgentPanelWidth}
            selectedDatasource={selectedDatasource ? { id: selectedDatasource.id, name: selectedDatasource.name } : null}
            onActiveThreadChange={handleActiveThreadChange}
            onLoadQuery={(datasourceId, query) => {
              console.log('page.tsx onLoadQuery called:', { datasourceId, query, loadQueryRef: loadQueryRef.current });
              // Use the ref to call ThreePanelLayout's load query handler
              if (loadQueryRef.current) {
                console.log('Calling loadQueryRef.current');
                loadQueryRef.current(datasourceId, query);
              } else {
                console.warn('loadQueryRef.current is null');
              }
            }}
          />

          {/* Toggle Button */}
          {!isAgentPanelOpen && (
            <Button
              onClick={() => setIsAgentPanelOpen(true)}
              variant="default"
              size="sm"
              className="fixed right-4 bottom-4 z-40 shadow-lg"
            >
              <MessageSquare className="h-4 w-4 mr-2" />
              Open Assistant
            </Button>
          )}
        </div>
      </div>
    </AgentContext.Provider>
  );
}

export default function Home() {
  return (
    <ProtectedRoute>
      <HomeContent />
    </ProtectedRoute>
  );
}
