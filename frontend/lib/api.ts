// API client for backend communication
import axios, { AxiosError, AxiosRequestConfig, AxiosResponse } from 'axios';
import type {
  VizQLQueryRequest,
  VizQLQueryResponse,
  VizQLExecuteRequest,
  VizQLExecuteResponse,
  ExportViewsRequest,
  ExportViewsResponse,
  GenerateSummaryRequest,
  GenerateSummaryResponse,
  AggregateViewsRequest,
  AggregateViewsResponse,
  ClassifyIntentRequest,
  ClassifyIntentResponse,
  RouteQueryRequest,
  RouteQueryResponse,
  TableauProject,
  TableauWorkbook,
  ProjectContents,
  DatasourceSchema,
  DatasourceSample,
  ChatContext,
  AddContextRequest,
  RemoveContextRequest,
} from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_TIMEOUT = 30000; // 30 seconds

export const apiClient = axios.create({
  baseURL: API_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for error handling
apiClient.interceptors.request.use(
  (config) => {
    // Add any request modifications here (e.g., auth tokens)
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // Retry logic for network errors or 5xx errors
    if (
      error.response &&
      error.response.status >= 500 &&
      !originalRequest._retry &&
      originalRequest
    ) {
      originalRequest._retry = true;
      
      // Wait before retrying (exponential backoff)
      await new Promise((resolve) => setTimeout(resolve, 1000));
      
      return apiClient(originalRequest);
    }

    // Handle specific error cases
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      const message = (error.response.data as any)?.detail || error.message;
      
      switch (status) {
        case 401:
          // Handle unauthorized - could redirect to login
          console.error('Unauthorized access');
          break;
        case 403:
          console.error('Forbidden access');
          break;
        case 404:
          console.error('Resource not found');
          break;
        case 500:
          console.error('Server error');
          break;
        default:
          console.error(`API error: ${status} - ${message}`);
      }
    } else if (error.request) {
      // Request made but no response received
      console.error('Network error - no response received');
    } else {
      // Error setting up request
      console.error('Request setup error:', error.message);
    }

    return Promise.reject(error);
  }
);

// Chat API functions
export interface ConversationResponse {
  id: number;
  name?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface MessageResponse {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  model_used?: string;
  tokens_used?: number;
  created_at: string;
}

export interface ChatResponse {
  message: MessageResponse;
  conversation_id: number;
  model: string;
  tokens_used: number;
}

export interface MessageRequest {
  conversation_id: number;
  content: string;
  model?: string;
  agent_type?: 'summary' | 'vizql' | 'general';
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
}

export const chatApi = {
  // Create a new conversation
  createConversation: async (): Promise<ConversationResponse> => {
    const response = await apiClient.post<ConversationResponse>('/api/v1/chat/conversations');
    return response.data;
  },

  // List all conversations
  listConversations: async (skip = 0, limit = 50): Promise<ConversationResponse[]> => {
    const response = await apiClient.get<ConversationResponse[]>('/api/v1/chat/conversations', {
      params: { skip, limit },
    });
    return response.data;
  },

  // Get a conversation by ID
  getConversation: async (conversationId: number): Promise<ConversationResponse> => {
    const response = await apiClient.get<ConversationResponse>(
      `/api/v1/chat/conversations/${conversationId}`
    );
    return response.data;
  },

  // Get messages for a conversation
  getMessages: async (conversationId: number): Promise<MessageResponse[]> => {
    const response = await apiClient.get<MessageResponse[]>(
      `/api/v1/chat/conversations/${conversationId}/messages`
    );
    return response.data;
  },

  // Rename a conversation
  renameConversation: async (conversationId: number, name: string): Promise<ConversationResponse> => {
    const response = await apiClient.patch<ConversationResponse>(
      `/api/v1/chat/conversations/${conversationId}/rename`,
      { name }
    );
    return response.data;
  },

  // Send a message (non-streaming)
  sendMessage: async (request: MessageRequest): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/api/v1/chat/message', {
      ...request,
      stream: false,
    });
    return response.data;
  },

  // Send a message with streaming
  sendMessageStream: async (
    request: MessageRequest,
    onChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): Promise<void> => {
    try {
      const response = await fetch(`${API_URL}/api/v1/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...request, stream: true }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (!data) {
              continue; // Skip empty data lines
            }
            if (data === '[DONE]') {
              onComplete();
              return;
            }
            // Check if it's a JSON error object
            if (data.startsWith('{') && data.includes('error')) {
              try {
                const parsed = JSON.parse(data);
                if (parsed.error) {
                  onError(new Error(parsed.error));
                  return;
                }
              } catch {
                // Not valid JSON, treat as content
              }
            }
            // Treat as content chunk (plain text)
            if (data && data !== '[DONE]') {
              onChunk(data);
            }
          }
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        const line = buffer.trim();
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data && data !== '[DONE]') {
            onChunk(data);
          }
        }
      }

      onComplete();
    } catch (error) {
      console.error('Streaming error:', error);
      onError(error instanceof Error ? error : new Error('Unknown error'));
    }
  },

  // Delete a conversation
  deleteConversation: async (conversationId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/chat/conversations/${conversationId}`);
  },
};

