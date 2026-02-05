// Shared TypeScript types
import { z } from 'zod';

/**
 * Message role type - defines who sent the message
 */
export type MessageRole = 'user' | 'assistant' | 'system';

/**
 * Message interface representing a single chat message
 * @property {string} id - Unique identifier for the message
 * @property {MessageRole} role - Role of the message sender
 * @property {string} content - The message content/text
 * @property {Date} createdAt - Timestamp when the message was created
 * @property {string} [modelUsed] - Optional identifier of the AI model used to generate this message
 */
export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: Date;
  modelUsed?: string;
  feedback?: string | null;
  feedbackText?: string | null;
  totalTimeMs?: number | null;
  vizqlQuery?: Record<string, any> | null;  // VizQL query used to generate the answer (for vizql agent)
}

/**
 * Conversation interface representing a chat session
 * @property {string} id - Unique identifier for the conversation
 * @property {Date} createdAt - Timestamp when the conversation was created
 * @property {Date} updatedAt - Timestamp when the conversation was last updated
 * @property {Message[]} messages - Array of messages in the conversation
 */
export interface Conversation {
  id: string;
  createdAt: Date;
  updatedAt: Date;
  messages: Message[];
}

// Zod validation schemas for runtime validation
export const MessageRoleSchema = z.enum(['user', 'assistant', 'system']);

export const MessageSchema = z.object({
  id: z.string().uuid(),
  role: MessageRoleSchema,
  content: z.string().min(1).max(100000), // Max 100KB content
  createdAt: z.coerce.date(),
  modelUsed: z.string().max(100).optional(),
});

export const ConversationSchema = z.object({
  id: z.string().uuid(),
  createdAt: z.coerce.date(),
  updatedAt: z.coerce.date(),
  messages: z.array(MessageSchema),
});

// Tableau types matching backend API models
export interface TableauDatasource {
  id: string;
  name: string;
  project_id?: string;
  project_name?: string;
  content_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TableauView {
  id: string;
  name: string;
  workbook_id?: string;
  workbook_name?: string;
  datasource_id?: string;
  content_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TableauEmbedUrl {
  view_id: string;
  workbook_id?: string;
  url: string;
  token?: string;
}

export interface TableauQueryRequest {
  datasource_id: string;
  filters?: Record<string, unknown>;
  columns?: string[];
  limit?: number;
}

export interface TableauQueryResponse {
  datasource_id: string;
  columns: string[];
  data: unknown[][];
  row_count: number;
}

// Agent types
export type AgentType = 'analyst' | 'vizql' | 'summary';

export interface VizQLQueryRequest {
  user_query: string;
  datasource_id: string;
}

export interface VizQLQueryResponse {
  vizql: string;
  explanation: string;
  valid: boolean;
  measures: string[];
  dimensions: string[];
  filters: Record<string, any>;
}

export interface VizQLExecuteRequest {
  datasource_id: string;
  vizql_query: string;
}

export interface VizQLExecuteResponse {
  data: unknown[][];
  columns: string[];
  row_count: number;
  vizql_query: string;
}

export interface ExportViewsRequest {
  view_ids: string[];
  format: 'json' | 'csv' | 'excel';
}

export interface ExportViewsResponse {
  datasets: Array<{
    view_id: string;
    data: unknown[][];
    columns: string[];
    row_count: number;
    format: string;
  }>;
  total_rows: number;
  view_count: number;
  format: string;
}

export interface GenerateSummaryRequest {
  view_ids: string[];
  format: 'html' | 'markdown' | 'pdf';
  include_visualizations?: boolean;
}

export interface GenerateSummaryResponse {
  content: string;
  format: string;
  visualizations: Array<{
    view_id: string;
    embed_url: string;
  }>;
  view_count: number;
  total_rows: number;
}

export interface AggregateViewsRequest {
  view_ids: string[];
  aggregation_type: 'sum' | 'avg' | 'count' | 'max' | 'min';
  column?: string;
}

export interface AggregateViewsResponse {
  total: number;
  by_view: Record<string, number>;
  aggregation_type: string;
  column?: string;
}

export interface ClassifyIntentRequest {
  query: string;
}

export interface ClassifyIntentResponse {
  agent: string;
  intent: string;
}

export interface RouteQueryRequest {
  query: string;
}

export interface RouteQueryResponse {
  agent: string;
  intent: string;
  result: Record<string, any>;
}

// Phase 5A: Object Explorer Types
export interface TableauProject {
  id: string;
  name: string;
  description?: string;
  parent_project_id?: string;
  content_permissions?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TableauWorkbook {
  id: string;
  name: string;
  project_id?: string;
  project_name?: string;
  content_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ProjectContents {
  project_id: string;
  datasources: TableauDatasource[];
  workbooks: TableauWorkbook[];
  projects: TableauProject[];
}

export interface ColumnSchema {
  name: string;
  data_type?: string;
  remote_type?: string;
  is_measure: boolean;
  is_dimension: boolean;
}

export interface DatasourceSchema {
  datasource_id: string;
  columns: ColumnSchema[];
}

export interface DatasourceSample {
  datasource_id: string;
  columns: string[];
  data: unknown[][];
  row_count: number;
  query?: {
    datasource: {
      datasourceLuid: string;
    };
    query: {
      fields: Array<{
        fieldCaption?: string;
        function?: string;
      }>;
    };
    options: {
      returnFormat: string;
      disaggregate: boolean;
    };
  };
}

// Phase 5B: Chat Context Types
export interface ChatContextObject {
  object_id: string;
  object_type: 'datasource' | 'view';
  object_name?: string;
  added_at: string;
}

export interface ChatContext {
  conversation_id: number;
  objects: ChatContextObject[];
}

export interface AddContextRequest {
  conversation_id: number;
  object_id: string;
  object_type: 'datasource' | 'view';
  object_name?: string;
}

export interface RemoveContextRequest {
  conversation_id: number;
  object_id: string;
}

// Agent Message Models
export type AgentMessageContentType = 'text' | 'image' | 'binary' | 'table' | 'json';

export interface AgentMessageContent {
  type: AgentMessageContentType;
  data: string | Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export type AgentMessageType = 'reasoning' | 'final_answer' | 'error' | 'progress' | 'metadata';

export interface AgentMessageChunk {
  message_type: AgentMessageType;
  content: AgentMessageContent;
  step_index?: number;
  step_name?: string;
  timestamp?: number;
  metadata?: Record<string, any>;
}
