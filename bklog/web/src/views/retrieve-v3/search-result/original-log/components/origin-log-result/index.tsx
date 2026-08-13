/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { defineComponent, ref, watch, computed, onMounted, onBeforeUnmount } from 'vue';

import JsonFormatter from '@/global/json-formatter.vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import SearchBar from '@/views/retrieve-v2/search-bar/index.vue';
import { cloneDeep, debounce } from 'lodash-es';
import RetrieveHelper from '@/views/retrieve-helper';
import { buildHighlightHtml, parseResultMarkedText } from '@/views/retrieve-core/page-highlight';
import { relatedLogSearchRowCacheService, retrieveRowCacheService, retrieveSearchWorkerService } from '@/storage';
import type { SearchStreamProgress } from '@/storage/services/retrieve-search-worker.service';
import type { RetrieveRowRenderMeta } from '@/storage/utils/retrieve-render-meta';
import { normalizeSearchTotal } from '@/storage/utils/normalize-search-total';
import { resolveAddToSearch } from '@/hooks/log-query-compiler';

import RenderJsonCell from './render-json-cell';
import { buildOriginLogSearchFieldPayload, buildOriginLogSearchHeaders } from './build-origin-log-search-fields';
import {
  buildOriginLogLocalQuerySeed,
  resolveLocalStoredRowCountAfterResult,
  resolveOriginLogStreamMode,
} from './resolve-origin-log-stream-mode';

import './index.scss';

