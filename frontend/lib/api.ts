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
  ChatContextObject,
  DatasourceSchema,
  DatasourceSample,
  ChatContext,
  AddContextRequest,
  RemoveContextRequest,
  PaginatedDatasourcesResponse,
  PaginatedWorkbooksResponse,
  PaginatedViewsResponse,
} from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_TIMEOUT = 30000; // 30 seconds
const LONG_OPERATION_TIMEOUT = 180000; // 3 minutes for schema enrichment, etc.

// Auth0 token cache (for client-side token management)
let auth0TokenCache: { token: string | null; expiresAt: number } = { token: null, expiresAt: 0 };

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
  async (config) => {
    // Try to get Auth0 access token first (if Auth0 is configured)
    let token: string | null = null;
    
    if (typeof window !== 'undefined') {
      // Try to get token from Auth0 session cookies via API route
      // The Auth0 SDK stores tokens in httpOnly cookies, so we need a server route to access them
      try {
        const response = await fetch('/api/auth/token', { 
          credentials: 'include',
          cache: 'no-store' // Always fetch fresh token
        });
        if (response.ok) {
          const data = await response.json();
          token = data.token;
          if (process.env.NODE_ENV === 'development') {
            console.debug('[API Client] Auth0 token retrieved:', token ? `Token (${token.length} chars)` : 'null');
          }
        } else {
          if (process.env.NODE_ENV === 'development') {
            console.debug('[API Client] Failed to get Auth0 token, status:', response.status);
          }
        }
      } catch (error) {
        console.warn('[API Client] Failed to fetch Auth0 token:', error);
      }
      
      // Fallback to localStorage for backward compatibility (internal tokens)
      if (!token) {
        token = localStorage.getItem('auth_token');
      }
    }
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      // Debug logging (remove in production)
      if (process.env.NODE_ENV === 'development') {
        console.debug(`[API] Adding auth token to request: ${config.method?.toUpperCase()} ${config.url}`);
      }
    } else {
      // Public endpoints that don't require authentication
      const publicEndpoints = ['/auth/config', '/auth/auth0-config', '/auth/login'];
      const isPublicEndpoint = publicEndpoints.some(endpoint => config.url?.includes(endpoint));
      
      // Debug logging (remove in production)
      if (process.env.NODE_ENV === 'development' && !isPublicEndpoint) {
        console.warn(`[API] No auth token found for request: ${config.method?.toUpperCase()} ${config.url}`);
      }
    }
    
    // Add Tableau config ID and auth type headers for tableau, vizql, and chat API endpoints
    if (typeof window !== 'undefined' && (
      config.url?.startsWith('/api/v1/tableau/') || 
      config.url?.startsWith('/api/v1/vizql/') ||
      config.url?.startsWith('/api/v1/chat/')
    )) {
      const configId = localStorage.getItem('tableau_config_id');
      if (configId) {
        config.headers['X-Tableau-Config-Id'] = configId;
      }
      const authType = localStorage.getItem('tableau_auth_type');
      if (authType) {
        config.headers['X-Tableau-Auth-Type'] = authType;
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
          const isTableauConfigsEndpoint = url.includes('/tableau-auth/configs');
          
          // Suppress 401 errors for tableau-auth/configs during logout (expected behavior)
          const hasNoAuthToken = typeof window !== 'undefined' && !localStorage.getItem('auth_token');
          if (isTableauConfigsEndpoint && hasNoAuthToken) {
            // Expected during logout - silently ignore
            break;
          }
          
          if (isAuthEndpoint && typeof window !== 'undefined') {
            // App authentication failed - redirect to login
            localStorage.removeItem('auth_token');
            window.location.href = '/login';
          } else if (isTableauEndpoint) {
            const isTableauAuthError = typeof message === 'string' && message.toLowerCase().includes('tableau');
            if (isTableauAuthError && typeof window !== 'undefined') {
              // Tableau token invalidated (e.g. new sign-in). Clear connection so user reconnects.
              localStorage.removeItem('tableau_connected');
              localStorage.removeItem('tableau_token_expires_at');
            }
            if (!isTableauAuthError && typeof window !== 'undefined') {
              // App auth failed on Tableau endpoint - redirect to login
              localStorage.removeItem('auth_token');
              window.location.href = '/login';
            } else {
              console.warn('Tableau connection error (token may be invalidated):', message);
            }
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
  feedback?: 'thumbs_up' | 'thumbs_down' | null;
  feedback_text?: string | null;
  total_time_ms?: number | null;
  extra_metadata?: Record<string, any> | null;  // Additional metadata (e.g., is_greeting flag)
  created_at: string;
}

export interface ChatResponse {
  message: MessageResponse;
  conversation_id: number;
  model: string;
  tokens_used: number;
}

export type SummaryMode = 'brief' | 'full' | 'custom';

export interface MessageRequest {
  conversation_id: number;
  content: string;
  model?: string;
  provider: string;
  agent_type?: 'summary' | 'vizql';
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  embedded_state?: Record<string, import('@/lib/tableauEmbeddedState').EmbeddedViewState>;
  summary_mode?: SummaryMode;
}

export const chatApi = {
  // Create a new conversation
  createConversation: async (agentType?: 'vizql' | 'summary'): Promise<ConversationResponse> => {
    const url = agentType 
      ? `/api/v1/chat/conversations?agent_type=${agentType}`
      : '/api/v1/chat/conversations';
    const response = await apiClient.post<ConversationResponse>(url);
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

  // Create a greeting message when agent type changes
  createGreetingMessage: async (conversationId: number, agentType: 'vizql' | 'summary'): Promise<MessageResponse> => {
    const response = await apiClient.post<MessageResponse>(
      `/api/v1/chat/conversations/${conversationId}/greeting?agent_type=${agentType}`
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
      // Build headers with Tableau config if available
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      // Add auth token if available (same logic as axios interceptor)
      if (typeof window !== 'undefined') {
        let token: string | null = null;
        
        // Try to get token from Auth0 session cookies via API route first
        try {
          const response = await fetch('/api/auth/token', { 
            credentials: 'include',
            cache: 'no-store'
          });
          if (response.ok) {
            const data = await response.json();
            token = data.token;
          }
        } catch (error) {
          // Fallback to localStorage for backward compatibility
        }
        
        // Fallback to localStorage if Auth0 token not available
        if (!token) {
          token = localStorage.getItem('auth_token');
        }
        
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        
        // Add Tableau config headers
        const configId = localStorage.getItem('tableau_config_id');
        if (configId) {
          headers['X-Tableau-Config-Id'] = configId;
        }
        const authType = localStorage.getItem('tableau_auth_type');
        if (authType) {
          headers['X-Tableau-Auth-Type'] = authType;
        }
        // Endor A3 token when provider is apple
        if (request.provider?.toLowerCase() === 'apple') {
          try {
            const tokenHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
            if (token) tokenHeaders['Authorization'] = `Bearer ${token}`;
            const tokenRes = await fetch(`${API_URL}/api/v1/gateway/endor-token`, {
              credentials: 'include',
              headers: tokenHeaders,
            });
            if (tokenRes.ok) {
              const { token: a3Token } = await tokenRes.json();
              if (a3Token) headers['X-Apple-IDMS-A3-Token'] = a3Token;
            }
          } catch {
            // continue without token; gateway will generate
          }
        }
      }
      
      const response = await fetch(`${API_URL}/api/v1/chat/message`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ ...request, stream: true }),
        signal: abortSignal,
        credentials: 'include', // Include cookies for Auth0
      });

      if (!response.ok) {
        const errorText = await response.text();
        let message = `Request failed (${response.status})`;
        try {
          const body = JSON.parse(errorText);
          if (typeof body?.detail === 'string') {
            message = body.detail;
          } else if (body?.detail?.message) {
            message = body.detail.message;
          }
        } catch {
          if (errorText.length < 200) message = errorText;
        }
        const err = new Error(message) as Error & { status?: number; errorCode?: string };
        err.status = response.status;
        err.errorCode = response.headers.get('X-Error-Code') || undefined;
        throw err;
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

  // Delete all conversations for the current user
  deleteAllConversations: async (): Promise<{ deleted_count: number; message: string }> => {
    const response = await apiClient.delete<{ deleted_count: number; message: string }>('/api/v1/chat/conversations');
    return response.data;
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
  // Get available providers with display names
  getProviders: async (): Promise<Array<{ provider: string; name: string }>> => {
    const response = await apiClient.get<{ providers: Array<{ provider: string; name: string }> }>('/api/v1/gateway/providers');
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

  // Get Endor A3 token (required when provider=apple)
  getEndorToken: async (): Promise<string> => {
    const response = await apiClient.get<{ token: string }>('/api/v1/gateway/endor-token');
    return response.data.token;
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
  listDatasources: async (
    pageSize = 100,
    pageNumber = 1,
    search?: string
  ): Promise<PaginatedDatasourcesResponse> => {
    const params: Record<string, any> = { pageSize, pageNumber };
    if (search) {
      params.search = search;
    }
    const response = await apiClient.get<PaginatedDatasourcesResponse>('/api/v1/tableau/datasources', { params });
    return response.data;
  },

  // List all workbooks
  listWorkbooks: async (
    pageSize = 100,
    pageNumber = 1,
    search?: string
  ): Promise<PaginatedWorkbooksResponse> => {
    const params: Record<string, any> = { pageSize, pageNumber };
    if (search) {
      params.search = search;
    }
    const response = await apiClient.get<PaginatedWorkbooksResponse>('/api/v1/tableau/workbooks', { params });
    return response.data;
  },

  // List views in workbook
  listWorkbookViews: async (
    workbookId: string,
    pageSize = 100,
    pageNumber = 1,
    search?: string
  ): Promise<PaginatedViewsResponse> => {
    const params: Record<string, any> = { pageSize, pageNumber };
    if (search) {
      params.search = search;
    }
    const response = await apiClient.get<PaginatedViewsResponse>(`/api/v1/tableau/workbooks/${workbookId}/views`, {
      params,
    });
    return response.data;
  },

  // List projects (stub - projects endpoint not yet implemented)
  listProjects: async (): Promise<TableauProject[]> => {
    // TODO: Implement projects endpoint in backend
    return [];
  },

  // Get project contents (stub - endpoint not yet implemented)
  getProjectContents: async (projectId: string): Promise<ProjectContents> => {
    // TODO: Implement project contents endpoint in backend
    return { project_id: projectId, datasources: [], workbooks: [], projects: [] };
  },

  // Get datasource schema (enrichment pipeline: VizQL + Metadata API - can be slow)
  getDatasourceSchema: async (datasourceId: string, forceRefresh = false): Promise<DatasourceSchema> => {
    const response = await apiClient.get<DatasourceSchema>(`/api/v1/tableau/datasources/${datasourceId}/schema`, {
      timeout: LONG_OPERATION_TIMEOUT,
      params: forceRefresh ? { force_refresh: 'true' } : undefined,
    });
    return response.data;
  },

  // Get datasource sample data (schema + query can be slow; use longer timeout)
  getDatasourceSample: async (datasourceId: string, limit = 100): Promise<DatasourceSample> => {
    const response = await apiClient.get<DatasourceSample>(`/api/v1/tableau/datasources/${datasourceId}/sample`, {
      params: { limit },
      timeout: LONG_OPERATION_TIMEOUT,
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
  preferred_provider?: string | null;
  preferred_model?: string | null;
  preferred_agent_type?: string | null;
  preferred_tableau_auth_type?: string | null;
  tableau_username?: string | null;
}

export interface UserTableauMappingCreate {
  user_id: number;
  tableau_server_config_id: number;
  tableau_username: string;
}

export interface UserTableauMappingUpdate {
  tableau_username: string;
}

export interface UserTableauMappingResponse {
  id: number;
  user_id: number;
  tableau_server_config_id: number;
  tableau_username: string;
  created_at: string;
  updated_at: string;
  // Note: site_id is not included as it comes from the Connected App configuration
}

export interface TableauConfigOption {
  id: number;
  name: string;
  server_url: string;
  site_id?: string | null;
  allow_pat_auth?: boolean;
  allow_standard_auth?: boolean;
  allow_connected_app_oauth?: boolean;
  has_connected_app?: boolean;
  has_connected_app_oauth?: boolean;
}

export interface TableauAuthRequest {
  config_id: number;
  auth_type?: 'connected_app' | 'pat' | 'standard' | 'connected_app_oauth';
}

export interface OAuthAuthorizeUrlResponse {
  authorize_url: string;
}

export interface SwitchSiteRequest {
  config_id: number;
  auth_type: 'standard' | 'pat';
  site_content_url: string;
}

export interface SiteInfo {
  id?: string | null;
  name?: string | null;
  contentUrl?: string | null;
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
  login: async (credentials?: LoginRequest): Promise<LoginResponse> => {
    // For Auth0, login is handled via redirect, but we keep this for backward compatibility
    if (credentials) {
      const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', credentials);
      // Store token
      if (typeof window !== 'undefined') {
        localStorage.setItem('auth_token', response.data.access_token);
      }
      return response.data;
    }
    // Auth0 login handled via redirect
    throw new Error('Auth0 login must be handled via redirect to /api/auth/login');
  },

  getAuthConfig: async (): Promise<{ enable_password_auth: boolean; enable_oauth_auth: boolean }> => {
    const response = await apiClient.get<{ enable_password_auth: boolean; enable_oauth_auth: boolean }>('/api/v1/auth/config');
    return response.data;
  },

  logout: async (): Promise<void> => {
    // For Auth0, logout is handled via redirect
    // Clear any cached tokens
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
      auth0TokenCache = { token: null, expiresAt: 0 };
    }
    // Auth0 logout handled via redirect to /api/auth/logout
  },

  getCurrentUser: async (): Promise<UserResponse> => {
    const response = await apiClient.get<UserResponse>('/api/v1/auth/me');
    return response.data;
  },

  updatePreferences: async (preferences: {
    preferred_provider?: string;
    preferred_model?: string;
    preferred_agent_type?: string;
    preferred_tableau_auth_type?: string;
  }): Promise<UserResponse> => {
    const response = await apiClient.put<UserResponse>('/api/v1/auth/preferences', preferences);
    return response.data;
  },

  listTableauConfigs: async (): Promise<TableauConfigOption[]> => {
    const response = await apiClient.get<TableauConfigOption[]>('/api/v1/tableau-auth/configs');
    return response.data;
  },

  getOAuthAuthorizeUrl: async (configId: number): Promise<OAuthAuthorizeUrlResponse> => {
    const response = await apiClient.get<OAuthAuthorizeUrlResponse>(
      `/api/v1/tableau-auth/oauth/authorize-url?config_id=${configId}`,
      { withCredentials: true }
    );
    return response.data;
  },

  authenticateTableau: async (request: TableauAuthRequest): Promise<TableauAuthResponse> => {
    const response = await apiClient.post<TableauAuthResponse>('/api/v1/tableau-auth/authenticate', request);
    return response.data;
  },

  switchSite: async (request: SwitchSiteRequest): Promise<TableauAuthResponse> => {
    const response = await apiClient.post<TableauAuthResponse>('/api/v1/tableau-auth/switch-site', request);
    return response.data;
  },

  listSites: async (configId: number, authType: 'standard' | 'pat'): Promise<SiteInfo[]> => {
    const response = await apiClient.get<SiteInfo[]>('/api/v1/tableau-auth/sites', {
      params: { config_id: configId, auth_type: authType },
    });
    return response.data;
  },
};

// User settings API (PAT management)
export interface UserTableauPAT {
  id: number;
  tableau_server_config_id: number;
  pat_name: string;
  server_name: string;
  server_url: string;
  created_at: string;
}

export interface CreateTableauPAT {
  tableau_server_config_id: number;
  pat_name: string;
  pat_secret: string;
}

export interface UserTableauPassword {
  id: number;
  tableau_server_config_id: number;
  tableau_username: string;
  server_name: string;
  server_url: string;
  created_at: string;
}

export interface CreateTableauPassword {
  tableau_server_config_id: number;
  tableau_username: string;
  password: string;
}

export const userSettingsApi = {
  getSettings: async (): Promise<{ username: string; role: string; has_tableau_pats: boolean }> => {
    const response = await apiClient.get('/api/v1/user/settings');
    return response.data;
  },
  listTableauPATs: async (): Promise<UserTableauPAT[]> => {
    const response = await apiClient.get<UserTableauPAT[]>('/api/v1/user/tableau-pats');
    return response.data;
  },
  createTableauPAT: async (data: CreateTableauPAT): Promise<UserTableauPAT> => {
    const response = await apiClient.post<UserTableauPAT>('/api/v1/user/tableau-pats', data);
    return response.data;
  },
  deleteTableauPAT: async (configId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/user/tableau-pats/${configId}`);
  },

  listTableauPasswords: async (): Promise<UserTableauPassword[]> => {
    const response = await apiClient.get<UserTableauPassword[]>('/api/v1/user/tableau-passwords');
    return response.data;
  },
  createTableauPassword: async (data: CreateTableauPassword): Promise<UserTableauPassword> => {
    const response = await apiClient.post<UserTableauPassword>('/api/v1/user/tableau-passwords', data);
    return response.data;
  },
  deleteTableauPassword: async (configId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/user/tableau-passwords/${configId}`);
  },

  getTableauAuthPreferences: async (): Promise<Record<number, string>> => {
    const response = await apiClient.get<Record<number, string>>('/api/v1/user/tableau-auth-preferences');
    return response.data;
  },

  updateTableauAuthPreference: async (configId: number, preferredAuthType: string): Promise<void> => {
    await apiClient.put('/api/v1/user/tableau-auth-preferences', {
      config_id: configId,
      preferred_auth_type: preferredAuthType,
    });
  },
};

// Admin API functions
export interface UserCreate {
  username: string;
  password: string;
  role: string;
}

export interface UserUpdate {
  username?: string;
  password?: string;
  role?: string;
  is_active?: boolean;
}

export interface TableauConfigCreate {
  name: string;
  server_url: string;
  site_id?: string;
  api_version?: string;
  client_id?: string;
  client_secret?: string;
  secret_id?: string;
  allow_pat_auth?: boolean;
  allow_standard_auth?: boolean;
  allow_connected_app_oauth?: boolean;
  eas_issuer_url?: string;
  eas_client_id?: string;
  eas_client_secret?: string;
  eas_authorization_endpoint?: string;
  eas_token_endpoint?: string;
  eas_sub_claim_field?: string;
  skip_ssl_verify?: boolean;
  ssl_cert_path?: string;
}

export interface TableauConfigUpdate {
  name?: string;
  server_url?: string;
  site_id?: string;
  api_version?: string;
  client_id?: string;
  client_secret?: string;
  secret_id?: string;
  allow_pat_auth?: boolean;
  allow_standard_auth?: boolean;
  allow_connected_app_oauth?: boolean;
  eas_issuer_url?: string;
  eas_client_id?: string;
  eas_client_secret?: string;
  eas_authorization_endpoint?: string;
  eas_token_endpoint?: string;
  eas_sub_claim_field?: string;
  skip_ssl_verify?: boolean;
  ssl_cert_path?: string;
  is_active?: boolean;
}

export interface TableauConfigResponse {
  id: number;
  name: string;
  server_url: string;
  site_id?: string | null;
  api_version?: string | null;
  client_id?: string | null;
  client_secret?: string | null;
  secret_id?: string | null;
  allow_pat_auth?: boolean;
  allow_standard_auth?: boolean;
  allow_connected_app_oauth?: boolean;
  eas_issuer_url?: string | null;
  eas_client_id?: string | null;
  eas_client_secret?: string | null;
  eas_authorization_endpoint?: string | null;
  eas_token_endpoint?: string | null;
  eas_sub_claim_field?: string | null;
  skip_ssl_verify?: boolean;
  ssl_cert_path?: string | null;
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
  apple_endor_app_id?: string;
  apple_endor_app_password?: string;
  apple_endor_other_app?: number;
  apple_endor_context?: string;
  apple_endor_one_time_token?: boolean;
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
  apple_endor_app_id?: string;
  apple_endor_app_password?: string;
  apple_endor_other_app?: number;
  apple_endor_context?: string;
  apple_endor_one_time_token?: boolean;
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
  apple_endor_app_id?: string | null;
  apple_endor_app_password?: string | null;
  apple_endor_other_app?: number | null;
  apple_endor_context?: string | null;
  apple_endor_one_time_token?: boolean | null;
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

export interface AuthConfigResponse {
  id: number;
  enable_password_auth: boolean;
  enable_oauth_auth: boolean;
  auth0_domain?: string | null;
  auth0_client_id?: string | null;
  auth0_client_secret?: string | null;
  auth0_audience?: string | null;
  auth0_issuer?: string | null;
  auth0_tableau_metadata_field?: string | null;
  backend_api_url?: string | null;
  tableau_oauth_frontend_redirect?: string | null;
  eas_jwt_key_configured: boolean;
  cors_origins?: string | null;
  mcp_server_name?: string | null;
  mcp_transport?: string | null;
  mcp_log_level?: string | null;
  redis_token_ttl?: number | null;
  resolved_cors_origins?: string | null;
  resolved_mcp_server_name?: string | null;
  resolved_mcp_transport?: string | null;
  resolved_mcp_log_level?: string | null;
  resolved_redis_token_ttl?: number | null;
  updated_by?: number | null;
  updated_at: string;
  created_at: string;
}

export interface AuthConfigUpdate {
  enable_password_auth?: boolean;
  enable_oauth_auth?: boolean;
  auth0_domain?: string;
  auth0_client_id?: string;
  auth0_client_secret?: string;
  auth0_audience?: string;
  auth0_issuer?: string;
  auth0_tableau_metadata_field?: string;
  backend_api_url?: string;
  tableau_oauth_frontend_redirect?: string;
  eas_jwt_key_pem?: string;
  cors_origins?: string;
  mcp_server_name?: string;
  mcp_transport?: string;
  mcp_log_level?: string;
  redis_token_ttl?: number;
}

// Agent Configuration interfaces
export interface AgentVersionResponse {
  version: string;
  is_enabled: boolean;
  is_default: boolean;
  description?: string | null;
}

export interface AgentConfigResponse {
  agent_name: string;
  versions: AgentVersionResponse[];
  default_version?: string | null;
}

export interface AgentVersionUpdate {
  is_enabled?: boolean;
  is_default?: boolean;
  description?: string;
}

export interface AgentSettingsResponse {
  agent_name: string;
  max_build_retries?: number | null;
  max_execution_retries?: number | null;
}

export interface AgentSettingsUpdate {
  max_build_retries?: number;
  max_execution_retries?: number;
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
      value_counts?: Array<{ value: string; count: number }>;
      min?: number | null;
      max?: number | null;
      median?: number | null;
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
      {
        params: { force_refresh: forceRefresh, include_statistics: includeStatistics },
        timeout: LONG_OPERATION_TIMEOUT,
      }
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

  updateUser: async (userId: number, userData: UserUpdate): Promise<UserResponse> => {
    const response = await apiClient.put<UserResponse>(`/api/v1/admin/users/${userId}`, userData);
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

  // User-Tableau Server Mapping management
  listUserTableauMappings: async (userId: number): Promise<UserTableauMappingResponse[]> => {
    const response = await apiClient.get<UserTableauMappingResponse[]>(`/api/v1/admin/users/${userId}/tableau-mappings`);
    return response.data;
  },

  createUserTableauMapping: async (userId: number, mappingData: UserTableauMappingCreate): Promise<UserTableauMappingResponse> => {
    const response = await apiClient.post<UserTableauMappingResponse>(`/api/v1/admin/users/${userId}/tableau-mappings`, mappingData);
    return response.data;
  },

  updateUserTableauMapping: async (userId: number, mappingId: number, mappingData: UserTableauMappingUpdate): Promise<UserTableauMappingResponse> => {
    const response = await apiClient.put<UserTableauMappingResponse>(`/api/v1/admin/users/${userId}/tableau-mappings/${mappingId}`, mappingData);
    return response.data;
  },

  deleteUserTableauMapping: async (userId: number, mappingId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/admin/users/${userId}/tableau-mappings/${mappingId}`);
  },

  // Auth configuration management
  getAuthConfig: async (): Promise<AuthConfigResponse> => {
    const response = await apiClient.get<AuthConfigResponse>('/api/v1/admin/auth-config');
    return response.data;
  },

  updateAuthConfig: async (configData: AuthConfigUpdate): Promise<AuthConfigResponse> => {
    const response = await apiClient.put<AuthConfigResponse>('/api/v1/admin/auth-config', configData);
    return response.data;
  },

  // Agent management
  listAgents: async (): Promise<Record<string, AgentVersionResponse[]>> => {
    const response = await apiClient.get<Record<string, AgentVersionResponse[]>>('/api/v1/admin/agents');
    return response.data;
  },

  getAgentVersions: async (agentName: string): Promise<AgentConfigResponse> => {
    const response = await apiClient.get<AgentConfigResponse>(`/api/v1/admin/agents/${agentName}`);
    return response.data;
  },

  getAgentSettings: async (agentName: string): Promise<AgentSettingsResponse> => {
    const response = await apiClient.get<AgentSettingsResponse>(`/api/v1/admin/agents/${agentName}/settings`);
    return response.data;
  },

  getAgentSystemPrompt: async (
    agentName: string,
    version?: string
  ): Promise<{ content: string }> => {
    const params = version ? { version } : {};
    const response = await apiClient.get<{ content: string }>(
      `/api/v1/admin/agents/${agentName}/system-prompt`,
      { params }
    );
    return response.data;
  },

  setActiveVersion: async (
    agentName: string,
    version: string
  ): Promise<AgentVersionResponse> => {
    const response = await apiClient.put<AgentVersionResponse>(
      `/api/v1/admin/agents/${agentName}/active-version`,
      { version }
    );
    return response.data;
  },

  updateAgentSettings: async (
    agentName: string,
    settings: AgentSettingsUpdate
  ): Promise<AgentSettingsResponse> => {
    const response = await apiClient.put<AgentSettingsResponse>(
      `/api/v1/admin/agents/${agentName}/settings`,
      settings
    );
    return response.data;
  },

  createAgentVersion: async (
    agentName: string,
    version: string,
    config: AgentVersionUpdate
  ): Promise<AgentVersionResponse> => {
    const response = await apiClient.post<AgentVersionResponse>(
      `/api/v1/admin/agents/${agentName}/versions/${version}`,
      config
    );
    return response.data;
  },
};

export default apiClient;
