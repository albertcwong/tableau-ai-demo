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
    return {
      fieldName,
      filterType,
      ...(appliedValues && { appliedValues: appliedValues as EmbeddedFilter['appliedValues'] }),
      ...(minValue != null && { minValue: String(minValue) }),
      ...(maxValue != null && { maxValue: String(maxValue) }),
    };
  });
}

/** Capture state from a tableau-viz element */
export async function captureEmbeddedState(
  vizElement: HTMLElement | null,
  viewId: string
): Promise<EmbeddedViewState | null> {
  if (!vizElement || typeof (vizElement as Record<string, unknown>).workbook !== 'object') {
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

  const workbook = viz.workbook;
  if (!workbook?.activeSheet) return null;

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

  try {
    const getFilters = activeSheet.getFiltersAsync;
    if (typeof getFilters === 'function') {
      const filters = await getFilters.call(activeSheet);
      result.filters = extractFilters(Array.isArray(filters) ? filters : []);
    }
  } catch (e) {
    console.warn('Could not get filters:', e);
  }

  try {
    if (sheetType === 'worksheet') {
      const getReader = activeSheet.getSummaryDataReaderAsync;
      if (typeof getReader === 'function') {
        const reader = await getReader.call(activeSheet, { pageRowCount: 10000 });
        try {
          const getAllPages = reader.getAllPagesAsync;
          const table = typeof getAllPages === 'function'
            ? await getAllPages.call(reader)
            : reader.pageCount && reader.pageCount > 0 && reader.getPageAsync
              ? await reader.getPageAsync.call(reader, 0)
              : null;
          if (table) {
            result.summary_data = dataTableToSummary(table);
          }
        } finally {
          if (typeof reader.releaseAsync === 'function') {
            await reader.releaseAsync.call(reader);
          }
        }
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
        if (typeof getReader !== 'function') continue;

        try {
          const reader = await getReader.call(ws, { pageRowCount: 5000 });
          try {
            const getAllPages = reader.getAllPagesAsync;
            const table = typeof getAllPages === 'function'
              ? await getAllPages.call(reader)
              : reader.pageCount && reader.pageCount > 0 && reader.getPageAsync
                ? await reader.getPageAsync.call(reader, 0)
                : null;
            if (table) {
              result.sheets_data!.push({
                sheet_name: ws.name ?? `Sheet_${i}`,
                sheet_index: i,
                summary_data: dataTableToSummary(table),
              });
            }
          } finally {
            if (typeof reader.releaseAsync === 'function') {
              await reader.releaseAsync.call(reader);
            }
          }
        } catch (e) {
          console.warn(`Could not get data for sheet ${i}:`, e);
        }
      }
    }
  } catch (e) {
    console.warn('Could not get summary data:', e);
  }

  return result;
}

/** Capture state for multiple views (finds viz by data-view-id or id) */
export async function captureEmbeddedStateForViews(
  viewIds: string[]
): Promise<Record<string, EmbeddedViewState>> {
  const out: Record<string, EmbeddedViewState> = {};
  for (const viewId of viewIds) {
    const el =
      document.querySelector(`[data-view-id="${CSS.escape(viewId)}"]`) ||
      document.getElementById(`tableau-viz-${viewId}`);
    const state = await captureEmbeddedState(el as HTMLElement, viewId);
    if (state) {
      out[viewId] = state;
    }
  }
  return out;
}
