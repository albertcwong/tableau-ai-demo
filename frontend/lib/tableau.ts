// Tableau utilities and helpers
import apiClient from './api';
import type {
  TableauDatasource,
  TableauView,
  TableauEmbedUrl,
  TableauQueryRequest,
  TableauQueryResponse,
} from '@/types';

/**
 * Fetch list of datasources from the backend API
 */
export async function getDatasources(
  projectId?: string,
  pageSize = 100,
  pageNumber = 1
): Promise<TableauDatasource[]> {
  const params = new URLSearchParams({
    page_size: pageSize.toString(),
    page_number: pageNumber.toString(),
  });
  if (projectId) {
    params.append('project_id', projectId);
  }

  const response = await apiClient.get<TableauDatasource[]>(
    `/api/v1/tableau/datasources?${params.toString()}`
  );
  return response.data;
}

/**
 * Fetch list of views from the backend API
 */
export async function getViews(
  datasourceId?: string,
  workbookId?: string,
  pageSize = 100,
  pageNumber = 1
): Promise<TableauView[]> {
  const params = new URLSearchParams({
    page_size: pageSize.toString(),
    page_number: pageNumber.toString(),
  });
  if (datasourceId) {
    params.append('datasource_id', datasourceId);
  }
  if (workbookId) {
    params.append('workbook_id', workbookId);
  }

  const response = await apiClient.get<TableauView[]>(
    `/api/v1/tableau/views?${params.toString()}`
  );
  return response.data;
}

/**
 * Get embed URL for a Tableau view
 */
/** Strip Tableau internal suffixes (e.g. ,1:0, ,1:1) that cause "Error parsing command parameter value string". */
export function sanitizeViewId(viewId: string): string {
  return viewId.includes(',') ? viewId.split(',')[0].trim() : viewId;
}

export async function getViewEmbedUrl(
  viewId: string,
  filters?: Record<string, string>
): Promise<TableauEmbedUrl> {
  const cleanId = sanitizeViewId(viewId);
  const params = new URLSearchParams();
  if (filters) {
    params.append('filters', JSON.stringify(filters));
  }

  const response = await apiClient.get<TableauEmbedUrl>(
    `/api/v1/tableau/views/${cleanId}/embed-url${params.toString() ? `?${params.toString()}` : ''}`
  );
  return response.data;
}

/**
 * Query a datasource
 */
export async function queryDatasource(
  request: TableauQueryRequest
): Promise<TableauQueryResponse> {
  const response = await apiClient.post<TableauQueryResponse>(
    '/api/v1/tableau/query',
    request
  );
  return response.data;
}
