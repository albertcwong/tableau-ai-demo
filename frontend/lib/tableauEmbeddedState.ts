/**
 * Capture embedded Tableau dashboard/viz state for Summary Agent.
 * Uses Tableau Embedding API v3 (loaded with tableau-viz web component).
 */

export interface EmbeddedFilter {
  fieldName: string;
  filterType: string;
  appliedValues?: Array<{ value: string } | string>;
  minValue?: string;
  maxValue?: string;
}

export interface EmbeddedViewState {
  view_id: string;
  sheet_type: 'worksheet' | 'dashboard';
  active_sheet?: { name: string; sheetType: string };
  filters?: EmbeddedFilter[];
  summary_data?: { columns: string[]; data: unknown[][]; row_count: number };
  sheets_data?: Array<{
    sheet_name: string;
    sheet_index?: number;
    summary_data: { columns: string[]; data: unknown[][]; row_count: number };
  }>;
  captured_at: string;
  capture_error?: string; // Error message if capture failed
}

const MAX_SHEETS = 10;
const MAX_ROWS_PER_SHEET = 5000;

/** DataTable from Embedding API - columns have fieldId, data is row arrays */
interface DataTableLike {
  columns: Array<{ fieldId?: string; alias?: string }>;
  data: unknown[][];
  totalRowCount?: number;
}

function dataTableToSummary(table: DataTableLike): {
  columns: string[];
  data: unknown[][];
  row_count: number;
} {
  const columns = table.columns.map((c) => c.alias || c.fieldId || '');
  const data = (table.data || []).slice(0, MAX_ROWS_PER_SHEET);
  return {
    columns,
    data,
    row_count: data.length,
  };
}

/** Extract filters from Embedding API filter objects */
function extractFilters(filters: unknown[]): EmbeddedFilter[] {
  if (!Array.isArray(filters)) return [];
  return filters.map((f: unknown) => {
    const x = f as Record<string, unknown>;
    const fieldName = String(x.fieldName ?? x.field_name ?? '');
    const filterType = String(x.filterType ?? x.filter_type ?? '');
    const appliedValues = x.appliedValues ?? x.applied_values;
    const minValue = x.minValue ?? x.min_value;
    const maxValue = x.maxValue ?? x.max_value;
    const result: Partial<EmbeddedFilter> = {
      fieldName,
      filterType,
    };
    if (appliedValues && typeof appliedValues === 'object') {
      result.appliedValues = appliedValues as EmbeddedFilter['appliedValues'];
    }
    if (minValue != null) {
      result.minValue = String(minValue);
    }
    if (maxValue != null) {
      result.maxValue = String(maxValue);
    }
    return result as EmbeddedFilter;
  });
}

