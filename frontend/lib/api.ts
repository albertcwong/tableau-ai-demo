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
  withCredentials: true, // Include credentials in CORS requests
});

// Request interceptor for error handling
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      // Debug logging (remove in production)
      if (process.env.NODE_ENV === 'development') {
        console.debug(`[API] Adding auth token to request: ${config.method?.toUpperCase()} ${config.url}`);
      }
    } else {
      // Debug logging (remove in production)
      if (process.env.NODE_ENV === 'development') {
        console.warn(`[API] No auth token found for request: ${config.method?.toUpperCase()} ${config.url}`);
      }
    }
    
    // Add Tableau config ID header for tableau and vizql API endpoints
    if (typeof window !== 'undefined' && (config.url?.startsWith('/api/v1/tableau/') || config.url?.startsWith('/api/v1/vizql/'))) {
      const configId = localStorage.getItem('tableau_config_id');
      if (configId) {
        config.headers['X-Tableau-Config-Id'] = configId;
      }
    }
    
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
      const url = originalRequest?.url || '';
      
      switch (status) {
        case 401:
          // Only redirect to login for app authentication endpoints, not Tableau endpoints
          // Tableau connection failures should be handled gracefully without logging out
          const isAuthEndpoint = url.includes('/auth/') && !url.includes('/tableau-auth/');
          const isTableauEndpoint = url.includes('/tableau/') || url.includes('/tableau-auth/');
          
          if (isAuthEndpoint && typeof window !== 'undefined') {
            // App authentication failed - redirect to login
            localStorage.removeItem('auth_token');
            window.location.href = '/login';
          } else if (isTableauEndpoint) {
            // Tableau endpoint error - don't redirect, just log
            console.warn('Tableau connection error:', message);
          } else if (typeof window !== 'undefined') {
            // Other 401 errors - check if it's a general auth issue
            // Only redirect if it's clearly an auth problem, not a Tableau connectivity issue
            console.warn('Unauthorized access:', message);
          }
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
  vizql_query?: Record<string, any> | null;  // VizQL query used to generate the answer (for vizql agent)
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  model_used?: string;
  tokens_used?: number;
  feedback?: string | null;
  feedback_text?: string | null;
  total_time_ms?: number | null;
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
    onError: (error: Error) => void,
    onStructuredChunk?: (chunk: import('@/types').AgentMessageChunk) => void,
    abortSignal?: AbortSignal
  ): Promise<void> => {
    try {
      const response = await fetch(`${API_URL}/api/v1/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...request, stream: true }),
        signal: abortSignal,
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
        // Check if aborted
        if (abortSignal?.aborted) {
          reader.cancel();
          return;
        }
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
            
            // Try to parse as structured AgentMessageChunk
            try {
              const parsed = JSON.parse(data);
              // Check if it's a structured message chunk
              if (parsed.message_type && parsed.content) {
                const structuredChunk: import('@/types').AgentMessageChunk = parsed;
                
                // Call structured chunk handler if provided
                if (onStructuredChunk) {
                  onStructuredChunk(structuredChunk);
                }
                
                // Handle completion marker
                if (structuredChunk.message_type === 'progress' && 
                    typeof structuredChunk.content.data === 'string' &&
                    structuredChunk.content.data === '[DONE]') {
                  onComplete();
                  return;
                }
                
                // Handle errors
                if (structuredChunk.message_type === 'error') {
                  const errorMsg = typeof structuredChunk.content.data === 'string' 
                    ? structuredChunk.content.data 
                    : JSON.stringify(structuredChunk.content.data);
                  onError(new Error(errorMsg));
                  return;
                }
                
                // Don't call onChunk for reasoning chunks - they're handled by onStructuredChunk
                // Only call onChunk for final_answer chunks if onStructuredChunk is not provided (backward compatibility)
                if (structuredChunk.message_type === 'final_answer' && !onStructuredChunk) {
                  if (structuredChunk.content.type === 'text' && typeof structuredChunk.content.data === 'string') {
                    onChunk(structuredChunk.content.data);
                  }
                }
                
                continue;
              }
            } catch {
              // Not valid JSON, fall through to legacy handling
            }
            
            // Legacy handling for plain text chunks
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
      // Don't call onError for abort errors - cancellation is intentional
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Stream cancelled by user');
        return;
      }
      console.error('Streaming error:', error);
      onError(error instanceof Error ? error : new Error('Unknown error'));
    }
  },

  // Delete a conversation
  deleteConversation: async (conversationId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/chat/conversations/${conversationId}`);
  },

  // Update message feedback
  updateMessageFeedback: async (messageId: number, feedback: 'thumbs_up' | 'thumbs_down' | null, feedbackText?: string | null): Promise<MessageResponse> => {
    const response = await apiClient.put<MessageResponse>(`/api/v1/chat/messages/${messageId}/feedback`, {
      feedback: feedback || null,
      feedback_text: feedbackText || null,
    });
    return response.data;
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

  // Get gateway health (includes models if requested)
  health: async (includeModels: boolean = false): Promise<{ status: string; providers: string[]; models?: string[]; model_count: number }> => {
    const params = includeModels ? { include_models: 'true' } : {};
    const response = await apiClient.get<{ status: string; providers: string[]; models?: string[]; model_count: number }>('/api/v1/gateway/health', {
      params,
    });
    return response.data;
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
  // List all datasources
  listDatasources: async (pageSize = 100, pageNumber = 1): Promise<TableauDatasource[]> => {
    const params: Record<string, any> = { pageSize, pageNumber };
    const response = await apiClient.get<TableauDatasource[]>('/api/v1/tableau/datasources', { params });
    return response.data;
  },

  // List all workbooks
  listWorkbooks: async (pageSize = 100, pageNumber = 1): Promise<TableauWorkbook[]> => {
    const params: Record<string, any> = { pageSize, pageNumber };
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

  // Execute VizQL Data Service query
  executeVDSQuery: async (datasourceId: string, query: any): Promise<{ columns: string[]; data: unknown[][]; row_count: number }> => {
    const response = await apiClient.post<{ columns: string[]; data: unknown[][]; row_count: number }>(
      `/api/v1/tableau/datasources/${datasourceId}/execute-query`,
      { datasource_id: datasourceId, query }
    );
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

// Auth API functions
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    username: string;
    role: string;
    is_active: boolean;
  };
}

export interface UserResponse {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
}

export interface TableauConfigOption {
  id: number;
  name: string;
  server_url: string;
  site_id?: string | null;
}

export interface TableauAuthRequest {
  config_id: number;
}

export interface TableauAuthResponse {
  authenticated: boolean;
  server_url: string;
  site_id?: string | null;
  user_id?: string | null;
  token: string;
  expires_at?: string | null;
}

export const authApi = {
  login: async (credentials: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', credentials);
    // Store token
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', response.data.access_token);
    }
    return response.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/api/v1/auth/logout');
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
    }
  },

  getCurrentUser: async (): Promise<UserResponse> => {
    const response = await apiClient.get<UserResponse>('/api/v1/auth/me');
    return response.data;
  },

  listTableauConfigs: async (): Promise<TableauConfigOption[]> => {
    const response = await apiClient.get<TableauConfigOption[]>('/api/v1/tableau-auth/configs');
    return response.data;
  },

  authenticateTableau: async (request: TableauAuthRequest): Promise<TableauAuthResponse> => {
    const response = await apiClient.post<TableauAuthResponse>('/api/v1/tableau-auth/authenticate', request);
    return response.data;
  },
};

// Admin API functions
export interface UserCreate {
  username: string;
  password: string;
  role: string;
}

export interface TableauConfigCreate {
  name: string;
  server_url: string;
  site_id?: string;
  api_version?: string;
  client_id: string;
  client_secret: string;
  secret_id?: string;
}

export interface TableauConfigUpdate {
  name?: string;
  server_url?: string;
  site_id?: string;
  api_version?: string;
  client_id?: string;
  client_secret?: string;
  secret_id?: string;
  is_active?: boolean;
}

export interface TableauConfigResponse {
  id: number;
  name: string;
  server_url: string;
  site_id?: string | null;
  api_version?: string | null;
  client_id: string;
  client_secret: string;
  secret_id?: string | null;
  is_active: boolean;
  created_by?: number | null;
  created_at: string;
}

export interface ProviderConfigCreate {
  name: string;
  provider_type: string;
  api_key?: string;
  salesforce_client_id?: string;
  salesforce_private_key_path?: string;
  salesforce_username?: string;
  salesforce_models_api_url?: string;
  vertex_project_id?: string;
  vertex_location?: string;
  vertex_service_account_path?: string;
  apple_endor_endpoint?: string;
}

export interface ProviderConfigUpdate {
  name?: string;
  provider_type?: string;
  api_key?: string;
  salesforce_client_id?: string;
  salesforce_private_key_path?: string;
  salesforce_username?: string;
  salesforce_models_api_url?: string;
  vertex_project_id?: string;
  vertex_location?: string;
  vertex_service_account_path?: string;
  apple_endor_endpoint?: string;
  is_active?: boolean;
}

export interface ProviderConfigResponse {
  id: number;
  name: string;
  provider_type: string;
  is_active: boolean;
  created_by?: number | null;
  created_at: string;
  api_key?: string | null;
  salesforce_client_id?: string | null;
  salesforce_private_key_path?: string | null;
  salesforce_username?: string | null;
  salesforce_models_api_url?: string | null;
  vertex_project_id?: string | null;
  vertex_location?: string | null;
  vertex_service_account_path?: string | null;
  apple_endor_endpoint?: string | null;
}

export interface ContextObjectResponse {
  object_id: string;
  object_type: string;
  object_name?: string | null;
  added_at: string;
}

export interface ConversationMessageResponse {
  id: number;
  role: string;
  content: string;
  model_used?: string | null;
  tokens_used?: number | null;
  total_time_ms?: number | null;
  created_at: string;
}

export interface UserInfoResponse {
  id: number;
  username: string;
  role: string;
}

export interface FeedbackDetailResponse {
  message_id: number;
  conversation_id: number;
  role: string;
  content: string;
  feedback: string;
  feedback_text?: string | null;
  agent_type?: string | null;
  total_time_ms?: number | null;
  model_used?: string | null;
  created_at: string;
  conversation_name?: string | null;
  user?: UserInfoResponse | null;
  context_objects: ContextObjectResponse[];
  conversation_thread: ConversationMessageResponse[];
}

// VizQL API functions
export interface EnrichSchemaResponse {
  datasource_id: string;
  field_count: number;
  measure_count: number;
  dimension_count: number;
  cached: boolean;
  enriched_schema: {
    datasource_id: string;
    fields: Array<{
      fieldCaption: string;
      fieldName: string;
      dataType: string;
      fieldRole: string;
      fieldType: string;
      defaultAggregation?: string;
      suggestedAggregation?: string;
      columnClass: string;
      description: string;
      formula?: string;
      hidden: boolean;
      aliases?: Array<{ member: any; value: any }>;
      // Field statistics
      cardinality?: number | null;
      sample_values?: string[];
      min?: number | null;
      max?: number | null;
      null_percentage?: number | null;
    }>;
    field_map: Record<string, any>;
    measures: string[];
    dimensions: string[];
  };
}

export interface SupportedFunctionsResponse {
  datasource_id: string;
  functions: Array<{
    name: string;
    overloads: Array<{
      arg_types: string[];
      return_type: string;
    }>;
  }>;
  function_count: number;
}

export const vizqlApi = {
  // Enrich datasource schema with VizQL metadata
  enrichSchema: async (datasourceId: string, forceRefresh = false, includeStatistics = true): Promise<EnrichSchemaResponse> => {
    const response = await apiClient.post<EnrichSchemaResponse>(
      `/api/v1/vizql/datasources/${datasourceId}/enrich-schema`,
      null,
      { params: { force_refresh: forceRefresh, include_statistics: includeStatistics } }
    );
    return response.data;
  },

  // Get supported functions for a datasource
  getSupportedFunctions: async (datasourceId: string): Promise<SupportedFunctionsResponse> => {
    const response = await apiClient.get<SupportedFunctionsResponse>(
      `/api/v1/vizql/datasources/${datasourceId}/supported-functions`
    );
    return response.data;
  },
};

export const adminApi = {
  // User management
  listUsers: async (): Promise<UserResponse[]> => {
    const response = await apiClient.get<UserResponse[]>('/api/v1/admin/users');
    return response.data;
  },

  createUser: async (userData: UserCreate): Promise<UserResponse> => {
    const response = await apiClient.post<UserResponse>('/api/v1/admin/users', userData);
    return response.data;
  },

  deleteUser: async (userId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/admin/users/${userId}`);
  },

  // Tableau config management
  listTableauConfigs: async (): Promise<TableauConfigResponse[]> => {
    const response = await apiClient.get<TableauConfigResponse[]>('/api/v1/admin/tableau-configs');
    return response.data;
  },

  createTableauConfig: async (configData: TableauConfigCreate): Promise<TableauConfigResponse> => {
    const response = await apiClient.post<TableauConfigResponse>('/api/v1/admin/tableau-configs', configData);
    return response.data;
  },

  updateTableauConfig: async (configId: number, configData: TableauConfigUpdate): Promise<TableauConfigResponse> => {
    const response = await apiClient.put<TableauConfigResponse>(`/api/v1/admin/tableau-configs/${configId}`, configData);
    return response.data;
  },

  deleteTableauConfig: async (configId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/admin/tableau-configs/${configId}`);
  },

  // Provider config management
  listProviderConfigs: async (): Promise<ProviderConfigResponse[]> => {
    const response = await apiClient.get<ProviderConfigResponse[]>('/api/v1/admin/provider-configs');
    return response.data;
  },

  createProviderConfig: async (configData: ProviderConfigCreate): Promise<ProviderConfigResponse> => {
    const response = await apiClient.post<ProviderConfigResponse>('/api/v1/admin/provider-configs', configData);
    return response.data;
  },

  updateProviderConfig: async (configId: number, configData: ProviderConfigUpdate): Promise<ProviderConfigResponse> => {
    const response = await apiClient.put<ProviderConfigResponse>(`/api/v1/admin/provider-configs/${configId}`, configData);
    return response.data;
  },

  deleteProviderConfig: async (configId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/admin/provider-configs/${configId}`);
  },

  // Feedback management
  listFeedback: async (feedbackType?: 'thumbs_up' | 'thumbs_down'): Promise<FeedbackDetailResponse[]> => {
    const params = feedbackType ? { feedback_type: feedbackType } : {};
    const response = await apiClient.get<FeedbackDetailResponse[]>('/api/v1/admin/feedback', { params });
    return response.data;
  },
};

export default apiClient;