export default defineComponent({
  name: 'LogResult',
  props: {
    indexSetId: {
      type: Number,
      default: 0,
    },
    logIndex: {
      type: Number,
      default: 0,
    },
    retrieveParams: {
      type: Object,
      required: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const searchBarRef = ref<any>();
    const tableRef = ref<HTMLElement>();
    const logList = ref<any[]>([]);
    const renderMetaList = ref<(RetrieveRowRenderMeta | undefined)[]>([]);
    const cachedRowKeys = ref<string[]>([]);
    const choosedIndex = ref(props.logIndex);
    const listLoading = ref(false);
    const isCollapsed = ref(false);
    const exceptionMsg = ref('');

    const fieldsMap = computed(() => store.getters.rawFieldList.reduce((dataMap, item) => {
      dataMap[item.field_name] = item;
      return dataMap;
    }, {}),
    );

    const timeField = computed(() => store.state.indexFieldInfo.time_field);
    const timeFieldType = computed(() => fieldsMap.value[timeField.value]?.field_type);
    const visibleFields = computed(() => store.getters.visibleFields);

    const requestOtherparams = cloneDeep(props.retrieveParams);
    delete requestOtherparams.format;

    // 隐藏掉tippy弹出框中的非必要按钮
    const styleContent = `
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(1),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(2),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(5) {
        display: none !important;
      }
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(3),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(4) {
        .segment-new-link {
          display: none !important;
        }
      }
    `;

    let styleElement: any = null;
    let begin = 0;
    const size = 50;
    let total = 0;
    let isUnmounted = false;
    let requestSeq = 0;
    /** 本地 Stream 独立 queryKey，禁止与主检索 row_keys 混用 */
    let localQueryKey = '';
    /** 当前 localQueryKey 已写入的行数（不含主检索种子 keys） */
    let localStoredRowCount = 0;
    let activeLocalSearchRequestId = '';
    let scrollIntoViewTimer: ReturnType<typeof setTimeout> | null = null;
    let appliedStreamRowCount = 0;

    const isMonitorApm = window.__IS_MONITOR_APM__;

    watch(
      () => props.logIndex,
      () => {
        choosedIndex.value = props.logIndex;
      },
      {
        immediate: true,
      },
    );

    const setExceptionMsg = (message = '') => {
      exceptionMsg.value = message || '';
    };

    const isRequestCanceled = (error: any) => error?.code === 'ERR_CANCELED'
      || error?.name === 'CanceledError'
      || error?.name === 'AbortError'
      || error?.message === 'Search request canceled';

    /** 取消进行中的本地 Stream，不影响主检索 requestId */
    const cancelPendingRequest = () => {
      if (!activeLocalSearchRequestId) {
        return;
      }
      retrieveSearchWorkerService.cancelSearch(activeLocalSearchRequestId);
      activeLocalSearchRequestId = '';
    };

    const clearLocalQueryCache = () => {
      if (!localQueryKey) {
        localStoredRowCount = 0;
        appliedStreamRowCount = 0;
        return;
      }
      const key = localQueryKey;
      localQueryKey = '';
      localStoredRowCount = 0;
      appliedStreamRowCount = 0;
      // 本地检索只清理 relatedLogSearchRows，绝不碰主检索 retrieveRows
      relatedLogSearchRowCacheService.releaseQuery(key);
      relatedLogSearchRowCacheService.clearQuery(key).catch((error) => {
        console.warn('[origin-log-result] clear local query rows failed', error);
      });
    };

    /** 将尚未展示的 rowKeys 增量读入 UI（仅追加未缓存 key） */
    const appendLocalRenderEntries = async (rowKeys: string[]) => {
      if (!rowKeys.length) return 0;
      const existing = new Set(cachedRowKeys.value);
      const nextKeys = rowKeys.filter(key => !existing.has(key));
      if (!nextKeys.length) return 0;
      const entries = await relatedLogSearchRowCacheService.getRenderEntries(nextKeys);
      const rows: any[] = [];
      const metas: (RetrieveRowRenderMeta | undefined)[] = [];
      const keys: string[] = [];
      nextKeys.forEach((key, index) => {
        const entry = entries[index];
        if (!entry?.row) return;
        keys.push(key);
        rows.push(entry.row);
        metas.push(entry.renderMeta);
      });
      if (!rows.length) return 0;
      logList.value.push(...rows);
      renderMetaList.value.push(...metas);
      cachedRowKeys.value.push(...keys);
      return rows.length;
    };

    /**
     * 同步本地渲染列表。
     * - replace：progress/finish 的 rowKeys 为本次 writer 全量 keys（从 0 递增）
     * - append：Worker writer 仅返回本页新增 keys
     */
    const syncLocalRenderList = async (rowKeys: string[], mode: 'replace' | 'append') => {
      if (mode === 'append') {
        const added = await appendLocalRenderEntries(rowKeys);
        localStoredRowCount += added;
        return;
      }

      const nextKeys = rowKeys.slice(appliedStreamRowCount);
      const added = await appendLocalRenderEntries(nextKeys);
      appliedStreamRowCount += added;
      localStoredRowCount = Math.max(localStoredRowCount, appliedStreamRowCount);

      if (appliedStreamRowCount < rowKeys.length) {
        const missingKeys = rowKeys.slice(appliedStreamRowCount);
        const filled = await appendLocalRenderEntries(missingKeys);
        appliedStreamRowCount += filled;
        localStoredRowCount = Math.max(localStoredRowCount, appliedStreamRowCount);
      }
    };

    const requestLogList = async (isManualSearch = true) => {
      // 新请求发起前先取消旧请求，避免乱序回写
      cancelPendingRequest();
      requestSeq += 1;
      const currentRequestSeq = requestSeq;
      const { isStorageAppend, syncMode, uiMode, writeMode } = resolveOriginLogStreamMode({
        begin,
        hasLocalQueryKey: !!localQueryKey,
        isManualSearch,
      });

      listLoading.value = true;
      if (!isStorageAppend) {
        setExceptionMsg('');
        appliedStreamRowCount = 0;
        if (localQueryKey) {
          clearLocalQueryCache();
        }
        localStoredRowCount = 0;
        localQueryKey = relatedLogSearchRowCacheService.createQueryKey(
          buildOriginLogLocalQuerySeed({
            addition: requestOtherparams.addition,
            indexSetId: props.indexSetId,
            keyword: requestOtherparams.keyword,
            searchMode: requestOtherparams.search_mode,
            seq: currentRequestSeq,
          }),
        );
      }

      const requestQueryKey = localQueryKey;
      const requestStartSeq = isStorageAppend ? localStoredRowCount : 0;
      const baseUrl = process.env.NODE_ENV === 'development' ? 'api/v1' : window.AJAX_URL_PREFIX;
      const searchUrl = store.getters.isSceneMode
        ? '/search/scene/search/'
        : `/search/index_set/${props.indexSetId}/search/`;
      const requestData = {
        ...requestOtherparams,
        sort_list: store.state.indexFieldInfo.default_sort_list.filter(item => item.length > 0 && !!item[1]) || [],
        size,
        begin,
      };
      const { fieldMetadata, fieldNames } = buildOriginLogSearchFieldPayload(store.state);
      let thisRequestId = '';

      const isCurrentRequest = () => !isUnmounted && currentRequestSeq === requestSeq && requestQueryKey === localQueryKey;

      const handleProgress = async (progress: SearchStreamProgress) => {
        if (!isCurrentRequest() || progress.queryKey !== requestQueryKey) return;

        if (progress.stage === 'meta' && progress.meta) {
          const metaTotal = normalizeSearchTotal(progress.meta.total);
          if (metaTotal > 0 || begin === 0) {
            total = metaTotal;
          }
          if (String(progress.meta.code) === '9900403') {
            store.commit('updateState', {
              authDialogData: {
                apply_url: progress.meta?.data?.apply_url ?? progress.meta?.apply_url,
                apply_data: progress.meta?.permission,
              },
            });
            setExceptionMsg(progress.meta?.message || t('无权限'));
          }
          return;
        }

        if (progress.stage === 'row' && progress.rowKeys?.length) {
          await syncLocalRenderList(progress.rowKeys, syncMode);
          if (isManualSearch && logList.value.length > 0 && choosedIndex.value < 0) {
            handleChooseRow(0, logList.value[0]);
          }
        }
      };

      try {
        const workerResult = await retrieveSearchWorkerService.searchStream({
          baseURL: baseUrl,
          body: requestData,
          fieldMetadata,
          fieldNames,
          headers: buildOriginLogSearchHeaders(store.state),
          onRequestId: (requestId) => {
            thisRequestId = requestId;
            activeLocalSearchRequestId = requestId;
          },
          onProgress: (progress) => {
            void handleProgress(progress);
          },
          queryKey: requestQueryKey,
          // 物理隔离表：禁止写入主检索 retrieveRows
          rowStore: 'relatedLogSearchRows',
          searchPath: searchUrl,
          startSeq: requestStartSeq,
          writeMode,
        });

        if (!isCurrentRequest()) {
          // 过期请求：仅清理本次独立 query（分页复用中的 key 不删）
          if (!isStorageAppend && requestQueryKey && requestQueryKey !== localQueryKey) {
            relatedLogSearchRowCacheService.clearQuery(requestQueryKey).catch(() => undefined);
          }
          return;
        }

        const { code, data, result, message, permission, rowKeys } = workerResult;

        if (code === '9900403') {
          store.commit('updateState', {
            authDialogData: {
              apply_url: data?.apply_url,
              apply_data: permission,
            },
          });
          setExceptionMsg(message || t('无权限'));
          return;
        }

        if (result) {
          begin += size;
          total = normalizeSearchTotal(data?.total) || total;
          await syncLocalRenderList(rowKeys, syncMode);
          localStoredRowCount = resolveLocalStoredRowCountAfterResult({
            isStorageAppend,
            requestStartSeq,
            rowKeysLength: rowKeys.length,
          });
          if (!isStorageAppend) {
            appliedStreamRowCount = rowKeys.length;
          }
          setExceptionMsg('');
          if (isManualSearch) {
            choosedIndex.value = -1;
            if (logList.value[0]) {
              handleChooseRow(0, logList.value[0]);
            }
          }
          return;
        }

        // 仅清空「手动重搜」的首屏失败；种子后加载更多失败保留已有行
        if (uiMode === 'replace') {
          logList.value = [];
          renderMetaList.value = [];
          cachedRowKeys.value = [];
          appliedStreamRowCount = 0;
          localStoredRowCount = 0;
          total = 0;
        }
        setExceptionMsg(message || t('检索失败'));
      } catch (error: any) {
        if (isRequestCanceled(error) || !isCurrentRequest()) {
          return;
        }
        if (uiMode === 'replace') {
          logList.value = [];
          renderMetaList.value = [];
          cachedRowKeys.value = [];
          appliedStreamRowCount = 0;
          localStoredRowCount = 0;
          total = 0;
        }
        setExceptionMsg(error?.message || t('检索失败'));
      } finally {
        if (activeLocalSearchRequestId === thisRequestId) {
          activeLocalSearchRequestId = '';
        }
        if (!isUnmounted && currentRequestSeq === requestSeq) {
          listLoading.value = false;
        }
      }
    };

    const getValidUISearchValue = (searchValue: any[]) => searchValue.reduce((addtions, item) => {
      if (!item.disabled) {
        addtions.push({
          field: item.field,
          operator: item.operator,
          value:
              item.hidden_values?.length > 0
                ? item.value.filter(value => !item.hidden_values.includes(value))
                : item.value,
        });
      }
      return addtions;
    }, []);

    /**
     * UI 操作符落地映射（与 setQueryCondition.getAdditionMappingOperator 对齐）。
     * resolveAddToSearch 对非 text/keyword 等值会输出语义操作符 `is`，
     * 本地 SearchBar 不经 store，必须在此把 `is` → `=`，否则会把「等于」错落成 is。
     */
    const getAdditionMappingOperator = (
      operator: string,
      field: string,
      value: string[],
      depth: number,
      isNestedField = 'false',
    ) => {
      let mappingKey: Record<string, string> = {
        is: '=',
        'is not': '!=',
      };

      const textMappingKey = {
        is: 'contains match phrase',
        'is not': 'not contains match phrase',
      };

      const keywordMappingKey = {
        is: 'contains',
        'is not': 'not contains',
      };

      const boolMapping = {
        is: `is ${value[0]}`,
        'is not': `is ${/true/i.test(value[0]) ? 'false' : 'true'}`,
      };

      const targetField =        fieldsMap.value[field]
        ?? store.state.visibleFields?.find?.(item => item.field_name === field)
        ?? store.state.indexFieldInfo?.fields?.find?.(item => item.field_name === field);
      const textType = targetField?.field_type ?? '';
      const isVirtualObjNode = targetField?.is_virtual_obj_node ?? false;

      if (isVirtualObjNode && textType === 'object') {
        mappingKey = textMappingKey;
      }

      if (textType === 'text') {
        mappingKey = textMappingKey;
      }

      if (textType === 'boolean') {
        mappingKey = boolMapping;
        if (value.length) {
          value.splice(0, value.length);
        }
      }

      if ((depth > 1 || isNestedField === 'true') && textType === 'keyword') {
        mappingKey = keywordMappingKey;
      }
      return mappingKey[operator] ?? operator;
    };

    /**
     * 分词「添加到本次检索」：统一走 resolveAddToSearch（UI + 语句）。
     * UI 模式再经 getAdditionMappingOperator 落地，与 log-rows → setQueryCondition 一致。
     */
    const handleMenuClick = (data: {
      option: {
        depth: number;
        fieldName: string;
        fieldType: string;
        operation: string;
        value: string;
        fullPlain?: string;
        isSoleToken?: boolean;
        tokenIndex?: number;
        tokenCount?: number;
      };
      isLink: boolean;
    }) => {
      const searchMode = requestOtherparams.search_mode === 'sql' ? 'sql' : 'ui';
      const fieldName = data.option.fieldName || '*';
      const fieldType =        fieldsMap.value[fieldName]?.field_type
        ?? store.state.indexFieldInfo?.fields?.find?.(item => item.field_name === fieldName)?.field_type
        ?? data.option.fieldType;
      /** 对象/数组不能 String()，否则会得到 "[object Object]" */
      const toScalarPlain = (val: any): string => {
        if (val === undefined || val === null || val === '') return '';
        if (typeof val === 'object') {
          if (val._isBigNumber) return String(val)
            .replace(/<\/?mark>/gim, '')
            .trim();
          return '';
        }
        return String(val)
          .replace(/<\/?mark>/gim, '')
          .trim();
      };
      const row = logList.value[choosedIndex.value];
      const fromRow = row
        ? (row[fieldName]
          ?? fieldName
            .split('.')
            .reduce((cur: any, key: string) => (cur === null || cur === undefined ? undefined : cur[key]), row))
        : undefined;
      // 时间格式化只影响展示；date 字段必须回取行内原始时间戳
      const isDateField = ['date', 'date_nanos'].includes(fieldType);
      const rawValue =        isDateField && fromRow !== undefined && fromRow !== null && fromRow !== ''
        ? toScalarPlain(fromRow)
        : String(data.option.value ?? '')
          .replace(/<\/?mark>/gim, '')
          .trim();
      let fullPlain = toScalarPlain(data.option.fullPlain);
      // 已污染的 "[object Object]" 视为缺失，回退行数据或放弃完整值
      if (isDateField || !fullPlain || fullPlain === '--' || fullPlain === '[object Object]') {
        const rowPlain = toScalarPlain(fromRow);
        if (rowPlain) {
          fullPlain = rowPlain;
        }
      }
      const soleByValue = Boolean(fullPlain && fullPlain === rawValue);
      const isSoleToken = Boolean(
        data.option.isSoleToken
          || (typeof data.option.tokenCount === 'number' && data.option.tokenCount === 1 && (!fullPlain || soleByValue))
          || soleByValue,
      );
      const payload = resolveAddToSearch({
        field: fieldName,
        value: rawValue,
        fieldType,
        fullText: fullPlain || (isSoleToken ? rawValue : undefined),
        operatorHint: data.option.operation,
        isSoleToken,
        tokenIndex: data.option.tokenIndex ?? (isSoleToken ? 0 : undefined),
        tokenCount: data.option.tokenCount ?? (isSoleToken ? 1 : undefined),
        searchMode,
      });

      let isNeedRefresh = false;
      if (searchMode === 'ui') {
        const uiValue = [...(payload.value ?? [])];
        const operator = getAdditionMappingOperator(payload.operator, payload.field, uiValue, data.option.depth ?? 0);
        const searchItem = {
          disabled: false,
          field: payload.field,
          field_type: payload.fieldType ?? fieldType,
          operator,
          value: uiValue,
          relation: 'OR',
          showAll: true,
        };
        isNeedRefresh = searchBarRef.value.addValue(searchItem);
        const searchValue = searchBarRef.value.getValue();
        requestOtherparams.addition = getValidUISearchValue(searchValue);
        requestOtherparams.keyword = '*';
      } else {
        const searchItem = payload.queryString || '';
        if (!searchItem) {
          return;
        }
        isNeedRefresh = searchBarRef.value.addValue(searchItem);
        const searchValue = searchBarRef.value.getValue();
        requestOtherparams.addition = [];
        requestOtherparams.keyword = searchValue;
      }
      if (isNeedRefresh) {
        handleReset();
        requestLogList();
      }
    };

    const handleSearch = (mode: string, isManualSearch = true) => {
      requestOtherparams.search_mode = mode;
      const searchValue = searchBarRef.value.getValue();
      if (mode === 'ui') {
        requestOtherparams.addition = getValidUISearchValue(searchValue);
        requestOtherparams.keyword = '*';
      } else {
        requestOtherparams.addition = [];
        requestOtherparams.keyword = !searchValue ? '*' : searchValue;
      }
      handleReset();

      requestLogList(isManualSearch);
    };

    const handleChooseRow = (index: number, fallbackRow?: Record<string, any>) => {
      if (choosedIndex.value === index) {
        return;
      }

      choosedIndex.value = index;
      const rowKey = cachedRowKeys.value[index];
      const row = fallbackRow || logList.value[index];
      if (rowKey) {
        // 附带行数据作 fallback：本地 Stream key 在 relatedLogSearchRows，解析侧会双表查找
        emit('choose-row', row ? { rowKey, ...row } : { rowKey });
        return;
      }
      // 无 rowKey 时用当前列表行驱动上下文/实时日志更新
      if (row) {
        emit('choose-row', row);
      }
    };

    const handleScrollContent = debounce((e: any) => {
      if (logList.value.length === total) {
        return;
      }

      const { scrollTop, scrollHeight, clientHeight } = e.target;
      if (scrollHeight - scrollTop - clientHeight <= 1) {
        requestLogList(false);
      }
    }, 600);

    const handleReset = () => {
      cancelPendingRequest();
      clearLocalQueryCache();
      logList.value = [];
      renderMetaList.value = [];
      cachedRowKeys.value = [];
      begin = 0;
      setExceptionMsg('');
    };

    // 添加样式函数
    const addSegmentLightStyle = () => {
      if (!styleElement) {
        styleElement = document.createElement('style');
        styleElement.id = 'dynamic-segment-light-style';
        styleElement.innerHTML = styleContent;
        document.head.appendChild(styleElement);
      }
    };

    // 移除样式函数
    const removeSegmentLightStyle = () => {
      if (styleElement) {
        document.head.removeChild(styleElement);
        styleElement = null;
      }
    };

    const handleCollpaseToggle = () => {
      isCollapsed.value = !isCollapsed.value;
      emit('toggle-collapse', isCollapsed.value);
    };

    const renderTimeCell = (row: any) => {
      const formatValue = RetrieveHelper.formatDateValue(row[timeField.value], timeFieldType.value);
      // formatDateValue 可能返回 <mark>格式化时间</mark>，需解析后渲染，避免标签被当作纯文本
      const { plainText, markRanges } = parseResultMarkedText(formatValue);
      const displayText = plainText || String(formatValue ?? '');
      return buildHighlightHtml({
        text: displayText,
        resultRanges: markRanges,
      });
    };

    onMounted(() => {
      addSegmentLightStyle();
    });

    onBeforeUnmount(() => {
      isUnmounted = true;
      requestSeq += 1;
      cancelPendingRequest();
      clearLocalQueryCache();
      handleScrollContent.cancel();
      if (scrollIntoViewTimer) {
        clearTimeout(scrollIntoViewTimer);
        scrollIntoViewTimer = null;
      }
      logList.value = [];
      renderMetaList.value = [];
      cachedRowKeys.value = [];
      removeSegmentLightStyle();
    });

    expose({
      // init: () => handleSearch(requestOtherparams.search_mode, false),
      init: async () => {
        // 初始化搜索框
        const modeIndex = store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE];
        searchBarRef.value.setLocalMode(modeIndex);
        requestOtherparams.search_mode = modeIndex === 0 ? 'ui' : 'sql';
        const addition = props.retrieveParams.addition || [];
        // 初始化带上常用查询设置
        if (modeIndex === 0) {
          // ui 模式
          const searchValue = searchBarRef.value.getValue();
          if (addition.length > 0 && !searchValue.length) {
            // 常用设置项回填到搜索框
            const addAdditionList = addition.map(item => ({
              disabled: false,
              field: item.field,
              field_type: fieldsMap.value[item.field]?.field_type ?? item.field_type,
              operator: item.operator,
              value: item.value,
              relation: 'OR',
              showAll: true,
            }));
            addAdditionList.forEach((addition) => {
              searchBarRef.value.addValue(addition);
            });
          }
          requestOtherparams.addition = addition;
          requestOtherparams.keyword = '*';
        } else {
          // sql 模式
          const keyword = props.retrieveParams.keyword;
          requestOtherparams.keyword = keyword;
          if (addition.length) {
            requestOtherparams.addition = addition;
          }
        }
        // 设置外部数据：优先读 IndexedDB 渲染行（含检索高亮 overlay），避免初次丢失 mark
        const outerLogResult = store.state.indexSetQueryResult;
        total = outerLogResult.total;
        setExceptionMsg(outerLogResult.is_error ? outerLogResult.exception_msg || '' : '');
        const rowKeys = outerLogResult.row_keys ?? [];
        cachedRowKeys.value = rowKeys;
        if (rowKeys.length) {
          const cachedEntries = await retrieveRowCacheService.getRenderEntries(rowKeys);
          const renderRows = cachedEntries.map(entry => entry?.row).filter(Boolean);
          if (renderRows.length === rowKeys.length) {
            logList.value = renderRows;
            renderMetaList.value = cachedEntries.map(entry => entry?.renderMeta);
          } else {
            // 渲染行不完整时回退原始行，避免列表空白
            const cachedRows = await retrieveRowCacheService.getRows(rowKeys);
            logList.value = cachedRows.length === rowKeys.length ? cachedRows : (outerLogResult.list ?? []).slice();
            renderMetaList.value = logList.value.map(() => undefined);
          }
        } else {
          cachedRowKeys.value = [];
          logList.value = (outerLogResult.list ?? []).slice();
          renderMetaList.value = logList.value.map(() => undefined);
        }
        begin = logList.value.length;
        if (scrollIntoViewTimer) {
          clearTimeout(scrollIntoViewTimer);
        }
        scrollIntoViewTimer = setTimeout(() => {
          if (isUnmounted) {
            return;
          }
          // 自动定位到选中行
          const isChoosedRow = Array.from(tableRef.value?.querySelectorAll('.is-choosed') ?? [])[0] as HTMLElement;
          if (!isChoosedRow) {
            return;
          }
          const positionInfo = isChoosedRow.getBoundingClientRect();
          if (positionInfo.top > window.innerHeight - 70) {
            isChoosedRow.scrollIntoView();
          }
        });
      },
      reset: handleReset,
    });

    const rowStyle = `font-family: var(--bklog-v3-row-ctx-font);
    font-size: var(--table-fount-size);
    color: var(--table-fount-color);`;

    return () => (
      <div class='log-result-main'>
        <div
          class='collapse-main'
          on-click={handleCollpaseToggle}
        >
          <log-icon
            class={{ 'collpase-icon': true, 'is-collapsed': isCollapsed.value }}
            type='angle-left'
            common
          />
        </div>
        <div class='title-main'>
          <div class='title'>{t('原始日志检索结果')}</div>
          <div class='split-line'></div>
          <div class='desc'>{t('可切换原始日志，查看该日志的上下文')}</div>
        </div>
        <div class={['search-main', { 'is-monitor-apm': isMonitorApm }]}>
          <SearchBar
            ref={searchBarRef}
            showClear={false}
            showCopy={false}
            showFavorites={false}
            showQuerySetting={false}
            usageType='local'
            popupAppendToBody
            on-mode-change={handleSearch}
            on-search={handleSearch}
          />
        </div>
        <div
          class='content-main'
          on-scroll={handleScrollContent}
        >
          <table
            ref={tableRef}
            class='log-result-table'
          >
            <thead>
              <tr class='table-header'>
                <th style='width:90px;padding-left:42px'>{t('行号')}</th>
                <th style='width:200px'>{t('时间')}</th>
                <th style='min-width:300px'>{t('原始日志')}</th>
              </tr>
            </thead>
            <tbody v-bkloading={{ isLoading: listLoading.value, opacity: 0.6 }}>
              {logList.value.length > 0
                && logList.value.map((row, index) => (
                  <tr
                    key={`${index}_${row.time}`}
                    class={{ 'is-choosed': choosedIndex.value === index }}
                    on-click={() => handleChooseRow(index)}
                  >
                    <td>
                      <div class='index-column'>
                        <span>{index + 1}</span>
                        <div class='choosed-bgd'>
                          <div class={['check-icon-main', { 'is-monitor-apm-icon': isMonitorApm }]}>
                            {isMonitorApm ? (
                              <span class='bk-icon icon-check-1'></span>
                            ) : (
                              <span class='bk-icon bklog-icon bklog-correct'></span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td
                      style={rowStyle}
                      domProps={{ innerHTML: renderTimeCell(row) }}
                    ></td>
                    <td style='padding:4px 0'>
                      <RenderJsonCell>
                        <JsonFormatter
                          class='bklog-column-wrapper'
                          fields={visibleFields.value}
                          jsonValue={row}
                          limitRow={null}
                          renderMeta={renderMetaList.value[index]}
                          onMenu-click={handleMenuClick}
                        ></JsonFormatter>
                      </RenderJsonCell>
                    </td>
                  </tr>
                ))}
              {!listLoading.value && !logList.value.length && exceptionMsg.value && (
                <tr>
                  <td
                    colspan={3}
                    style='padding: 24px 16px; border-bottom: none;'
                  >
                    <bk-exception
                      scene='part'
                      type='500'
                    >
                      <span>{exceptionMsg.value}</span>
                    </bk-exception>
                  </td>
                </tr>
              )}
              {!listLoading.value && !logList.value.length && !exceptionMsg.value && (
                <tr>
                  <td
                    colspan={3}
                    style='padding: 24px 16px; border-bottom: none;'
                  >
                    <bk-exception
                      scene='part'
                      type='empty'
                    >
                      <span>{t('检索结果为空')}</span>
                    </bk-exception>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  },
});