/** Capture state from a tableau-viz element */
export async function captureEmbeddedState(
  vizElement: HTMLElement | null,
  viewId: string
): Promise<EmbeddedViewState | null> {
  if (!vizElement) {
    console.warn(`[captureEmbeddedState] Viz element not found for view ${viewId}`);
    return null;
  }

  const viz = vizElement as unknown as {
    workbook?: {
      activeSheet?: {
        sheetType?: string;
        name?: string;
        getFiltersAsync?: () => Promise<unknown[]>;
        getSummaryDataReaderAsync?: (options?: { pageRowCount?: number }) => Promise<{
          getAllPagesAsync?: () => Promise<DataTableLike>;
          getPageAsync?: (i: number) => Promise<DataTableLike>;
          pageCount?: number;
          totalRowCount?: number;
          releaseAsync?: () => Promise<void>;
        }>;
        worksheets?: Array<{
          name?: string;
          getSummaryDataReaderAsync?: (options?: { pageRowCount?: number }) => Promise<{
            getAllPagesAsync?: () => Promise<DataTableLike>;
            getPageAsync?: (i: number) => Promise<DataTableLike>;
            pageCount?: number;
            totalRowCount?: number;
            releaseAsync?: () => Promise<void>;
          }>;
        }>;
      };
    };
  };

  if (typeof viz.workbook !== 'object') {
    console.warn(`[captureEmbeddedState] workbook not available for view ${viewId} - viz may not be interactive yet`);
    return null;
  }

  const workbook = viz.workbook;
  if (!workbook?.activeSheet) {
    console.warn(`[captureEmbeddedState] activeSheet not available for view ${viewId}`);
    return null;
  }

  const activeSheet = workbook.activeSheet;
  const sheetType = (activeSheet.sheetType === 'dashboard' ? 'dashboard' : 'worksheet') as
    | 'worksheet'
    | 'dashboard';

  const result: EmbeddedViewState = {
    view_id: viewId,
    sheet_type: sheetType,
    active_sheet: {
      name: activeSheet.name ?? '',
      sheetType: activeSheet.sheetType ?? sheetType,
    },
    captured_at: new Date().toISOString(),
  };

  // Skip getFiltersAsync - it returns 410 (Gone) when session is stale; summary agent doesn't use filters
  try {
    if (sheetType === 'worksheet') {
      const getReader = activeSheet.getSummaryDataReaderAsync;
      if (typeof getReader !== 'function') {
        console.warn(`[captureEmbeddedState] getSummaryDataReaderAsync not available for view ${viewId}`);
        result.capture_error = 'getSummaryDataReaderAsync method not available';
        return result;
      }

      try {
        // Use official pattern: no options for getAllPagesAsync (works for < 4M rows)
        const reader = await getReader.call(activeSheet);
        try {
          const getAllPages = reader.getAllPagesAsync;
          if (typeof getAllPages === 'function') {
            const table = await getAllPages.call(reader);
            if (table) {
              result.summary_data = dataTableToSummary(table);
              console.log(`[captureEmbeddedState] Successfully captured ${result.summary_data.row_count} rows for view ${viewId}`);
            } else {
              console.warn(`[captureEmbeddedState] getAllPagesAsync returned null for view ${viewId}`);
              result.capture_error = 'getAllPagesAsync returned no data';
            }
          } else if (reader.pageCount && reader.pageCount > 0 && reader.getPageAsync) {
            // Fallback for older API versions
            const table = await reader.getPageAsync.call(reader, 0);
            if (table) {
              result.summary_data = dataTableToSummary(table);
              console.log(`[captureEmbeddedState] Successfully captured ${result.summary_data.row_count} rows (page 0) for view ${viewId}`);
            } else {
              console.warn(`[captureEmbeddedState] getPageAsync(0) returned null for view ${viewId}`);
              result.capture_error = 'getPageAsync returned no data';
            }
          } else {
            console.warn(`[captureEmbeddedState] No data reader methods available for view ${viewId}`);
            result.capture_error = 'Data reader methods not available';
          }
        } finally {
          if (typeof reader.releaseAsync === 'function') {
            await reader.releaseAsync.call(reader);
          }
        }
      } catch (e) {
        const errorMsg = e instanceof Error ? e.message : String(e);
        console.error(`[captureEmbeddedState] Error calling getSummaryDataReaderAsync for view ${viewId}:`, e);
        result.capture_error = `Failed to get summary data: ${errorMsg}`;
      }
    } else if (sheetType === 'dashboard' && activeSheet.worksheets) {
      const worksheets = Array.isArray(activeSheet.worksheets)
        ? activeSheet.worksheets.slice(0, MAX_SHEETS)
        : [];
      result.sheets_data = [];

      // For tabbed dashboards: only capture the active tab (Worksheet.isActive)
      // If no worksheet is active (e.g. all tiled, no tabs), capture all
      const activeIndices = worksheets
        .map((ws, i) => (ws && (ws as { isActive?: boolean }).isActive ? i : -1))
        .filter((i) => i >= 0);
      const sheetsToCapture =
        activeIndices.length > 0 ? activeIndices : [...worksheets.keys()];

      for (const i of sheetsToCapture) {
        const ws = worksheets[i];
        const getReader = ws?.getSummaryDataReaderAsync;
        if (typeof getReader !== 'function') {
          console.warn(`[captureEmbeddedState] getSummaryDataReaderAsync not available for sheet ${i} in view ${viewId}`);
          continue;
        }

        try {
          // Use official pattern: no options for getAllPagesAsync
          const reader = await getReader.call(ws);
          try {
            const getAllPages = reader.getAllPagesAsync;
            let table: DataTableLike | null = null;
            if (typeof getAllPages === 'function') {
              table = await getAllPages.call(reader);
            } else if (reader.pageCount && reader.pageCount > 0 && reader.getPageAsync) {
              // Fallback for older API versions
              table = await reader.getPageAsync.call(reader, 0);
            }

            if (table) {
              const summaryData = dataTableToSummary(table);
              result.sheets_data!.push({
                sheet_name: ws.name ?? `Sheet_${i}`,
                sheet_index: i,
                summary_data: summaryData,
              });
              console.log(`[captureEmbeddedState] Successfully captured ${summaryData.row_count} rows for sheet ${i} (${ws.name}) in view ${viewId}`);
            } else {
              console.warn(`[captureEmbeddedState] No data returned for sheet ${i} in view ${viewId}`);
            }
          } finally {
            if (typeof reader.releaseAsync === 'function') {
              await reader.releaseAsync.call(reader);
            }
          }
        } catch (e) {
          const errorMsg = e instanceof Error ? e.message : String(e);
          console.error(`[captureEmbeddedState] Error getting data for sheet ${i} in view ${viewId}:`, e);
          // Continue with other sheets even if one fails
        }
      }
    }
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : String(e);
    console.error(`[captureEmbeddedState] Error capturing summary data for view ${viewId}:`, e);
    result.capture_error = `Failed to capture summary data: ${errorMsg}`;
  }

  return result;
}

