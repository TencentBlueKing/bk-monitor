import { computed, nextTick, onBeforeUnmount, ref, type Ref } from 'vue';

import $http from '@/api';
import { getFlatObjValues } from '@/common/util';
import useFieldNameHook from '@/hooks/use-field-name';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { retrieveRowCacheService } from '@/storage';
import { createRetrieveRowRenderMeta } from '@/storage/utils/retrieve-render-meta';

import { getDefaultDisplayFields } from '../../components/data-filter/fields-config/default-display-fields';

export type DisplayMode = 'log' | 'code';

export interface RelatedLogCommonOptions {
  indexSetId: Ref<number>;
  targetRow: Ref<Record<string, any>>;
  targetFields?: Ref<string[]>;
}

export const stripMark = (value: string) => value.replace(/<mark>/g, '').replace(/<\/mark>/g, '');

export const normalizeDisplayValue = (value: any) => {
  if (value === null || value === undefined) return ' ';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return value;
};

export const flattenLogParams = (row: Record<string, any>) => {
  const params: Record<string, string> = {};

  const walk = (obj: any, prefix = '') => {
    if (obj === null || obj === undefined) {
      if (prefix) params[prefix] = '';
      return;
    }

    Object.keys(obj).forEach((key) => {
      const prefixKey = prefix ? `${prefix}.${key}` : key;
      const value = obj[key];
      if (value && typeof value === 'object' && !value._isBigNumber) {
        walk(value, prefixKey);
        return;
      }
      params[prefixKey] = stripMark(value?._isBigNumber ? value.toString() : String(value ?? ''));
    });
  };

  walk(row);
  return params;
};

