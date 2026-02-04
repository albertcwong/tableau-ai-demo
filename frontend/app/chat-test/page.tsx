'use client';

import { useState, useEffect } from 'react';
import { ChatInterface } from '@/components/chat';
import { MessageList, MessageInput, ModelSelector } from '@/components/chat';
import type { Message, MessageRole } from '@/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { gatewayApi } from '@/lib/api';

export default function ChatTestPage() {
  const [showFullInterface, setShowFullInterface] = useState(true);
  const [testMessages, setTestMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'user',
      content: 'Hello! This is a test message.',
      createdAt: new Date(),
    },
    {
      id: '2',
      role: 'assistant',
      content: 'Hi there! I\'m an AI assistant. Here\'s some **markdown** formatting:\n\n- Item 1\n- Item 2\n\nAnd here\'s some code:\n\n```python\ndef hello():\n    print("Hello, World!")\n```',
      createdAt: new Date(),
      modelUsed: 'gpt-4',
    },
    {
      id: '3',
      role: 'user',
      content: 'Can you show me a code example?',
      createdAt: new Date(),
    },
    {
      id: '4',
      role: 'assistant',
      content: 'Sure! Here\'s a JavaScript example:\n\n```javascript\nconst greet = (name) => {\n  return `Hello, ${name}!`;\n};\n\nconsole.log(greet("World"));\n```',
      createdAt: new Date(),
      modelUsed: 'gpt-4',
    },
  ]);
  const [selectedModel, setSelectedModel] = useState('gpt-4');
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [providers, setProviders] = useState<string[]>([]);
  const [providerModels, setProviderModels] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  const PROVIDER_LABELS: Record<string, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    vertex: 'Google Vertex AI',
    salesforce: 'Salesforce',
    apple: 'Apple Endor',
  };

  // Fetch providers on mount
  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const providerList = await gatewayApi.getProviders();
        setProviders(providerList);
        if (providerList.length > 0) {
          setSelectedProvider(providerList[0]);
          await fetchModelsForProvider(providerList[0]);
        }
      } catch (error) {
        console.error('Failed to fetch providers:', error);
      }
    };
    fetchProviders();
  }, []);

  // Fetch models when provider changes (cascading effect)
  const fetchModelsForProvider = async (provider: string) => {
    setIsLoadingModels(true);
    try {
      const models = await gatewayApi.getModels(provider);
      setProviderModels(models);
      // Auto-select first model if current selection not in new list
      if (models.length > 0 && !models.includes(selectedModel)) {
        setSelectedModel(models[0]);
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
      setProviderModels([]);
    } finally {
      setIsLoadingModels(false);
    }
  };

  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider);
    fetchModelsForProvider(provider);
  };

  const handleSendTestMessage = (content: string) => {
    const userMessage: Message = {
      id: `test-${Date.now()}`,
      role: 'user',
      content,
      createdAt: new Date(),
    };
    setTestMessages((prev) => [...prev, userMessage]);

    // Simulate AI response after a delay
    setTimeout(() => {
      const assistantMessage: Message = {
        id: `test-${Date.now() + 1}`,
        role: 'assistant',
        content: `You said: "${content}". This is a simulated response.`,
        createdAt: new Date(),
        modelUsed: selectedModel,
      };
      setTestMessages((prev) => [...prev, assistantMessage]);
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Chat Components Test Page</h1>
          <p className="text-muted-foreground">
            Test the chat interface components and their functionality
          </p>
        </div>

        <div className="mb-4 flex gap-2">
          <Button
            onClick={() => setShowFullInterface(!showFullInterface)}
            variant={showFullInterface ? 'default' : 'outline'}
          >
            {showFullInterface ? 'Show Individual Components' : 'Show Full Interface'}
          </Button>
        </div>

        {showFullInterface ? (
          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-4">Full Chat Interface</h2>
              <div className="h-[600px] border rounded-lg">
                <ChatInterface defaultModel="gpt-4" />
              </div>
            </Card>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* MessageList Component */}
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-4">MessageList Component</h2>
              <div className="h-[400px] border rounded-lg">
                <MessageList messages={testMessages} />
              </div>
            </Card>

            {/* MessageInput Component */}
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-4">MessageInput Component</h2>
              <div className="space-y-4">
                <MessageInput
                  onSend={handleSendTestMessage}
                  placeholder="Type a test message..."
                />
                <div className="text-sm text-muted-foreground">
                  <p>Try sending a message with markdown:</p>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    <li>**bold** text</li>
                    <li>*italic* text</li>
                    <li>`code` inline</li>
                    <li>```language code block```</li>
                  </ul>
                </div>
              </div>
            </Card>

            {/* Provider & Model Cascading Demo */}
            <Card className="p-6 lg:col-span-2">
              <h2 className="text-xl font-semibold mb-4">Provider & Model Cascading Demo</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="test-provider-select" className="text-sm font-medium mb-2 block">
                      Provider (Select to see cascading effect)
                    </Label>
                    <Select
                      id="test-provider-select"
                      value={selectedProvider || ''}
                      onChange={(e) => handleProviderChange(e.target.value)}
                      className="w-full"
                      disabled={providers.length === 0}
                    >
                      {providers.length === 0 ? (
                        <option>Loading providers...</option>
                      ) : (
                        providers.map((provider) => (
                          <option key={provider} value={provider}>
                            {PROVIDER_LABELS[provider] || provider}
                          </option>
                        ))
                      )}
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="test-model-select" className="text-sm font-medium mb-2 block">
                      Model (Updates based on provider)
                    </Label>
                    <Select
                      id="test-model-select"
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="w-full"
                      disabled={providerModels.length === 0 || isLoadingModels}
                    >
                      {isLoadingModels ? (
                        <option>Loading models...</option>
                      ) : providerModels.length === 0 ? (
                        <option>No models available</option>
                      ) : (
                        providerModels.map((model) => (
                          <option key={model} value={model}>
                            {model}
                          </option>
                        ))
                      )}
                    </Select>
                  </div>
                  <div className="p-3 bg-muted rounded-md text-sm">
                    <p className="font-medium mb-1">Current Selection:</p>
                    <p className="text-muted-foreground">
                      Provider: <strong>{selectedProvider ? PROVIDER_LABELS[selectedProvider] || selectedProvider : 'None'}</strong>
                    </p>
                    <p className="text-muted-foreground">
                      Model: <strong>{selectedModel}</strong>
                    </p>
                    <p className="text-muted-foreground mt-2">
                      Available models: <strong>{providerModels.length}</strong>
                    </p>
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold mb-2">How it works:</h3>
                    <ul className="text-sm text-muted-foreground space-y-2 list-disc list-inside">
                      <li>Select a provider from the dropdown</li>
                      <li>Model list automatically updates to show only models from that provider</li>
                      <li>If current model isn't in the new provider, first model is auto-selected</li>
                      <li>This demonstrates the cascading effect</li>
                    </ul>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold mb-2">Available Models:</h3>
                    <div className="max-h-[200px] overflow-y-auto p-2 bg-muted rounded-md">
                      {isLoadingModels ? (
                        <p className="text-sm text-muted-foreground">Loading...</p>
                      ) : providerModels.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No models available</p>
                      ) : (
                        <ul className="text-xs space-y-1">
                          {providerModels.map((model) => (
                            <li key={model} className={model === selectedModel ? 'font-bold' : ''}>
                              {model}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            {/* ModelSelector Component */}
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-4">ModelSelector Component</h2>
              <div className="space-y-4">
                <ModelSelector
                  selected={selectedModel}
                  onSelect={setSelectedModel}
                  showProvider={true}
                />
                <div className="text-sm text-muted-foreground">
                  <p>Selected model: <strong>{selectedModel}</strong></p>
                </div>
              </div>
            </Card>

            {/* Test Messages Display */}
            <Card className="p-6">
              <h2 className="text-xl font-semibold mb-4">Test Messages State</h2>
              <div className="space-y-2 text-sm">
                <p className="font-medium">Total messages: {testMessages.length}</p>
                <div className="max-h-[300px] overflow-y-auto space-y-2">
                  {testMessages.map((msg) => (
                    <div key={msg.id} className="p-2 bg-muted rounded text-xs">
                      <div className="font-medium">{msg.role}</div>
                      <div className="truncate">{msg.content.substring(0, 50)}...</div>
                      {msg.modelUsed && (
                        <div className="text-muted-foreground">Model: {msg.modelUsed}</div>
                      )}
                    </div>
                  ))}
                </div>
                <Button
                  onClick={() => setTestMessages([])}
                  variant="outline"
                  size="sm"
                  className="w-full"
                >
                  Clear Messages
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* Component Documentation */}
        <Card className="mt-6 p-6">
          <h2 className="text-xl font-semibold mb-4">Component Documentation</h2>
          <div className="space-y-4 text-sm">
            <div>
              <h3 className="font-semibold mb-2">ChatInterface</h3>
              <p className="text-muted-foreground mb-2">
                Main chat container that manages conversations and message state.
              </p>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li>Automatically creates conversations</li>
                <li>Handles message streaming</li>
                <li>Manages model selection</li>
                <li>Supports real-time AI responses</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-2">MessageList</h3>
              <p className="text-muted-foreground mb-2">
                Displays messages with markdown rendering and syntax highlighting.
              </p>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li>Auto-scrolls to bottom</li>
                <li>Markdown support</li>
                <li>Code syntax highlighting</li>
                <li>User/assistant message styling</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-2">MessageInput</h3>
              <p className="text-muted-foreground mb-2">
                Input field with send button for user messages.
              </p>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li>Enter key to send</li>
                <li>Disabled state when loading</li>
                <li>Auto-clears after send</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-2">ModelSelector</h3>
              <p className="text-muted-foreground mb-2">
                Dropdown to select AI models with provider-based cascading.
              </p>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li>Fetches providers dynamically from API</li>
                <li>Provider selection cascades to update model list</li>
                <li>Auto-detects provider for pre-selected model</li>
                <li>Auto-selects first model when provider changes</li>
                <li>Shows friendly provider names (OpenAI, Anthropic, etc.)</li>
                <li>Handles loading states and errors gracefully</li>
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