function sanitizeViewId(viewId: string): string {
  return viewId.includes(',') ? viewId.split(',')[0].trim() : viewId;
}

/** Capture state for multiple views (finds viz by data-view-id or id). Viz elements use sanitized ids. */
export async function captureEmbeddedStateForViews(
  viewIds: string[]
): Promise<Record<string, EmbeddedViewState>> {
  const out: Record<string, EmbeddedViewState> = {};
  console.log(`[captureEmbeddedStateForViews] Attempting to capture ${viewIds.length} view(s):`, viewIds);
  
  for (const viewId of viewIds) {
    const cleanId = sanitizeViewId(viewId);
    // Try multiple selectors to find the viz element
    const selectors = [
      `[data-view-id="${CSS.escape(cleanId)}"]`,
      `[data-view-id="${CSS.escape(viewId)}"]`,
      `#tableau-viz-${cleanId}`,
      `#tableau-viz-${viewId}`,
    ];
    
    let el: HTMLElement | null = null;
    for (const selector of selectors) {
      el = document.querySelector(selector) as HTMLElement | null;
      if (el) {
        console.log(`[captureEmbeddedStateForViews] Found viz element for ${viewId} using selector: ${selector}`);
        break;
      }
    }
    
    if (!el) {
      console.warn(`[captureEmbeddedStateForViews] Viz element not found for view ${viewId}. Tried selectors:`, selectors);
      // Still create an entry with error so backend knows capture failed
      out[viewId] = {
        view_id: viewId,
        sheet_type: 'worksheet',
        captured_at: new Date().toISOString(),
        capture_error: `Viz element not found. Ensure the view is visible in the explorer.`,
      };
      continue;
    }
    
    const state = await captureEmbeddedState(el, viewId);
    if (state) {
      out[viewId] = state;
      if (state.capture_error) {
        console.warn(`[captureEmbeddedStateForViews] Capture failed for view ${viewId}: ${state.capture_error}`);
      }
    } else {
      // captureEmbeddedState returned null - create entry with error
      out[viewId] = {
        view_id: viewId,
        sheet_type: 'worksheet',
        captured_at: new Date().toISOString(),
        capture_error: 'Failed to capture embedded state (workbook or activeSheet not available)',
      };
    }
  }
  
  const successCount = Object.values(out).filter(s => !s.capture_error && (s.summary_data || s.sheets_data)).length;
  console.log(`[captureEmbeddedStateForViews] Capture complete: ${successCount}/${viewIds.length} views captured successfully`);
  
  return out;
}