export const useCommonRelatedLog = (options: RelatedLogCommonOptions) => {
  const store = useStore();
  const { t } = useLocale();
  const { changeFieldName } = useFieldNameHook({ store });

  const logViewRef = ref<any>();
  const dataFilterRef = ref<any>();
  const scrollerRef = ref<HTMLElement>();
  const loading = ref(false);
  const logList = ref<any[]>([]);
  const reverseLogList = ref<any[]>([]);
  const filterType = ref('include');
  const activeFilterKey = ref<string[]>([]);
  const ignoreCase = ref(false);
  const showType = ref<DisplayMode>('log');
  const highlightList = ref<any[]>([]);
  const interval = ref({ prev: 0, next: 0 });
  const isFilterEmpty = ref(false);
  const paramsInfo = ref<Record<string, any>>(flattenLogParams(options.targetRow.value));

  let rawList: any[] = [];
  let reverseRawList: any[] = [];
  let relatedQueryKey = '';
  let relatedSeq = 0;
  let displayFieldNames: string[] = [];
  let filterCheckTimer: ReturnType<typeof setTimeout> | undefined;
  let filterResetTimer: ReturnType<typeof setTimeout> | undefined;
  let highlightTimer: ReturnType<typeof setTimeout> | undefined;

  const targetFields = computed(() => options.targetFields?.value || []);

  const getShowFieldNames = () => displayFieldNames.length
    ? displayFieldNames
    : getDefaultDisplayFields(store, store.state.retrieve.catchFieldCustomConfig?.contextDisplayFields);

  const getDisplayFieldValue = (row: Record<string, any>, flatRow: Record<string, any>, field: string) => {
    const realField = changeFieldName(field);
    return normalizeDisplayValue(flatRow[realField] ?? row[realField] ?? row[field] ?? flatRow[field]);
  };

  const writeRowsToCache = async (rows: any[], renderRows?: any[]) => {
    if (!rows.length) return [];
    if (!relatedQueryKey) {
      relatedQueryKey = retrieveRowCacheService.createQueryKey({
        standalone: 'related-log-stream',
        indexSetId: options.indexSetId.value,
        seed: options.targetRow.value?.dtEventTimeStamp,
      });
      relatedSeq = 0;
    }
    const fieldNames = getShowFieldNames();
    const renderMetas = rows.map((row, index) => createRetrieveRowRenderMeta(row, renderRows?.[index]));
    const keys = await retrieveRowCacheService.appendRows(relatedQueryKey, rows, relatedSeq, {
      fieldNames,
      renderRows,
      renderMetas,
    });
    relatedSeq += rows.length;
    return keys;
  };

  const formatList = (list: any[], fields = getShowFieldNames()) => list.map((row) => {
    const displayObj = {};
    const { newObject } = getFlatObjValues(row);
    fields.forEach((field) => {
      Object.assign(displayObj, {
        [field]: getDisplayFieldValue(row, newObject, field),
      });
    });
    return displayObj;
  });

  const resetLogs = () => {
    if (relatedQueryKey) {
      retrieveRowCacheService.clearQuery(relatedQueryKey).catch((error) => {
        console.warn('[related-log] clear query rows failed', error);
      });
    }
    logList.value = [];
    reverseLogList.value = [];
    rawList = [];
    reverseRawList = [];
    relatedQueryKey = '';
    relatedSeq = 0;
    isFilterEmpty.value = false;
  };

  const setRawLists = (normalRows: any[], reverseRows: any[] = []) => {
    rawList = normalRows;
    reverseRawList = reverseRows;
    logList.value = formatList(rawList);
    reverseLogList.value = formatList(reverseRawList);
    writeRowsToCache(reverseRows.concat(normalRows), reverseLogList.value.concat(logList.value)).catch((error) => {
      console.warn('[related-log] cache rows failed', error);
    });
  };

  const appendRawRows = (rows: any[]) => {
    const renderRows = formatList(rows);
    rawList.push(...rows);
    logList.value.push(...renderRows);
    writeRowsToCache(rows, renderRows).catch((error) => {
      console.warn('[related-log] cache append rows failed', error);
    });
  };

  const prependReverseRows = (rows: any[]) => {
    const renderRows = formatList(rows);
    reverseRawList.unshift(...rows);
    reverseLogList.value.unshift(...renderRows);
    writeRowsToCache(rows, renderRows).catch((error) => {
      console.warn('[related-log] cache prepend rows failed', error);
    });
  };

  const handleFieldsConfigUpdate = (fields: string[]) => {
    displayFieldNames = fields;
    logList.value = formatList(rawList, fields);
    reverseLogList.value = formatList(reverseRawList, fields);
  };

  const checkFilterEmpty = () => {
    clearTimeout(filterCheckTimer);
    filterCheckTimer = setTimeout(() => {
      const lineDomList = Array.from(logViewRef.value?.$el?.querySelectorAll('.line') || []) as HTMLElement[];
      isFilterEmpty.value = !!lineDomList.length && lineDomList.every(item => item.style.display === 'none');
    });
  };

  const initHighlight = (direction?: string) => {
    clearTimeout(highlightTimer);
    if (!highlightList.value.length) return;
    highlightTimer = setTimeout(() => {
      dataFilterRef.value?.getHighlightControl?.()?.initLightItemList(direction);
    });
  };

  const scrollToCurrentRow = () => {
    nextTick(() => {
      const current = scrollerRef.value?.querySelector('.log-init') as HTMLElement;
      if (!current || !scrollerRef.value) return;
      const wrapperHeight = scrollerRef.value.offsetHeight;
      const targetTop = wrapperHeight <= current.scrollHeight
        ? current.offsetTop
        : current.offsetTop - Math.ceil((wrapperHeight - current.scrollHeight) / 2);
      scrollerRef.value.scrollTo({ top: targetTop, behavior: 'smooth' });
    });
  };

  const handleFilter = (field: string, value: any) => {
    switch (field) {
      case 'filterKey':
        activeFilterKey.value = value;
        clearTimeout(filterResetTimer);
        filterResetTimer = setTimeout(() => {
          if (!value.length) scrollToCurrentRow();
          checkFilterEmpty();
        }, 300);
        break;
      case 'showType':
        showType.value = value;
        break;
      case 'ignoreCase':
        ignoreCase.value = value;
        break;
      case 'interval':
        interval.value = value;
        break;
      case 'filterType':
        filterType.value = value;
        break;
      default:
        highlightList.value = value;
        initHighlight();
    }
  };

  const request = async (url: string, data: Record<string, any>, requestId?: string) => {
    loading.value = true;
    try {
      return await $http.request(url, {
        params: { index_set_id: options.indexSetId.value },
        data,
      }, {
        catchIsShowMessage: false,
        requestId,
      });
    } finally {
      loading.value = false;
    }
  };

  const disposeCommon = () => {
    clearTimeout(filterCheckTimer);
    clearTimeout(filterResetTimer);
    clearTimeout(highlightTimer);
    // 卸载时清掉日志缓存，避免残留 query 占用
    resetLogs();
  };

  onBeforeUnmount(disposeCommon);

  return {
    t,
    store,
    logViewRef,
    dataFilterRef,
    scrollerRef,
    loading,
    logList,
    reverseLogList,
    filterType,
    activeFilterKey,
    ignoreCase,
    showType,
    highlightList,
    interval,
    isFilterEmpty,
    paramsInfo,
    targetFields,
    rawList: () => rawList,
    reverseRawList: () => reverseRawList,
    formatList,
    resetLogs,
    setRawLists,
    appendRawRows,
    prependReverseRows,
    handleFieldsConfigUpdate,
    handleFilter,
    scrollToCurrentRow,
    initHighlight,
    request,
    disposeCommon,
  };
};
