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

/** DataTable from Embedding API - columns have fieldId/alias, rows are arrays of DataValue */
interface DataTableLike {
  columns: Array<{ fieldId?: string; alias?: string }>;
  data: unknown[][];
  totalRowCount?: number;
}

/** DataValue returned by Tableau Embedding API v3 — each cell has value + formattedValue */
interface DataValue {
  value?: unknown;
  formattedValue?: string;
  [key: string]: unknown;
}

/** Extract a readable scalar from a Tableau DataValue cell */
function extractCellValue(cell: unknown): unknown {
  if (cell !== null && typeof cell === 'object') {
    const dv = cell as DataValue;
    // Prefer formattedValue (e.g. "$1,234.56"), fall back to raw value
    if (dv.formattedValue !== undefined && dv.formattedValue !== null && dv.formattedValue !== '') {
      return dv.formattedValue;
    }
    if (dv.value !== undefined) return dv.value;
  }
  return cell;
}

function dataTableToSummary(table: DataTableLike): {
  columns: string[];
  data: unknown[][];
  row_count: number;
} {
  const columns = table.columns.map((c) => c.alias || c.fieldId || '');
  const rawRows = (table.data || []).slice(0, MAX_ROWS_PER_SHEET);
  // Extract readable values from each DataValue cell
  const data = rawRows.map((row) =>
    Array.isArray(row) ? row.map(extractCellValue) : [extractCellValue(row)]
  );
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
        // Simple direct API (preferred — matches Tableau Extensions API pattern)
        getSummaryDataAsync?: (options?: {
          maxRows?: number;
          ignoreAliases?: boolean;
          ignoreSelection?: boolean;
          includeAllColumns?: boolean;
        }) => Promise<DataTableLike>;
        // Streaming reader API (fallback)
        getSummaryDataReaderAsync?: (options?: { pageRowCount?: number }) => Promise<{
          getAllPagesAsync?: () => Promise<DataTableLike>;
          getPageAsync?: (i: number) => Promise<DataTableLike>;
          pageCount?: number;
          totalRowCount?: number;
          releaseAsync?: () => Promise<void>;
        }>;
        worksheets?: Array<{
          name?: string;
          isActive?: boolean;
          getSummaryDataAsync?: (options?: {
            maxRows?: number;
            ignoreAliases?: boolean;
            ignoreSelection?: boolean;
            includeAllColumns?: boolean;
          }) => Promise<DataTableLike>;
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

  // Read sheetType ONCE and cache it — the getter is a proxy call into the Tableau SDK.
  // Re-accessing the same getter can surface a deferred internal error from the first call
  // (e.g. "create-summary-data-table-reader") as a synchronous throw on the second access.
  let sheetType: 'worksheet' | 'dashboard';
  let sheetName = '';
  try {
    sheetType = (activeSheet.sheetType === 'dashboard' ? 'dashboard' : 'worksheet');
    sheetName = activeSheet.name ?? '';
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : String(e);
    console.error(`[captureEmbeddedState] Error reading activeSheet properties for view ${viewId}:`, e);
    return {
      view_id: viewId,
      sheet_type: 'worksheet',
      captured_at: new Date().toISOString(),
      capture_error: `Viz session not ready — try again after the view finishes loading: ${errorMsg}`,
    };
  }

  const result: EmbeddedViewState = {
    view_id: viewId,
    sheet_type: sheetType,
    active_sheet: {
      name: sheetName,
      sheetType: sheetType,  // reuse cached value — never re-access the proxy getter
    },
    captured_at: new Date().toISOString(),
  };

  // Skip getFiltersAsync - it returns 410 (Gone) when session is stale; summary agent doesn't use filters
  const SUMMARY_OPTIONS = {
    maxRows: 0,           // 0 = all rows
    ignoreAliases: false,
    ignoreSelection: true,
    includeAllColumns: false,
  };

  /**
   * Get summary data from a single worksheet.
   * Tries getSummaryDataAsync first (simpler, more compatible with this Tableau version),
   * then falls back to getSummaryDataReaderAsync if not available.
   */
  async function getSheetSummary(sheet: NonNullable<typeof activeSheet>, label: string): Promise<DataTableLike | null> {
    // --- Primary: getSummaryDataAsync (simple, direct, per user reference code) ---
    const getDirect = (sheet as typeof activeSheet & { getSummaryDataAsync?: (o?: typeof SUMMARY_OPTIONS) => Promise<DataTableLike> }).getSummaryDataAsync;
    if (typeof getDirect === 'function') {
      try {
        const table = await getDirect.call(sheet, SUMMARY_OPTIONS);
        if (table) {
          console.log(`[captureEmbeddedState] getSummaryDataAsync succeeded for ${label}: ${table.data?.length ?? 0} rows`);
          return table;
        }
      } catch (e) {
        console.warn(`[captureEmbeddedState] getSummaryDataAsync failed for ${label}, trying reader:`, e);
      }
    }

    // --- Fallback: getSummaryDataReaderAsync ---
    const getReader = (sheet as typeof activeSheet & { getSummaryDataReaderAsync?: (o?: { pageRowCount?: number }) => Promise<{ getAllPagesAsync?: () => Promise<DataTableLike>; getPageAsync?: (i: number) => Promise<DataTableLike>; pageCount?: number; releaseAsync?: () => Promise<void> }> }).getSummaryDataReaderAsync;
    if (typeof getReader !== 'function') {
      console.warn(`[captureEmbeddedState] No data fetch method available for ${label}`);
      return null;
    }
    const reader = await getReader.call(sheet);
    try {
      const getAllPages = reader.getAllPagesAsync;
      if (typeof getAllPages === 'function') {
        const table = await getAllPages.call(reader);
        if (table) {
          console.log(`[captureEmbeddedState] getSummaryDataReaderAsync succeeded for ${label}: ${table.data?.length ?? 0} rows`);
          return table;
        }
      } else if (reader.pageCount && reader.pageCount > 0 && reader.getPageAsync) {
        const table = await reader.getPageAsync.call(reader, 0);
        if (table) {
          console.log(`[captureEmbeddedState] getPageAsync(0) succeeded for ${label}: ${table.data?.length ?? 0} rows`);
          return table;
        }
      }
    } finally {
      if (typeof reader.releaseAsync === 'function') {
        await reader.releaseAsync.call(reader);
      }
    }
    return null;
  }

  try {
    if (sheetType === 'worksheet') {
      try {
        const table = await getSheetSummary(activeSheet, `view ${viewId}`);
        if (table) {
          result.summary_data = dataTableToSummary(table);
          console.log(`[captureEmbeddedState] Captured ${result.summary_data.row_count} rows for view ${viewId}`);
        } else {
          result.capture_error = 'No data returned from worksheet';
        }
      } catch (e) {
        const errorMsg = e instanceof Error ? e.message : String(e);
        console.error(`[captureEmbeddedState] Error capturing worksheet data for view ${viewId}:`, e);
        result.capture_error = `Failed to get summary data: ${errorMsg}`;
      }
    } else if (sheetType === 'dashboard') {
      // Accessing activeSheet.worksheets is also a proxy getter — read it once inside try
      let rawWorksheets: typeof activeSheet.worksheets;
      try {
        rawWorksheets = activeSheet.worksheets;
      } catch (e) {
        const errorMsg = e instanceof Error ? e.message : String(e);
        console.error(`[captureEmbeddedState] Error reading dashboard worksheets for view ${viewId}:`, e);
        result.capture_error = `Could not read dashboard worksheets: ${errorMsg}`;
        return result;
      }

      const worksheets = Array.isArray(rawWorksheets)
        ? rawWorksheets.slice(0, MAX_SHEETS)
        : [];
      result.sheets_data = [];

      // Cache per-worksheet metadata (name, isActive) in a single try per ws —
      // these are proxy getters that can throw independently.
      interface WsInfo { ws: typeof worksheets[0]; name: string; isActive: boolean; index: number }
      const wsInfos: WsInfo[] = [];
      for (let i = 0; i < worksheets.length; i++) {
        const ws = worksheets[i];
        if (!ws) continue;
        try {
          wsInfos.push({ ws, name: ws.name ?? `Sheet_${i}`, isActive: ws.isActive ?? false, index: i });
        } catch {
          // Skip worksheets whose metadata can't be read
          console.warn(`[captureEmbeddedState] Could not read metadata for sheet ${i} in view ${viewId}`);
        }
      }

      // For tabbed dashboards: only capture the active tab (Worksheet.isActive)
      // If no worksheet is active (e.g. all tiled, no tabs), capture all
      const activeInfos = wsInfos.filter((w) => w.isActive);
      const toCapture = activeInfos.length > 0 ? activeInfos : wsInfos;

      for (const { ws, name, index } of toCapture) {
        try {
          const table = await getSheetSummary(ws as typeof activeSheet, `sheet ${index} (${name}) in view ${viewId}`);
          if (table) {
            const summaryData = dataTableToSummary(table);
            result.sheets_data!.push({
              sheet_name: name,
              sheet_index: index,
              summary_data: summaryData,
            });
            console.log(`[captureEmbeddedState] Captured ${summaryData.row_count} rows for sheet ${index} (${name}) in view ${viewId}`);
          } else {
            console.warn(`[captureEmbeddedState] No data returned for sheet ${index} in view ${viewId}`);
          }
        } catch (e) {
          const errorMsg = e instanceof Error ? e.message : String(e);
          console.error(`[captureEmbeddedState] Error getting data for sheet ${index} in view ${viewId}:`, e);
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
