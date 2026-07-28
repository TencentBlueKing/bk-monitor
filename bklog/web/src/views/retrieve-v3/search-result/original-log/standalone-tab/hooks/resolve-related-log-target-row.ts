import { parseTableRowData } from '@/common/util';
import { retrieveRowCacheService } from '@/storage';
import type { Store } from 'vuex';

export interface RelatedLogTargetRowOptions {
  rowKey?: string;
  fallbackRow?: Record<string, any>;
  contextFields?: string[];
  timeField?: string;
  isFormatDate?: boolean;
}

export interface RelatedLogTargetRowResult {
  /** 上下文/实时日志 API 请求参数 */
  row: Record<string, any>;
  /** IndexedDB 中的完整原始行 */
  fullRow: Record<string, any>;
}

export async function fetchFullRowByKey(rowKey?: string, fallbackRow?: Record<string, any>) {
  if (rowKey) {
    const [fullRow] = await retrieveRowCacheService.getRows([rowKey]);
    if (fullRow) return fullRow;
  }
  return fallbackRow;
}

export function buildRelatedLogParams(
  row: Record<string, any>,
  options: Omit<RelatedLogTargetRowOptions, 'rowKey' | 'fallbackRow'> = {},
) {
  const { contextFields, timeField, isFormatDate = false } = options;
  const params: Record<string, any> = {
    dtEventTimeStamp: row.dtEventTimeStamp,
  };

  if (Array.isArray(contextFields) && contextFields.length) {
    const targetContextFields = Array.from(new Set([...contextFields, timeField].filter(Boolean)));
    targetContextFields.forEach((field) => {
      if (field === 'bk_host_id') {
        if (row[field]) params[field] = row[field];
      } else {
        params[field] = parseTableRowData(row, field, '', isFormatDate, '');
      }
    });
  } else {
    Object.assign(params, row);
  }

  return params;
}

export function getRelatedLogIndexSetId(row: Record<string, any>, store: Store<any>) {
  const rowIndexSetId = row.__index_set_id__ ?? row.index_set_id;
  if (rowIndexSetId !== undefined && rowIndexSetId !== null && rowIndexSetId !== '') {
    return Number(rowIndexSetId);
  }

  if (store.getters.isSceneMode && row.__result_table) {
    const flatIndexSetList = store.state.retrieve?.flatIndexSetList ?? [];
    for (const indexSet of flatIndexSetList) {
      const matchedIndex = (indexSet.indices || []).find(
        (index: { result_table_id?: string }) => index.result_table_id === row.__result_table,
      );
      if (matchedIndex) {
        return matchedIndex.index_set_id;
      }
    }
  }

  const storeIndexId = store.getters.indexId;
  if (storeIndexId !== undefined && storeIndexId !== null && storeIndexId !== '') {
    return Number(storeIndexId);
  }

  return Number(store.getters.indexId || 0);
}

export async function resolveRelatedLogTargetRow(
  options: RelatedLogTargetRowOptions,
): Promise<RelatedLogTargetRowResult | null> {
  const fullRow = await fetchFullRowByKey(options.rowKey, options.fallbackRow);
  if (!fullRow || !Object.keys(fullRow).length) {
    return null;
  }

  return {
    fullRow,
    row: buildRelatedLogParams(fullRow, options),
  };
}

export function getRelatedLogResolveOptions(store: Store<any>): Omit<RelatedLogTargetRowOptions, 'rowKey' | 'fallbackRow'> {
  return {
    contextFields: store.state.indexSetOperatorConfig?.contextAndRealtime?.extra?.context_fields,
    timeField: store.state.indexFieldInfo?.time_field,
    isFormatDate: store.state.isFormatDate,
  };
}