// Gateway API functions
export const gatewayApi = {
  // Get available providers
  getProviders: async (): Promise<string[]> => {
    const response = await apiClient.get<{ providers: string[] }>('/api/v1/gateway/providers');
    return response.data.providers;
  },

  // Get available models, optionally filtered by provider
  getModels: async (provider?: string): Promise<string[]> => {
    const params = provider ? { provider } : {};
    const response = await apiClient.get<{ models: string[] }>('/api/v1/gateway/models', {
      params,
    });
    return response.data.models;
  },
};

// Agent API functions
export const agentsApi = {
  // VizQL Agent
  constructVizQL: async (request: VizQLQueryRequest): Promise<VizQLQueryResponse> => {
    const response = await apiClient.post<VizQLQueryResponse>(
      '/api/v1/agents/vds/construct-query',
      request
    );
    return response.data;
  },

  executeVizQL: async (request: VizQLExecuteRequest): Promise<VizQLExecuteResponse> => {
    const response = await apiClient.post<VizQLExecuteResponse>(
      '/api/v1/agents/vds/execute-query',
      request
    );
    return response.data;
  },

  // Summary Agent
  exportViews: async (request: ExportViewsRequest): Promise<ExportViewsResponse> => {
    const response = await apiClient.post<ExportViewsResponse>(
      '/api/v1/agents/summary/export-views',
      request
    );
    return response.data;
  },

  generateSummary: async (request: GenerateSummaryRequest): Promise<GenerateSummaryResponse> => {
    const response = await apiClient.post<GenerateSummaryResponse>(
      '/api/v1/agents/summary/generate-summary',
      request
    );
    return response.data;
  },

  aggregateViews: async (request: AggregateViewsRequest): Promise<AggregateViewsResponse> => {
    const response = await apiClient.post<AggregateViewsResponse>(
      '/api/v1/agents/summary/aggregate-views',
      request
    );
    return response.data;
  },

  // Router
  classifyIntent: async (request: ClassifyIntentRequest): Promise<ClassifyIntentResponse> => {
    const response = await apiClient.post<ClassifyIntentResponse>(
      '/api/v1/agents/router/classify',
      request
    );
    return response.data;
  },

  routeQuery: async (request: RouteQueryRequest): Promise<RouteQueryResponse> => {
    const response = await apiClient.post<RouteQueryResponse>(
      '/api/v1/agents/router/route',
      request
    );
    return response.data;
  },
};

// Phase 5A: Object Explorer API functions
export const tableauExplorerApi = {
  // List all projects
  listProjects: async (parentProjectId?: string, pageSize = 100, pageNumber = 1): Promise<TableauProject[]> => {
    const params: Record<string, any> = { pageSize, pageNumber };
    if (parentProjectId) params.parent_project_id = parentProjectId;
    const response = await apiClient.get<TableauProject[]>('/api/v1/tableau/projects', { params });
    return response.data;
  },

  // Get project contents
  getProjectContents: async (projectId: string): Promise<ProjectContents> => {
    const response = await apiClient.get<ProjectContents>(`/api/v1/tableau/projects/${projectId}/contents`);
    return response.data;
  },

  // List all workbooks
  listWorkbooks: async (projectId?: string, pageSize = 100, pageNumber = 1): Promise<TableauWorkbook[]> => {
    const params: Record<string, any> = { pageSize, pageNumber };
    if (projectId) params.project_id = projectId;
    const response = await apiClient.get<TableauWorkbook[]>('/api/v1/tableau/workbooks', { params });
    return response.data;
  },

  // List views in workbook
  listWorkbookViews: async (workbookId: string, pageSize = 100, pageNumber = 1): Promise<TableauView[]> => {
    const response = await apiClient.get<TableauView[]>(`/api/v1/tableau/workbooks/${workbookId}/views`, {
      params: { pageSize, pageNumber },
    });
    return response.data;
  },

  // Get datasource schema
  getDatasourceSchema: async (datasourceId: string): Promise<DatasourceSchema> => {
    const response = await apiClient.get<DatasourceSchema>(`/api/v1/tableau/datasources/${datasourceId}/schema`);
    return response.data;
  },

  // Get datasource sample data
  getDatasourceSample: async (datasourceId: string, limit = 100): Promise<DatasourceSample> => {
    const response = await apiClient.get<DatasourceSample>(`/api/v1/tableau/datasources/${datasourceId}/sample`, {
      params: { limit },
    });
    return response.data;
  },
};

// Phase 5B: Chat Context API functions
export const chatContextApi = {
  // Add object to chat context
  addContext: async (request: AddContextRequest): Promise<ChatContextObject> => {
    const response = await apiClient.post<ChatContextObject>('/api/v1/chat/context/add', request);
    return response.data;
  },

  // Remove object from chat context
  removeContext: async (request: RemoveContextRequest): Promise<void> => {
    await apiClient.delete('/api/v1/chat/context/remove', {
      params: {
        conversation_id: request.conversation_id,
        object_id: request.object_id,
      },
    });
  },

  // Get chat context for conversation
  getContext: async (conversationId: number): Promise<ChatContext> => {
    const response = await apiClient.get<ChatContext>(`/api/v1/chat/context/${conversationId}`);
    return response.data;
  },
};

export default apiClient;
