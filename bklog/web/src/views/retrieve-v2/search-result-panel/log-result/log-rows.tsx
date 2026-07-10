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
import { computed, defineComponent, h, nextTick, onBeforeUnmount, reactive, ref, watch, type Ref } from 'vue';

import { getRowFieldValue, setDefaultTableWidth, TABLE_LOG_FIELDS_SORT_REGULAR, xssFilter } from '@/common/util';
import { getInputQueryDefaultItem } from '@/views/retrieve-v2/search-bar/utils/const.common';
// import { perfStart, perfEnd } from '@/utils/performance-monitor';
import JsonFormatter from '@/global/json-formatter.vue';
import type { RetrieveRowRenderMeta } from '@/storage/utils/retrieve-render-meta';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import { UseSegmentProp } from '@/hooks/use-segment-pop';
import useStore from '@/hooks/use-store';
import useWheel from '@/hooks/use-wheel';

import PopInstanceUtil from '@/global/pop-instance-util';
import { BK_LOG_STORAGE } from '@/store/store.type';
import RetrieveHelper, { RetrieveEvent } from '../../../retrieve-helper';
import ExpandView from '../../components/result-cell-element/expand-view.vue';
import OperatorTools from '../../components/result-cell-element/operator-tools.vue';
import RetrieveLoader from '@/skeleton/retrieve-loader.vue';
import { retrieveFieldCacheService, retrieveRowCacheService } from '@/storage';
import FullRowViewer from './full-row-viewer.vue';
import ScrollTop from '../../components/scroll-top/index';
import useTextAction from '../../hooks/use-text-action';
import LogCell from './log-cell';
import LogResultException from './log-result-exception';
import {
  LOG_SOURCE_F,
  ROW_EXPAND,
  ROW_F_ORIGIN_CTX,
  ROW_F_ORIGIN_TIME,
  ROW_INDEX,
  ROW_KEY,
  ROW_SOURCE,
  SECTION_SEARCH_INPUT,
} from './log-row-attributes';
import RowRender from './row-render';
import ScrollXBar from '../../components/scroll-x-bar';
import useLazyRender from './use-lazy-render';
import useHeaderRender from './use-render-header';

import './log-rows.scss';

const FullRowViewerComponent = FullRowViewer as any;

type RowConfig = {
  expand?: boolean;
  isIntersect?: boolean;
  minHeight?: number;
  stickyTop?: number;
  rowMinHeight?: number;
};

export default defineComponent({
  props: {
    contentType: {
      type: String,
      default: 'table',
    },
    handleClickTools: {
      type: Function,
      default: undefined,
    },
  },
  setup(props, { emit }) {
    const store = useStore();
    const { $t } = useLocale();

    const refRootElement: Ref<HTMLElement> = ref();
    const refTableHead: Ref<HTMLElement> = ref();
    const refLoadMoreElement: Ref<HTMLElement> = ref();
    const refResultRowBox: Ref<HTMLElement> = ref();
    const refSegmentContent: Ref<HTMLElement> = ref();
    const { handleOperation, getObjectValue, handleAddCondition } = useTextAction(emit, 'origin');

    let savedSelection: Range = null;
    let mousedownOnRow = false;
    let hoverOperatorHideTimer: ReturnType<typeof setTimeout> = null;
    const layoutTimers: number[] = [];

    const hoverOperatorState = reactive({
      visible: false,
      interacting: false,
      row: null,
      rowIndex: -1,
      top: 0,
      right: 12,
    });

    const popInstanceUtil = new PopInstanceUtil({
      refContent: () => refSegmentContent.value,
      tippyOptions: {
        hideOnClick: true,
        theme: 'segment-light',
        placement: 'bottom',
        appendTo: document.body,
        popperOptions: {
          strategy: 'fixed',
        },
      },
    });

    const getSelectionReferenceRect = (range: Range, e: MouseEvent) => {
      const rects = Array.from(range.getClientRects()).filter(rect => rect.width && rect.height);

      if (!rects.length) {
        return range.getBoundingClientRect();
      }

      return rects.reduce((closestRect, rect) => {
        const getDistance = (targetRect: DOMRect) => {
          const offsetX = e.clientX < targetRect.left ? targetRect.left - e.clientX : Math.max(e.clientX - targetRect.right, 0);
          const offsetY = e.clientY < targetRect.top ? targetRect.top - e.clientY : Math.max(e.clientY - targetRect.bottom, 0);
          return offsetX ** 2 + offsetY ** 2;
        };

        return getDistance(rect) < getDistance(closestRect) ? rect : closestRect;
      }, rects[rects.length - 1]);
    };

    const FULLTEXT_FIELD_NAME = '*';
    const SELECTION_WORD_REGEX = /\S+/g;

    type SelectionToken = {
      text: string;
      isCursorText: boolean;
      fieldName?: string;
      tokenType?: 'field-name' | 'field-value';
    };

    const stripSelectionMarkup = (value: string) => String(value ?? '').replace(/<\/?mark>/gim, '');

    const tokenizeSelectionText = (value: string, extra?: Partial<SelectionToken>) => {
      const tokens: SelectionToken[] = [];
      const text = stripSelectionMarkup(value);
      let lastIndex = 0;
      let match: RegExpExecArray | null;
      SELECTION_WORD_REGEX.lastIndex = 0;

      while ((match = SELECTION_WORD_REGEX.exec(text)) !== null) {
        if (match.index > lastIndex) {
          tokens.push({
            text: text.slice(lastIndex, match.index),
            isCursorText: false,
          });
        }

        tokens.push({
          text: match[0],
          isCursorText: true,
          ...extra,
        });
        lastIndex = match.index + match[0].length;
      }

      if (lastIndex < text.length) {
        tokens.push({
          text: text.slice(lastIndex),
          isCursorText: false,
        });
      }

      return tokens;
    };

    const getFieldPlainText = (row: Record<string, any>, field: Record<string, any>) => {
      const rawValue = getRowFieldValue(row, field);
      if (rawValue === null || rawValue === undefined || rawValue === '') {
        return '--';
      }

      return stripSelectionMarkup(String(rawValue));
    };

    const getFieldSegmentTokens = (row: Record<string, any>, field: Record<string, any>) => tokenizeSelectionText(getFieldPlainText(row, field));

    const getOriginSegmentTokens = (row: Record<string, any>) => {
      const tokens: SelectionToken[] = [];
      const fields = visibleFields.value.length ? visibleFields.value : filteredFieldList.value;

      fields.forEach((field, index) => {
        if (index > 0) {
          tokens.push({ text: ' ', isCursorText: false });
        }

        tokens.push({
          text: field.field_name,
          isCursorText: true,
          fieldName: field.field_name,
          tokenType: 'field-name',
        });
        tokens.push({ text: ' ', isCursorText: false });
        tokens.push(...tokenizeSelectionText(getFieldPlainText(row, field), {
          fieldName: field.field_name,
          tokenType: 'field-value',
        }));
      });

      return tokens;
    };

    const getSelectionTextByRange = (range: Range) => stripSelectionMarkup(range?.toString?.() ?? '');

    const getSelectionAnchorElement = (range: Range) => {
      const startNode = range?.startContainer as Node | null;
      const endNode = range?.endContainer as Node | null;
      const startElement = startNode instanceof Element ? startNode : startNode?.parentElement;
      const endElement = endNode instanceof Element ? endNode : endNode?.parentElement;

      return (startElement?.closest?.('[data-field-name]') ?? endElement?.closest?.('[data-field-name]')) as HTMLElement | null;
    };

    const completeSelectionByTokens = (selectionText: string, tokens: SelectionToken[]) => {
      if (!selectionText || !tokens.length) {
        return [];
      }

      const normalizedSelection = stripSelectionMarkup(selectionText);
      if (!normalizedSelection) {
        return [];
      }

      const plainText = tokens.map(item => item.text).join('');
      const selectionStart = plainText.indexOf(normalizedSelection);
      if (selectionStart < 0) {
        return [];
      }

      const selectionEnd = selectionStart + normalizedSelection.length;
      let cursor = 0;
      const selectedTokenIndexes = new Set<number>();
      for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];
        const tokenStart = cursor;
        const tokenEnd = tokenStart + token.text.length;
        cursor = tokenEnd;

        if (selectionStart < tokenEnd && selectionEnd > tokenStart) {
          selectedTokenIndexes.add(i);
        }
      }

      if (!selectedTokenIndexes.size) {
        return [];
      }

      const completedTokens: SelectionToken[] = [];
      const appendedTokenSet = new Set<string>();
      for (const index of Array.from(selectedTokenIndexes).sort((a, b) => a - b)) {
        const token = tokens[index];
        if (!token?.isCursorText) {
          continue;
        }

        const tokenKey = [token.fieldName ?? '', token.tokenType ?? '', token.text].join('__');
        if (!appendedTokenSet.has(tokenKey)) {
          appendedTokenSet.add(tokenKey);
          completedTokens.push(token);
        }
      }

      return completedTokens;
    };

    const getFieldByName = (fieldName: string) => {
      if (!fieldName) {
        return undefined;
      }

      return filteredFieldList.value.find(item => item.field_name === fieldName)
        ?? visibleFields.value.find(item => item.field_name === fieldName)
        ?? fullColumns.value.find(item => item.field_name === fieldName);
    };

    const addSelectionToCurrentSearch = (selectionRange: Range, row: Record<string, any>) => {
      const selectionText = getSelectionTextByRange(selectionRange);
      if (!selectionText) {
        return;
      }

      const targetElement = getSelectionAnchorElement(selectionRange);
      const targetFieldName = targetElement?.getAttribute('data-field-name') ?? '';
      const fulltextFieldItem = getInputQueryDefaultItem();

      if (showCtxType.value === 'table') {
        const targetField = getFieldByName(targetFieldName);
        if (!targetField) {
          handleAddCondition(FULLTEXT_FIELD_NAME, fulltextFieldItem.operator, [selectionText]);
          return;
        }

        const completedTokens = completeSelectionByTokens(selectionText, getFieldSegmentTokens(row, targetField));
        if (!completedTokens.length) {
          handleAddCondition(targetField.field_name, 'is', [selectionText]);
          return;
        }

        completedTokens.forEach(token => {
          handleAddCondition(targetField.field_name, 'is', [token.text]);
        });
        return;
      }

      const conditions: Array<{ field: string; operator: string; value: string[] }> = [];
      const appendedConditionKeys = new Set<string>();
      const fieldNameSet = new Set(filteredFieldList.value.map(item => item.field_name));
      const originTokens = completeSelectionByTokens(selectionText, getOriginSegmentTokens(row));

      originTokens.forEach((token) => {
        if (!token.text || token.tokenType === 'field-name' || fieldNameSet.has(token.text)) {
          return;
        }

        const field = getFieldByName(token.fieldName ?? '');
        const plainText = field ? getFieldPlainText(row, field) : '';
        const operator = field && plainText === token.text ? 'is' : fulltextFieldItem.operator;
        const conditionField = operator === 'is' && field ? field.field_name : FULLTEXT_FIELD_NAME;
        const conditionKey = [conditionField, operator, token.text].join('__');
        if (!appendedConditionKeys.has(conditionKey)) {
          appendedConditionKeys.add(conditionKey);
          conditions.push({
            field: conditionField,
            operator,
            value: [token.text],
          });
        }
      });

      if (!conditions.length) {
        handleAddCondition(FULLTEXT_FIELD_NAME, fulltextFieldItem.operator, [selectionText]);
        return;
      }

      conditions.forEach(item => {
        handleAddCondition(item.field, item.operator, item.value);
      });
    };

    const setSelectionPopTargetHandler = (rect: DOMRect) => {
      let virtualTarget = document.body.querySelector('.bklog-selection-pop-target') as HTMLElement;
      if (!virtualTarget) {
        virtualTarget = document.createElement('span');
        virtualTarget.className = 'bklog-selection-pop-target';
        virtualTarget.style.setProperty('position', 'fixed');
        virtualTarget.style.setProperty('visibility', 'hidden');
        virtualTarget.style.setProperty('pointer-events', 'none');
        virtualTarget.style.setProperty('z-index', '-1');
        document.body.appendChild(virtualTarget);
      }

      virtualTarget.style.setProperty('left', `${rect.left}px`);
      virtualTarget.style.setProperty('top', `${rect.top}px`);
      virtualTarget.style.setProperty('width', `${Math.max(rect.width, 1)}px`);
      virtualTarget.style.setProperty('height', `${Math.max(rect.height, 1)}px`);

      return virtualTarget;
    };

    const useSegmentPop = new UseSegmentProp({
      delineate: true,
      aiBluekingEnabled: store.state.features.isAiAssistantActive,
      stopPropagation: true,
      highlightEnabled: true,
      allowDelineateSearch: true,
      onclick: (...args) => {
        const type = args[1];
        if (type === 'add-to-ai') {
          props.handleClickTools(type, savedSelection?.toString() ?? '');
        } else if (type === 'is' && savedSelection && hoverOperatorState.row) {
          addSelectionToCurrentSearch(savedSelection, hoverOperatorState.row);
        } else {
          handleOperation(type, { value: savedSelection?.toString() ?? '', operation: type });
        }
        popInstanceUtil.hide();

        if (savedSelection) {
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(savedSelection);
        }
      },
    });

    const pageIndex = ref(1);
    // 前端本地分页
    const pageSize = ref(50);
    const isRending = ref(false);

    let tableRowConfig = new WeakMap();
    const tableRowConfigByKey = new Map();
    const isPageLoading = ref(RetrieveHelper.isSearching);
    const isPaginationLoading = ref(false);
    // 前端本地分页loadmore触发器
    // renderList 没有使用响应式，这里需要手动触发更新，所以这里使用一个计数器来触发更新
    const localUpdateCounter = ref(0);
    const hasMoreList = ref(true);
    let renderList = Object.freeze([]);
    const fullRowViewerState = reactive({
      visible: false,
      rowKey: '',
      rowData: null as Record<string, any> | null,
      truncatedFields: [] as string[],
    });
    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const filteredFieldList = computed(() => store.getters.filteredFieldList);
    const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
    const visibleFields = computed(() => store.getters.visibleFields);
    const indexSetOperatorConfig = computed(() => store.state.indexSetOperatorConfig);
    const tableShowRowIndex = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX]);
    const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
    const timeField = computed(() => indexFieldInfo.value.time_field);
    const timeFieldType = computed(() => indexFieldInfo.value.time_field_type);
    const isLoading = computed(() => indexSetQueryResult.value.is_loading || indexFieldInfo.value.is_loading);
    const kvShowFieldsList = computed(() => filteredFieldList.value?.map(f => f.field_name));
    const userSettingConfig = computed(() => store.state.retrieve.catchFieldCustomConfig);
    const fieldScope = computed(() => indexFieldInfo.value.field_scope || store.state.indexId || 'default');
    const rowKeys = computed<string[]>(() => indexSetQueryResult.value?.row_keys ?? []);
    const tableDataSize = computed(() => rowKeys.value.length || (indexSetQueryResult.value?.list?.length ?? 0));
    const isUnionSearch = computed(() => store.getters.isUnionSearch);
    const tableList = computed<any[]>(() => Object.freeze(indexSetQueryResult.value?.list ?? []));
    const gradeOption = computed(() => store.state.indexFieldInfo.custom_config?.grade_options ?? { disabled: false });
    const indexSetType = computed(() => store.state.indexItem.isUnionIndex);
    const limitRow = computed(() => store.state.storage[BK_LOG_STORAGE.RESULT_DISPLAY_LINES]);

    const bumpFieldWidthVersion = () => {
      store.commit('updateState', { fieldWidthVersion: store.state.fieldWidthVersion + 1 });
    };

    const exceptionMsg = computed(() => {
      if (/^cancel$/gi.test(indexSetQueryResult.value?.exception_msg)) {
        return $t('检索结果为空');
      }

      return indexSetQueryResult.value?.exception_msg || $t('检索结果为空');
    });
    const isShowSourceField = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_SOURCE_FIELD]);
    const fullColumns = ref([]);
    const showCtxType = ref(props.contentType);
    const columnLayoutVersion = ref(0);
    const isFirstPageLayoutPending = ref(false);
    let firstPageLayoutToken = 0;

    /**
     * 重置分页状态
     * 新查询首屏需要先展示骨架屏，等待列宽布局稳定后再渲染真实行，避免 monitor 包外部挂载时首帧列宽抖动。
     */
    const resetPageState = () => {
      pageIndex.value = 1;
      hasMoreList.value = true;
      isFirstPageLayoutPending.value = true;
      firstPageLayoutToken += 1;
      tableRowConfig = new WeakMap();
      tableRowConfigByKey.clear();
    };

    const { addEvent } = useRetrieveEvent();
    addEvent(RetrieveEvent.SEARCHING_CHANGE, (isSearching) => {
      isPageLoading.value = isSearching;
      if (isSearching && tableDataSize.value === 0 && !isPaginationLoading.value) {
        resetPageState();
      }
    });

    addEvent([
      RetrieveEvent.SEARCH_VALUE_CHANGE,
      RetrieveEvent.SEARCH_TIME_CHANGE,
      RetrieveEvent.TREND_GRAPH_SEARCH,
    ], () => {
      resetPageState();
    });

    addEvent(RetrieveEvent.SORT_LIST_CHANGED, () => {
      /**
       * SORT_LIST_CHANGED may be fired after the sort query has finished.
       * In that case tableDataSize has already changed and first-page reveal has already been scheduled/finished.
       * Resetting first-page layout again here would leave the skeleton pending forever because no new data-size
       * change will arrive to call scheduleFirstPageTableReveal().
       *
       * New sort queries already clear list and set loading in requestIndexSetQuery(), which drives the skeleton
       * through tableDataSize/isLoading watchers. Therefore this event only needs to force reset while the request
       * is still in-flight or before any result rows are available.
       */
      if (isLoading.value || isPageLoading.value || isRequesting.value || tableDataSize.value === 0) {
        resetPageState();
      }
    });

    addEvent(RetrieveEvent.AUTO_REFRESH, async () => {
      resetPageState();
      // 场景化检索模式下条件为空时跳过
      if (store.getters.isSceneMode && store.getters.isSceneFilterEmpty) return;
      // 检索条件有变更时先加载字段信息
      if (store.state.indexItem.isSceneFilterChanged) {
        await store.dispatch('requestIndexSetFieldInfo');
      }
      store.dispatch('requestIndexSetQuery', { from: 'auto_refresh' });
    });

    const getRowCacheKey = (row, index: number) => rowKeys.value[index] ?? `${row?.dtEventTimeStamp ?? 'row'}_${index}`;

    const setRenderList = (length?: number) => {
      const endIndex = length ?? tableDataSize.value;

      if (rowKeys.value.length) {
        const lastIndex = Math.min(endIndex, rowKeys.value.length);
        const keys = rowKeys.value.slice(0, lastIndex);

        retrieveRowCacheService.getRenderEntries(keys).then((entries) => {
          renderList = entries.filter(Boolean).map((entry, index) => ({
            item: entry.row,
            renderMeta: entry.renderMeta as RetrieveRowRenderMeta | undefined,
            [ROW_KEY]: keys[index] ?? getRowCacheKey(entry.row, index),
          }));
          localUpdateCounter.value += 1;
          nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
        });
        return;
      }

      const arr: Record<string, any>[] = [];
      const lastIndex = Math.min(endIndex, tableList.value.length);
      for (let i = 0; i < lastIndex; i++) {
        arr.push({
          item: tableList.value[i],
          renderMeta: undefined as RetrieveRowRenderMeta | undefined,
          [ROW_KEY]: `${tableList.value[i]?.dtEventTimeStamp ?? 'row'}_${i}`,
        });
      }

      renderList = arr;
    };

    const searchContainerHeight = ref(52);
    const resultContainerId = ref(RetrieveHelper.logRowsContainerId);
    const resultContainerIdSelector = `#${resultContainerId.value}`;


    const rowComponentMetaMap = new WeakMap<
      Record<string, any>,
      { renderMeta?: RetrieveRowRenderMeta; rowKey?: string }
    >();

    const setRowComponentMeta = (row: Record<string, any> | undefined, rowKey?: string, renderMeta?: RetrieveRowRenderMeta) => {
      if (row && typeof row === 'object') {
        rowComponentMetaMap.set(row, { rowKey, renderMeta });
      }
    };

    const getRowRenderMeta = (row?: Record<string, any>) => row ? rowComponentMetaMap.get(row)?.renderMeta : undefined;
    const getRowComponentKey = (row: Record<string, any> | undefined) => row ? rowComponentMetaMap.get(row)?.rowKey : undefined;

    const shouldShowFullRowAction = (row: Record<string, any>) => {
      const meta = getRowRenderMeta(row);
      return !!meta?.hasTruncatedField;
    };

    const openFullRowViewer = (row: Record<string, any>, rowIndex: number) => {
      const rowKey = getRowComponentKey(row) || rowKeys.value[rowIndex] || '';
      const meta = getRowRenderMeta(row);
      fullRowViewerState.rowKey = rowKey;
      fullRowViewerState.rowData = row;
      fullRowViewerState.truncatedFields = meta?.truncatedFields ?? [];
      if (fullRowViewerState.visible) {
        fullRowViewerState.visible = false;
        nextTick(() => {
          fullRowViewerState.visible = true;
        });
        return;
      }

      fullRowViewerState.visible = true;
    };

    const originalColumns = computed(() => {
      return [
        {
          field: ROW_F_ORIGIN_TIME,
          key: ROW_F_ORIGIN_TIME,
          title: ROW_F_ORIGIN_TIME,
          align: 'top',
          resize: false,
          minWidth: timeFieldType.value === 'date_nanos' ? 250 : 200,
          renderBodyCell: ({ row }) => {
            const timezone = store.state.indexItem.timezone;
            const fieldType = timeFieldType.value;
            const formatValue = RetrieveHelper.formatTimeZoneValue(row[timeField.value], fieldType, timezone);

            return h(
              'span',
              {
                class: 'time-field',
                domProps: {
                  innerHTML: xssFilter(formatValue),
                },
              },
              [],
            );
          },
        },
        {
          field: ROW_F_ORIGIN_CTX,
          key: ROW_F_ORIGIN_CTX,
          title: ROW_F_ORIGIN_CTX,
          align: 'top',
          minWidth: '100%',
          width: '100%',
          resize: false,
          renderBodyCell: ({ row }) => {
            return (
              <JsonFormatter
                class='bklog-column-wrapper'
                fields={visibleFields.value}
                jsonValue={row}
                limitRow={null}
                originalMode={true}
                renderMeta={getRowRenderMeta(row)}
                stateKey={getRowComponentKey(row)}
                onMenu-click={({ option, isLink }) => handleMenuClick(option, isLink)}
              />
            );
          },
        },
      ];
    });

    const formatColumn = (field) => {
      return {
        field: field.field_name,
        key: field.field_name,
        title: field.field_name,
        width: field.width,
        minWidth: field.minWidth,
        field_type: field.field_type,
        align: 'top',
        resize: true,
        renderBodyCell: ({ row }) => {
          return (
            <JsonFormatter
              class='bklog-column-wrapper'
              fields={field}
              jsonValue={getRowFieldValue(row, field)}
              limitRow={limitRow.value}
              renderMeta={getRowRenderMeta(row)}
              onMenu-click={({ option, isLink }) => handleMenuClick(option, isLink, { row, field })}
            />
          );
        },
        renderHeaderCell: () => {
          const sortable = field.es_doc_values && field.tag !== 'union-source' && field.field_type !== 'flattened';
          return renderHead(field, (order) => {
            if (sortable) {
              const sortList = order ? [[field.field_name, order]] : [];
              const updatedSortList = store.state.indexFieldInfo.sort_list.map((item) => {
                if (sortList.length > 0 && item[0] === field.field_name) {
                  return sortList[0];
                }
                if (sortList.length === 0 && item[0] === field.field_name) {
                  return [field.field_name, 'desc'];
                }
                return item;
              });
              const temporarySortList = syncSpecifiedFieldSort(field.field_name, sortList);
              resetPageState();
              store.commit('updateState', { localSort: true });
              store.commit('updateIndexFieldInfo', { sort_list: updatedSortList });
              store.commit('updateIndexItemParams', { sort_list: temporarySortList });
              store.dispatch('requestIndexSetQuery');
            }
          });
        },
      };
    };

    const getNumericWidth = (width, fallback = 0) => {
      if (typeof width === 'number') {
        return width;
      }

      if (typeof width === 'string' && width.includes('%')) {
        return fallback;
      }

      const parsedWidth = Number.parseFloat(width);
      return Number.isNaN(parsedWidth) ? fallback : parsedWidth;
    };

    const TABLE_WIDTH_SAFE_GAP = 4;

    const getFixedColumnsWidth = () => {
      const expandColumnWidth = 36;
      const rowIndexColumnWidth = tableShowRowIndex.value ? 50 : 0;
      const sourceColumnWidth = isShowSourceField.value && indexSetType.value ? 230 : 0;

      return expandColumnWidth + rowIndexColumnWidth + sourceColumnWidth;
    };

    const getFieldsAvailableWidth = () => offsetWidth.value - getFixedColumnsWidth() - TABLE_WIDTH_SAFE_GAP;

    const getColumnWidthTotal = (columnList: Record<string, any>[]) => {
      return columnList.reduce((total, item) => total + getNumericWidth(item.width, item.minWidth), 0);
    };

    const getExtraWidthTargetColumns = (columnList: Record<string, any>[]) => {
      const longTextColumns = columnList.filter((item) => {
        return item.field === 'log' || item.field_type === 'text' || getNumericWidth(item.width) >= 800;
      });

      return longTextColumns;
    };

    const distributeExtraWidthToLongTextColumns = (columnList: Record<string, any>[]) => {
      const availableWidth = getFieldsAvailableWidth();
      if (availableWidth <= 0 || columnList.length === 0) {
        return;
      }

      const columnWidth = getColumnWidthTotal(columnList);
      if (columnWidth >= availableWidth) {
        return;
      }

      const targetColumns = getExtraWidthTargetColumns(columnList);
      if (targetColumns.length === 0) {
        return;
      }

      const extraWidth = availableWidth - columnWidth;
      const addWidth = Math.floor(extraWidth / targetColumns.length);
      let restWidth = extraWidth - addWidth * targetColumns.length;

      targetColumns.forEach((item) => {
        const nextWidth = getNumericWidth(item.width, item.minWidth) + addWidth + (restWidth > 0 ? 1 : 0);
        restWidth -= 1;
        item.width = nextWidth;
      });
    };

    const triggerColumnLayoutReflow = () => {
      columnLayoutVersion.value += 1;
    };

    // 性能优化：使用 computed 缓存列配置，避免每次渲染都重新计算
    const getFieldColumns = computed(() => {
      columnLayoutVersion.value;

      if (showCtxType.value === 'table') {
        const columnList: Record<string, any>[] = [];
        const columns = visibleFields.value.length > 0 ? visibleFields.value : fullColumns.value;
        let maxColWidth = 40;
        let logField: Record<string, any> | null = null;

        // 性能优化：当字段数量很大时，使用 for 循环比 forEach 性能更好
        for (let i = 0; i < columns.length; i++) {
          const col = columns[i];
          const formatValue = formatColumn(col);
          if (col.field_name === 'log') {
            logField = formatValue;
          }

          columnList.push(formatValue);
          maxColWidth += formatValue.width;
        }

        if (!logField && columnList.length > 0) {
          logField = columnList[columnList.length - 1];
        }

        if (logField && offsetWidth.value > maxColWidth) {
          logField.width = getNumericWidth(logField.width, logField.minWidth);
        }

        distributeExtraWidthToLongTextColumns(columnList);

        return columnList;
      }

      return originalColumns.value;
    });

    const hanldeAfterExpandClick = (target: HTMLElement) => {
      const expandTarget = target
        .closest('.bklog-row-container')
        ?.querySelector('.bklog-row-observe .expand-view-wrapper');
      if (expandTarget) {
        RetrieveHelper.highlightElement(expandTarget as HTMLElement);
      }
    };

    const leftColumns = computed(() => [
      {
        field: '',
        key: ROW_EXPAND,
        // 设置需要显示展开图标的列
        type: 'expand',
        title: '',
        width: 36,
        align: 'center',
        resize: false,
        fixed: 'left',
        renderBodyCell: ({ row, rowIndex }) => {
          const config: RowConfig = ensureTableRowConfig(row, rowIndex).value;
          return (
            <span class={['bklog-expand-icon', { 'is-expaned': config.expand }]}>
              <i
                style={{ color: '#4D4F56', fontSize: '9px' }}
                class='bk-icon icon-play-shape'
              />
            </span>
          );
        },
      },
      {
        field: '',
        key: ROW_INDEX,
        title: tableShowRowIndex.value ? '#' : '',
        width: tableShowRowIndex.value ? 50 : 0,
        fixed: 'left',
        align: 'center',
        resize: false,
        class: tableShowRowIndex.value ? 'is-show' : 'is-hidden',
        renderBodyCell: ({ row, rowIndex }) => {
          return ensureTableRowConfig(row, rowIndex).value[ROW_INDEX] + 1;
        },
      },
      {
        field: '',
        key: ROW_SOURCE,
        title: '日志来源',
        width: 230,
        align: 'left',
        resize: false,
        fixed: 'left',
        disabled: !(isShowSourceField.value && indexSetType.value),
        renderBodyCell: ({ row }) => {
          const indeSetName = unionIndexItemList.value.find(
            item => item.index_set_id === String(row.__index_set_id__),
          )?.index_set_name ?? '';
          const hanldeSoureClick = (event) => {
            event.stopPropagation();
            event.preventDefault();
            event.stopImmediatePropagation();
          };

          return <span onClick={hanldeSoureClick}>{indeSetName}</span>;
        },
      },
    ]);

    const handleRowAIClcik = (e: MouseEvent, row: any, rowIndex: number) => {
      const displayRowIndex = ensureTableRowConfig(row, rowIndex).value[ROW_INDEX] + 1;
      const targetRow = (e.target as HTMLElement).closest('.bklog-row-container');
      const oldRow = targetRow?.parentElement.querySelector('.bklog-row-container.ai-active');

      oldRow?.classList.remove('ai-active');
      targetRow?.classList.add('ai-active');

      props.handleClickTools('ai', row, indexSetOperatorConfig.value, displayRowIndex);
    };

    // 替换原有的handleIconClick
    const handleIconClick = (type, content, field, row, isLink, depth, isNestedField) => {
      handleOperation(type, { content, field, row, isLink, depth, isNestedField, operation: type });
    };

    // 替换原有的handleMenuClick
    const handleMenuClick = (option, isLink, fieldOption?: { row: any; field: any }) => {
      const timeTypes = ['date', 'date_nanos'];

      handleOperation(option.operation, {
        ...option,
        value: timeTypes.includes(fieldOption?.field.field_type ?? null)
          ? `${getObjectValue(fieldOption?.row, fieldOption?.field)}`.replace(/<\/?mark>/gim, '')
          : option.value,
        fieldName: option.fieldName,
        operation: option.operation,
        field: fieldOption?.field,
        isLink,
        depth: option.depth,
        displayFieldNames: option.displayFieldNames,
      });
    };

    const { renderHead } = useHeaderRender();
    const getFallbackRenderFields = (fields: Record<string, any>[] = []) => {
      const renderableFields = fields.filter(field =>
        field?.field_name
        && field.field_type !== '__virtual__'
        && !field.is_virtual_obj_node,
      );
      const preferredFields = ['log', 'body']
        .map(fieldName => renderableFields.find(field => field.field_name === fieldName))
        .filter(Boolean);

      return preferredFields.length
        ? preferredFields
        : renderableFields.slice(0, 4);
    };
    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const setFullColumns = () => {
      /** 清空所有字段后所展示的默认字段  顺序: 时间字段，log字段，索引字段 */
      const dataFields: Record<string, any>[] = [];
      const indexSetFields: Record<string, any>[] = [];
      const logFields: Record<string, any>[] = [];

      // 性能优化：使用 for 循环替代 for...of，当字段数量很大时性能更好
      const filteredFields = filteredFieldList.value;
      for (let i = 0; i < filteredFields.length; i++) {
        const item = filteredFields[i];
        if (item.field_type === 'date') {
          dataFields.push(item);
        } else if (item.field_name === 'log' || item.field_alias === 'original_text') {
          logFields.push(item);
        } else if (!(item.field_type === '__virtual__' || item.is_built_in)) {
          indexSetFields.push(item);
        }
      }

      // 性能优化：缓存正则替换结果，避免重复计算
      const sortIndexSetFieldsList = indexSetFields.sort((a, b) => {
        const sortA = a.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        const sortB = b.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        return sortA.localeCompare(sortB);
      });
      let sortFieldsList = [...dataFields, ...logFields, ...sortIndexSetFieldsList];
      if (!sortFieldsList.length) {
        sortFieldsList = getFallbackRenderFields(filteredFields);
      }
      if (isUnionSearch.value && indexSetOperatorConfig.value?.isShowSourceField) {
        sortFieldsList.unshift(LOG_SOURCE_F());
      }

      if (rowKeys.value.length) {
        retrieveRowCacheService
          .getRows(rowKeys.value.slice(0, Math.min(rowKeys.value.length, 50)))
          .then((rows) => {
            const widthSnapshot = setDefaultTableWidth(sortFieldsList, rows, retrieveFieldCacheService.getUserWidthConfig(fieldScope.value));
            retrieveFieldCacheService.setComputedWidths(fieldScope.value, sortFieldsList);
            if (Object.keys(widthSnapshot).length) bumpFieldWidthVersion();
          });
      } else {
        const widthSnapshot = setDefaultTableWidth(sortFieldsList, tableList.value, retrieveFieldCacheService.getUserWidthConfig(fieldScope.value));
        retrieveFieldCacheService.setComputedWidths(fieldScope.value, sortFieldsList);
        if (Object.keys(widthSnapshot).length) bumpFieldWidthVersion();
      }
      fullColumns.value = sortFieldsList;
    };

    const getRowConfigWithCache = () => {
      return [['expand', false]].reduce((cfg, item: [keyof RowConfig, any]) => {
        cfg[item[0]] = item[1];
        return cfg;
      }, {});
    };

    const createRowConfigRef = (index: number, rowKey?: string) => {
      const rowIndex = index >= 0 ? index : -1;
      return ref({
        [ROW_KEY]: rowKey || `${ROW_KEY}_${rowIndex}`,
        [ROW_INDEX]: rowIndex,
        ...getRowConfigWithCache(),
      });
    };

    const getRowConfigKey = (row, index: number) => {
      return getRowComponentKey(row) || rowKeys.value[index] || '';
    };

    const ensureTableRowConfig = (row, index: number) => {
      if (!row) {
        return createRowConfigRef(index);
      }

      const rowKey = getRowConfigKey(row, index);
      let config = rowKey ? tableRowConfigByKey.get(rowKey) : tableRowConfig.get(row);
      if (!config) {
        config = createRowConfigRef(index, rowKey);
        if (rowKey) {
          tableRowConfigByKey.set(rowKey, config);
        }
      } else {
        if (rowKey && config.value[ROW_KEY] !== rowKey) {
          config.value[ROW_KEY] = rowKey;
        }
      }

      tableRowConfig.set(row, config);

      if (index >= 0 && config.value[ROW_INDEX] !== index) {
        config.value[ROW_INDEX] = index;
      }

      return config;
    };

    const isRequesting = ref(false);
    let requestingTimer: any = null;
    let skipNextLoadingEndReset = false;

    const debounceSetLoading = (delay = 120) => {
      requestingTimer && clearTimeout(requestingTimer);
      requestingTimer = setTimeout(() => {
        isRequesting.value = false;
      }, delay);
    };

    const expandOption = {
      render: ({ row, rowIndex }) => {
        const config = ensureTableRowConfig(row, rowIndex);
        const realRowIndex = config.value[ROW_INDEX];

        // // 性能监控：记录展开渲染耗时
        // perfStart('log-rows:expand-render', {
        //   rowIndex,
        //   fieldCount: kvShowFieldsList.value.length,
        // });

        // // 使用 nextTick 确保性能监控在渲染完成后执行
        // nextTick(() => {
        //   perfEnd('log-rows:expand-render', {
        //     rowIndex,
        //     fieldCount: kvShowFieldsList.value.length,
        //   });
        // });

        return (
          <ExpandView
            data={row}
            kv-show-fields-list={kvShowFieldsList.value}
            list-data={row}
            row-index={realRowIndex}
            row-key={getRowComponentKey(row) || rowKeys.value[realRowIndex] || ''}
            onValue-click={(type, content, isLink, field, depth, isNestedField) => {
              return handleIconClick(type, content, field, row, isLink, depth, isNestedField);
            }}
          />
        );
      },
    };

    let syncResultBoxRectBeforeRender = () => {};
    let scheduleFirstPageTableReveal = () => {};

    const resetRowListState = () => {
      const shouldWaitFirstPageLayout = isFirstPageLayoutPending.value && tableDataSize.value > 0;

      if (shouldWaitFirstPageLayout) {
        syncResultBoxRectBeforeRender();
      }

      setRenderList(null);
      debounceSetLoading();
      localUpdateCounter.value += 1;

      if (tableDataSize.value <= pageSize.value) {
        nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
      }

      if (shouldWaitFirstPageLayout) {
        scheduleFirstPageTableReveal();
      }
    };

    /**
     * 同步指定字段的排序状态
     * @param fieldName 字段名
     * @param updatedSortList 排序列表
     * @returns 更新后的排序列表
     */
    const syncSpecifiedFieldSort = (fieldName, updatedSortList) => {
      const requiredFields = ['gseIndex', 'iterationIndex', 'dtEventTimeStamp'];
      if (!(requiredFields.includes(fieldName) && updatedSortList.length)) {
        return updatedSortList;
      }
      const fields = filteredFieldList.value.map(item => item.field_name);
      const currentSort = updatedSortList.find(([key]) => key === fieldName)[1];

      for (const field of requiredFields) {
        if (field === fieldName) {
          continue;
        }
        if (fields.includes(field)) {
          const index = updatedSortList.findIndex(([key]) => key === field);
          const sortItem = [field, currentSort];

          if (index !== -1) {
            updatedSortList[index] = sortItem;
          } else {
            updatedSortList.push(sortItem);
          }
        }
      }
      return updatedSortList;
    };


    watch(
      () => [tableShowRowIndex.value, isShowSourceField.value, indexSetType.value],
      () => {
        computeRect();
      },
    );

    /**
     * 处理结果框的resize
     * @param resetScroll 是否重置滚动条
     */
    const handleResultBoxResize = (resetScroll = true) => {
      if (!RetrieveHelper.jsonFormatter.isExpandNodeClick) {
        if (resetScroll) {
          scrollXOffsetLeft = 0;
          refScrollXBar.value?.scrollLeft(0);
        }
      }

      computeRect(refResultRowBox.value);
    };

    let visibleFieldsLayoutToken = 0;
    const refreshVisibleFieldsColumnLayout = async () => {
      const layoutToken = ++visibleFieldsLayoutToken;
      if (!visibleFields.value.length) {
        setFullColumns();
        triggerColumnLayoutReflow();
        handleResultBoxResize();
        return;
      }

      const layoutRows = rowKeys.value.length
        ? await retrieveRowCacheService.getRows(rowKeys.value.slice(0, Math.min(rowKeys.value.length, 10)))
        : tableList.value;
      if (layoutToken !== visibleFieldsLayoutToken) {
        return;
      }

      const fieldsWidthConfig = {
        ...retrieveFieldCacheService.getUserWidthConfig(fieldScope.value),
        ...(userSettingConfig.value.fieldsWidth ?? {}),
      };
      const widthSnapshot = setDefaultTableWidth(visibleFields.value, layoutRows, fieldsWidthConfig);
      retrieveFieldCacheService.setComputedWidths(fieldScope.value, visibleFields.value);
      if (Object.keys(widthSnapshot).length) bumpFieldWidthVersion();
      triggerColumnLayoutReflow();
      handleResultBoxResize();
    };
    addEvent(RetrieveEvent.VISIBLE_FIELD_COLUMN_LAYOUT_CHANGE, refreshVisibleFieldsColumnLayout);

    watch(
      () => [
        indexFieldInfo.value.field_meta_version,
        filteredFieldList.value.length,
        visibleFields.value.length,
        showCtxType.value,
      ],
      ([, filteredLength, visibleLength, currentShowCtxType]) => {
        if (currentShowCtxType === 'table' && filteredLength > 0 && visibleLength === 0) {
          refreshVisibleFieldsColumnLayout();
        }
      },
    );

    watch(
      () => [props.contentType],
      () => {
        showCtxType.value = props.contentType;
        pageIndex.value = 1;
        setRenderList(50);
        handleResultBoxResize();
      },
    );

    watch(
      () => [tableDataSize.value],
      ([size]) => {
        if (size === 0) {
          resetPageState();
          if (!isLoading.value) {
            isFirstPageLayoutPending.value = false;
          }
        }

        resetRowListState();
      },
      {
        immediate: true,
      },
    );

    useResizeObserve(
      () => refResultRowBox.value,
      () => {
        handleResultBoxResize(!isColumnWidthChanging);
        RetrieveHelper.fire(RetrieveEvent.RESULT_ROW_BOX_RESIZE);
      },
      60,
    );

    addEvent(
      [
        RetrieveEvent.FAVORITE_WIDTH_CHANGE,
        RetrieveEvent.FAVORITE_SHOWN_CHANGE,
      ],
      handleResultBoxResize,
    );

    addEvent(RetrieveEvent.AI_CLOSE, () => {
      refResultRowBox.value?.querySelector('.ai-active')?.classList.remove('ai-active');
    });

    let isColumnWidthChanging = false;
    let columnWidthChangeTimer: number;

    const markColumnWidthChanging = () => {
      isColumnWidthChanging = true;
      window.clearTimeout(columnWidthChangeTimer);
      columnWidthChangeTimer = window.setTimeout(() => {
        isColumnWidthChanging = false;
      }, 300);
    };

    const preserveHorizontalScrollAfterColumnResize = (preferredScrollLeft: number) => {
      nextTick(() => {
        requestAnimationFrame(() => {
          computeRectSync(refResultRowBox.value);
          const maxOffset = Math.max(0, scrollWidth.value - offsetWidth.value);
          scrollXOffsetLeft = Math.min(preferredScrollLeft, maxOffset);
          refScrollXBar.value?.scrollLeft(scrollXOffsetLeft);
          setRowboxTransform();
        });
      });
    };

    const handleColumnWidthChange = (w, col) => {
      const prevScrollLeft = scrollXOffsetLeft;
      markColumnWidthChanging();

      const width = w > 40 ? w : 40;
      const currentFields = visibleFields.value.length ? visibleFields.value : fullColumns.value;
      const field = currentFields.find(item => item.field_name === col.field);
      if (!field) return;

      const longFiels = currentFields.filter(
        item => item.width >= 800 || item.field_name === 'log' || item.field_type === 'text',
      );
      const logField = longFiels.find(item => item.field_name === 'log');
      const targetField = longFiels.length
        ? longFiels
        : currentFields.filter(item => item.field_name !== col.field);

      if (width < col.width && targetField.length) {
        const widthDiff = col.width - width;
        if (logField) {
          logField.width += widthDiff;
        } else {
          const avgWidth = widthDiff / targetField.length;
          for (const field of targetField) {
            field.width += avgWidth;
          }
        }
      }

      const sourceObj = currentFields.reduce((acc, curField) => {
        acc[curField.field_name] = curField.width;
        return acc;
      }, {});
      const { fieldsWidth } = userSettingConfig.value;
      const newFieldsWidthObj = {
        ...fieldsWidth,
        ...sourceObj,
        [col.field]: Math.ceil(width),
      };

      field.width = width;

      store.dispatch('userFieldConfigChange', {
        fieldsWidth: newFieldsWidthObj,
      });
      retrieveFieldCacheService.setUserWidths(fieldScope.value, newFieldsWidthObj);
      bumpFieldWidthVersion();

      if (visibleFields.value.length) {
        store.commit('updateVisibleFields', visibleFields.value);
      } else {
        fullColumns.value = [...currentFields];
      }
      triggerColumnLayoutReflow();
      preserveHorizontalScrollAfterColumnResize(prevScrollLeft);
    };

    const getPaginationResponseSize = (resp) => {
      if (typeof resp?.length === 'number') {
        return resp.length;
      }

      if (typeof resp?.size === 'number') {
        return resp.size;
      }

      if (Array.isArray(resp)) {
        return resp.length;
      }

      if (Array.isArray(resp?.data?.list)) {
        return resp.data.list.length;
      }

      return null;
    };

    const loadMoreTableData = () => {
      // tableDataSize.value === 0 用于判定是否是第一次渲染导致触发的请求
      // visibleFields.value 在字段重置时会清空，所以需要判断
      if (isRequesting.value || tableDataSize.value === 0 || visibleFields.value.length === 0) {
        return Promise.resolve(false);
      }

      // 首屏（流式）检索进行中时，row_keys 是渐进写入的部分数据，此时不能触发后端分页，
      // 否则会因“未满一屏”误判而在首屏完成前反复发起 append 请求。
      if (indexSetQueryResult.value.is_loading && !indexSetQueryResult.value.is_pagination_loading) {
        return Promise.resolve(false);
      }

      if (pageIndex.value * pageSize.value < tableDataSize.value) {
        hasMoreList.value = true;
        isRequesting.value = true;
        pageIndex.value += 1;
        const maxLength = Math.min(pageSize.value * pageIndex.value, tableDataSize.value);
        setRenderList(maxLength);
        debounceSetLoading(0);
        nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
        localUpdateCounter.value += 1;
        return Promise.resolve(false);
      }

      if (hasMoreList.value) {
        isRequesting.value = true;
        isPaginationLoading.value = true;
        skipNextLoadingEndReset = true;
        return store
          .dispatch('requestIndexSetQuery', { isPagination: true })
          .then((resp) => {
            const responseSize = getPaginationResponseSize(resp);
            pageIndex.value += 1;
            handleResultBoxResize(false);

            if (responseSize !== null && responseSize < pageSize.value) {
              hasMoreList.value = false;
            }
          })
          .finally(() => {
            isPaginationLoading.value = false;
            debounceSetLoading(0);
            nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
          });
      }

      return Promise.resolve(false);
    };

    useResizeObserve(SECTION_SEARCH_INPUT, (entry) => {
      searchContainerHeight.value = entry.contentRect.height;
    });

    let scrollXOffsetLeft = 0;
    const refScrollXBar = ref();

    const afterScrollTop = () => {
      pageIndex.value = 1;
      const maxLength = Math.min(pageSize.value * pageIndex.value, tableDataSize.value);
      if (rowKeys.value.length) {
        setRenderList(maxLength);
      } else {
        renderList = renderList.slice(0, maxLength);
        localUpdateCounter.value += 1;
      }
    };

    // 监听滚动条滚动位置
    // 判定是否需要拉取更多数据
    const { offsetWidth, scrollWidth, computeRect, computeRectSync, getScrollElement } = useLazyRender({
      loadMoreFn: loadMoreTableData,
      container: resultContainerIdSelector,
      rootElement: refRootElement,
      refLoadMoreElement,
    });

    syncResultBoxRectBeforeRender = () => {
      computeRectSync(refResultRowBox.value);
      triggerColumnLayoutReflow();
    };

    scheduleFirstPageTableReveal = () => {
      const token = firstPageLayoutToken;
      nextTick(() => {
        requestAnimationFrame(() => {
          if (token !== firstPageLayoutToken || tableDataSize.value === 0) {
            return;
          }

          computeRectSync(refResultRowBox.value);
          triggerColumnLayoutReflow();

          nextTick(() => {
            requestAnimationFrame(() => {
              if (token !== firstPageLayoutToken || tableDataSize.value === 0) {
                return;
              }

              computeRectSync(refResultRowBox.value);
              isFirstPageLayoutPending.value = false;
              nextTick(() => {
                computeRectSync(refResultRowBox.value);
                setRowboxTransform();
              });
            });
          });
        });
      });
    };

    const setRowboxTransform = () => {
      if (refResultRowBox.value && refRootElement.value) {
        refResultRowBox.value.scrollLeft = scrollXOffsetLeft;
        if (refTableHead.value) {
          refTableHead.value.style.setProperty('width', `${scrollWidth.value}px`);
          refTableHead.value.style.transform = `translateX(-${scrollXOffsetLeft}px)`;
        }
      }
    };

    const hasScrollX = computed(() => {
      return showCtxType.value === 'table' && scrollWidth.value > offsetWidth.value;
    });

    const syncResultBoxLayout = () => {
      nextTick(() => {
        requestAnimationFrame(() => {
          triggerColumnLayoutReflow();

          nextTick(() => {
            requestAnimationFrame(() => {
              computeRectSync(refResultRowBox.value);
              if (scrollWidth.value <= offsetWidth.value && scrollXOffsetLeft !== 0) {
                scrollXOffsetLeft = 0;
                refScrollXBar.value?.scrollLeft(0);
              }
              setRowboxTransform();
            });
          });
        });
      });
    };

    const handleFieldSettingLayoutChange = () => {
      scrollXOffsetLeft = 0;
      refScrollXBar.value?.scrollLeft(0);
      computeRectSync(refResultRowBox.value);
      syncResultBoxLayout();
      layoutTimers.push(window.setTimeout(syncResultBoxLayout, 120));
      layoutTimers.push(window.setTimeout(syncResultBoxLayout, 320));
    };

    addEvent(
      [
        RetrieveEvent.LEFT_FIELD_SETTING_WIDTH_CHANGE,
        RetrieveEvent.LEFT_FIELD_SETTING_SHOWN_CHANGE,
      ],
      handleFieldSettingLayoutChange,
    );

    watch(
      () => [offsetWidth.value, showCtxType.value],
      ([width], [oldWidth]) => {
        if (width !== oldWidth) {
          syncResultBoxLayout();
        }
      },
    );

    const isPreloading = ref(false);     // 是否正在预加载
    const preloadThreshold = 32 * 50;        // 距离底部多少 px 开始预加载
    let lastPreloadTime = 0;
    const preloadCooldown = 300;         // ms

    const shouldPreloadOnScrollDown = (event: WheelEvent) => {
      if (!hasMoreList.value) return false;
      if (isPreloading.value) return false;

      // 1️⃣ 判定向下滚动
      if (event.deltaY <= 0) return false;

      const now = Date.now();
      if (now - lastPreloadTime < preloadCooldown) return false;

      const scrollElement = getScrollElement();
      // 2️⃣ 判定是否接近底部
      const scrollTop = scrollElement?.scrollTop ?? 0;
      const clientHeight = scrollElement?.clientHeight ?? 0;
      const scrollHeight = scrollElement?.scrollHeight ?? 0;
      const distanceToBottom = scrollHeight - (scrollTop + clientHeight);
      const shouldPreload = distanceToBottom <= preloadThreshold;
      if (shouldPreload) {
        lastPreloadTime = now;
      }

      return shouldPreload;
    };

    let isAnimating = false;

    useWheel({
      target: refRootElement,
      options: { passive: false },
      callback: (event: WheelEvent) => {
        if (shouldPreloadOnScrollDown(event)) {
          isPreloading.value = true;
          loadMoreTableData().finally(() => {
            isPreloading.value = false;
          });
        }

        const maxOffset = scrollWidth.value - offsetWidth.value;

        if (event.shiftKey) {
          if (hasScrollX.value && refScrollXBar.value) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            const currentScrollLeft = refScrollXBar.value.getScrollLeft?.() || 0;
            const scrollStep = event.deltaY || event.deltaX;
            const newScrollLeft = Math.max(0, Math.min(maxOffset, currentScrollLeft + scrollStep));

            refScrollXBar.value.scrollLeft(newScrollLeft);
            scrollXOffsetLeft = newScrollLeft;
            setRowboxTransform();
          }
          return;
        }

        if (event.deltaX !== 0 && hasScrollX.value) {
          event.preventDefault();
          event.stopPropagation();
          event.stopImmediatePropagation();
          if (!isAnimating) {
            isAnimating = true;
            requestAnimationFrame(() => {
              isAnimating = false;
              const nextOffset = Math.max(0, Math.min(maxOffset, scrollXOffsetLeft + event.deltaX));
              if (nextOffset !== scrollXOffsetLeft) {
                scrollXOffsetLeft = nextOffset;
                setRowboxTransform();
                refScrollXBar.value?.scrollLeft(nextOffset);
              }
            });
          }
        }
      },
    });


    const showHeader = computed(() => {
      return showCtxType.value === 'table' && tableDataSize.value > 0;
    });

    const hasResultException = computed(() => {
      const rawExceptionMsg = indexSetQueryResult.value?.exception_msg ?? '';
      return indexSetQueryResult.value?.is_error || (!!rawExceptionMsg && !/^cancel$/gi.test(rawExceptionMsg));
    });

    /**
     * 字段信息重新加载期间 visibleFields 会被清空。
     * monitor 独立包切换 timeRange 时，字段接口返回前如果继续渲染旧 renderList，
     * 表格会只剩固定列（序号/操作列），形成错误中间态。这里仅在字段加载中接管为首屏骨架屏，
     * 字段加载完成后的错误/空态仍交给 LogResultException 渲染。
     */
    const isFieldLoadingForFirstPage = computed(() => {
      return indexFieldInfo.value.is_loading && visibleFields.value.length === 0;
    });

    const shouldEnterFirstPageSkeleton = computed(() => {
      return (
        !hasResultException.value
        && !isPaginationLoading.value
        && tableDataSize.value === 0
        && (isLoading.value || isPageLoading.value || isRequesting.value)
      );
    });

    const shouldShowFirstPageSkeleton = computed(() => {
      if (hasResultException.value || isPaginationLoading.value) {
        return false;
      }

      return shouldEnterFirstPageSkeleton.value || isFieldLoadingForFirstPage.value || isFirstPageLayoutPending.value;
    });

    const shouldBlockTableRender = computed(() => {
      return shouldShowFirstPageSkeleton.value;
    });

    const renderHeadVNode = () => {
      if (shouldBlockTableRender.value) {
        return null;
      }

      let hasFullWidth = false;

      return (
        <div
          ref={refTableHead}
          class={['bklog-row-container row-header']}
        >
          <div class='bklog-list-row'>
            {allColumns.value.map((column) => {
              const isFullWidthColumn = !hasFullWidth && column.width === '100%';
              const cellStyle = getColumnWidth(column, isFullWidthColumn);
              hasFullWidth = hasFullWidth || column.width === '100%';

              return (
                <LogCell
                  key={column.key}
                  width={column.width}
                  class={[(column as any).class ?? '', 'bklog-row-cell header-cell', (column as any).fixed]}
                  customStyle={cellStyle}
                  minWidth={(column as any).minWidth > 0 ? (column as any).minWidth : column.width}
                  resize={column.resize}
                  onResize-width={w => handleColumnWidthChange(w, column)}
                >
                  {(column as any).renderHeaderCell?.({ column }, h) ?? column.title}
                </LogCell>
              );
            })}
          </div>
        </div>
      );
    };

    const renderScrollTop = () => {
      return <ScrollTop on-scroll-top={afterScrollTop} />;
    };

    const getColumnWidth = (column, fullWidth = false) => {
      if (fullWidth) {
        return {
          width: '100%',
          minWidth: `${Math.max(column.minWidth, column.width)}px`,
        };
      }

      if (typeof column.width === 'number') {
        return {
          width: `${column.width}px`,
          minWidth: `${column.width}px`,
          maxWidth: `${column.width}px`,
        };
      }
      return {
        width: column.width,
        minWidth: `${column.minWidth ?? 80}px`,
      };
    };

    const allColumns = computed(() => {
      const columns = [...leftColumns.value, ...getFieldColumns.value].filter(
        item => !(item as any).disabled,
      );
      return columns;
    });

    const clearHoverOperatorHideTimer = () => {
      if (hoverOperatorHideTimer) {
        clearTimeout(hoverOperatorHideTimer);
        hoverOperatorHideTimer = null;
      }
    };

    const scheduleHideHoverOperator = () => {
      clearHoverOperatorHideTimer();
      hoverOperatorHideTimer = setTimeout(() => {
        if (hoverOperatorState.interacting) {
          return;
        }
        hoverOperatorState.visible = false;
      }, 80);
    };

    const activateHoverOperator = () => {
      hoverOperatorState.interacting = true;
      clearHoverOperatorHideTimer();
    };

    const deactivateHoverOperator = () => {
      hoverOperatorState.interacting = false;
      scheduleHideHoverOperator();
    };

    const updateHoverOperatorPosition = (rowEl: HTMLElement) => {
      const rootEl = refRootElement.value;
      if (!rootEl || !rowEl) {
        return;
      }

      const rootRect = rootEl.getBoundingClientRect();
      const rowRect = rowEl.getBoundingClientRect();
      const rowPaddingTop = 4;
      const rowPaddingRight = 12;

      /**
       * Keep the product motion translate(0, -32px) unchanged.
       * Render the operator as a fixed overlay so it can move above the first row without being clipped by
       * .bklog-result-container overflow hidden. Do not clamp the anchor downward: that would make the
       * floating actions cover the row text and steal text click/selection interactions.
       */
      hoverOperatorState.top = rowRect.top + rowPaddingTop;
      hoverOperatorState.right = Math.max(
        rowPaddingRight,
        window.innerWidth - Math.min(rootRect.right, window.innerWidth) + rowPaddingRight,
      );
    };

    const handleRowMouseenter = (event: MouseEvent, row, rowIndex: number) => {
      clearHoverOperatorHideTimer();
      hoverOperatorState.interacting = false;
      hoverOperatorState.row = row;
      hoverOperatorState.rowIndex = rowIndex;
      hoverOperatorState.visible = !window?.__IS_MONITOR_TRACE__;
      updateHoverOperatorPosition(event.currentTarget as HTMLElement);
    };

    const handleRowMouseleave = () => {
      scheduleHideHoverOperator();
    };

    const renderHoverOperatorOverlay = () => {
      if (!hoverOperatorState.row || window?.__IS_MONITOR_TRACE__) {
        return null;
      }

      return (
        <div
          class={{
            'bklog-row-hover-operator': true,
            'is-show': hoverOperatorState.visible,
          }}
          style={{
            top: `${hoverOperatorState.top}px`,
            right: `${hoverOperatorState.right}px`,
          }}
          onFocusin={activateHoverOperator}
          onFocusout={deactivateHoverOperator}
          onMouseenter={activateHoverOperator}
          onMouseleave={deactivateHoverOperator}
        >
          <div class='bklog-row-hover-operator-content'>
            {/** @ts-expect-error */}
            <OperatorTools
              handle-click={(type, event) => {
                if (type === 'ai') {
                  handleRowAIClcik(event, hoverOperatorState.row, hoverOperatorState.rowIndex);
                  return;
                }
                if (type === 'fullRow') {
                  openFullRowViewer(hoverOperatorState.row, hoverOperatorState.rowIndex);
                  return;
                }
                props.handleClickTools(
                  type,
                  hoverOperatorState.row,
                  indexSetOperatorConfig.value,
                  ensureTableRowConfig(hoverOperatorState.row, hoverOperatorState.rowIndex).value[ROW_INDEX] + 1,
                  getRowConfigKey(hoverOperatorState.row, hoverOperatorState.rowIndex),
                );
              }}
              index={hoverOperatorState.row[ROW_INDEX]}
              operator-config={indexSetOperatorConfig.value}
              row-data={hoverOperatorState.row}
              show-full-row={shouldShowFullRowAction(hoverOperatorState.row)}
            />
          </div>
        </div>
      );
    };

    const renderRowCells = (row, rowIndex) => {
      const { expand } = ensureTableRowConfig(row, rowIndex).value;
      let hasFullWidth = false;

      return [
        <div
          key={`${rowIndex}-row`}
          class='bklog-list-row'
          data-row-index={rowIndex}
          data-row-click
        >
          {allColumns.value.map((column) => {
            const isFullWidthColumn = !hasFullWidth && column.width === '100%';
            const cellStyle = getColumnWidth(column, isFullWidthColumn);
            hasFullWidth = hasFullWidth || column.width === '100%';

            return (
              <div
                key={`${rowIndex}-${column.key}`}
                style={cellStyle}
                class={[(column as any).class ?? '', 'bklog-row-cell', (column as any).fixed]}
              >
                {column.renderBodyCell?.({ row, column, rowIndex }, h) ?? column.title}
              </div>
            );
          })}
        </div>,
        expand ? expandOption.render({ row, rowIndex }) : '',
      ];
    };

    const handleRowMousedown = (e: MouseEvent) => {
      mousedownOnRow = true;

      if (RetrieveHelper.isClickOnSelection(e, 2)) {
        RetrieveHelper.stopEventPropagation(e);
        return;
      }

      RetrieveHelper.setMousedownEvent(e);
      savedSelection = null;
    };

    const handleRowMouseup = (e: MouseEvent, item: any, rowIndex: number) => {
      if (!mousedownOnRow) {
        RetrieveHelper.setMousedownEvent(null);
        return;
      }
      // 选中文本不弹出复制等选项框
      if (window.__IS_MONITOR_TRACE__ && window.getSelection().toString().length > 1) {
        RetrieveHelper.setMousedownEvent(null);
        return;
      }

      mousedownOnRow = false;

      if (RetrieveHelper.isClickOnSelection(e, 2) || RetrieveHelper.isMouseSelectionUpEvent(e)) {
        RetrieveHelper.stopEventPropagation(e);
        RetrieveHelper.setMousedownEvent(null);
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
          savedSelection = selection.getRangeAt(0);
          const rect = getSelectionReferenceRect(savedSelection, e);
          const target = setSelectionPopTargetHandler(rect);
          popInstanceUtil.uninstallInstance();
          popInstanceUtil.show(target, true, true);
        }
        return;
      }

      const target = e.target as HTMLElement;
      const expandCell = target.closest('.bklog-row-observe')?.querySelector('.expand-view-wrapper');

      const interactiveTarget = target.closest('a, button, input, textarea, [role="button"], .bk-link-text');
      if (interactiveTarget || expandCell?.contains(target)) {
        RetrieveHelper.setMousedownEvent(null);
        return;
      }

      const config: RowConfig = ensureTableRowConfig(item, rowIndex).value;
      const isExpanding = !config.expand;
      config.expand = isExpanding;
      RetrieveHelper.setMousedownEvent(null);

      // 性能监控：记录展开/收起操作的耗时
      // if (isExpanding) {
      //   perfStart('log-rows:expand-click', {
      //     rowIndex: config[ROW_INDEX],
      //     fieldCount: kvShowFieldsList.value.length,
      //   });
      // }

      nextTick(() => {
        if (config.expand) {
          hanldeAfterExpandClick(target);
          // 展开完成后记录耗时
          // perfEnd('log-rows:expand-click', {
          //   rowIndex: config[ROW_INDEX],
          //   fieldCount: kvShowFieldsList.value.length,
          // });
        }
      });
    };

    const renderRowVNode = () => {
      if (shouldBlockTableRender.value) {
        return null;
      }

      return renderList.map((row, rowIndex) => {
        const renderRow = row.item as Record<string, any>;
        setRowComponentMeta(renderRow, row[ROW_KEY], row.renderMeta);
        const logLevel = gradeOption.value.disabled ? '' : RetrieveHelper.getLogLevel(renderRow, gradeOption.value);

        return [
          <RowRender
            key={row[ROW_KEY]}
            class={[
              'bklog-row-container',
              logLevel ?? 'normal',
              {
                'is-hover-operator-active': hoverOperatorState.visible && hoverOperatorState.rowIndex === rowIndex,
              },
            ]}
            row-index={rowIndex}
            on-row-mousedown={handleRowMousedown}
            on-row-mouseenter={e => handleRowMouseenter(e, renderRow, rowIndex)}
            on-row-mouseleave={handleRowMouseleave}
            on-row-mouseup={e => handleRowMouseup(e, renderRow, rowIndex)}
          >
            {renderRowCells(renderRow, rowIndex)}
          </RowRender>,
        ];
      });
    };

    const handleScrollXChanged = (event: MouseEvent) => {
      scrollXOffsetLeft = (event.target as HTMLElement)?.scrollLeft || 0;
      setRowboxTransform();
    };

    const renderScrollXBar = () => {
      return (
        <ScrollXBar
          ref={refScrollXBar}
          innerWidth={scrollWidth.value}
          outerWidth={offsetWidth.value}
          onScroll-change={handleScrollXChanged}
        />
      );
    };

    const loadingText = computed(() => {
      if (isLoading.value && !isRequesting.value && !isPaginationLoading.value) {
        return '';
      }

      if (hasMoreList.value && (isLoading.value || isRending.value || isPaginationLoading.value)) {
        return 'Loading ...';
      }

      if (!(isRequesting.value || hasMoreList.value) || tableDataSize.value < pageSize.value) {
        if (tableDataSize.value > 0) {
          return ` - 已加载所有数据: 共计 ${tableDataSize.value} 条 - `;
        }
      }

      return '';
    });

    const updateLoader = () => {
      if (refLoadMoreElement.value) {
        const targetElement = refLoadMoreElement.value.firstElementChild as HTMLElement;
        targetElement.style.width = `${offsetWidth.value}px`;
        targetElement.textContent = loadingText.value;
      }
    };

    const updateRootElementClass = () => {
      if (refRootElement.value) {
        refRootElement.value.classList.toggle('has-scroll-x', hasScrollX.value);
        refRootElement.value.classList.toggle('show-header', showHeader.value);
      }
    };

    watch(
      () => [offsetWidth.value, loadingText.value],
      () => {
        updateLoader();
      },
    );

    watch(
      () => [hasScrollX.value, showHeader.value],
      () => {
        updateRootElementClass();
      },
    );

    watch(
      () => indexSetQueryResult.value.is_loading,
      (newVal, oldVal) => {
        if (oldVal && !newVal) {
          if (tableDataSize.value === 0) {
            isFirstPageLayoutPending.value = false;
          }

          if (skipNextLoadingEndReset) {
            skipNextLoadingEndReset = false;
            return;
          }

          if (!isRequesting.value) {
            nextTick(() => {
              scrollXOffsetLeft = 0;
              refScrollXBar.value?.scrollLeft(0);
              computeRect(refResultRowBox.value);
            });
          }
        }
      },
    );

    const renderLoader = () => {
      return (
        <div
          ref={refLoadMoreElement}
          class='bklog-requsting-loading'
        >
          <div style='min-width: 100%' />
        </div>
      );
    };


    const isTableLoading = computed(() => {
      return (
        !shouldShowFirstPageSkeleton.value
        && tableDataSize.value === 0
        && (isRequesting.value || isRending.value || isPageLoading.value || isLoading.value)
      );
    });

    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const exceptionType = computed(() => {
      if (tableDataSize.value === 0 || indexFieldInfo.value.is_loading) {
        if (shouldShowFirstPageSkeleton.value) {
          return 'hidden';
        }

        if (isRequesting.value || isLoading.value || isPageLoading.value) {
          return 'loading';
        }

        if ($t('检索结果为空') === exceptionMsg.value) {
          return 'search-empty';
        }

        if (/^index-set-not-found/.test(exceptionMsg.value)) {
          return 'index-set-not-found';
        }

        if (/^index-set-field-not-found/.test(exceptionMsg.value)) {
          return 'index-set-field-not-found';
        }

        return exceptionMsg.value.length ? 'error' : 'empty';
      }

      return 'hidden';
    });

    const getExceptionRender = () => {
      if (shouldShowFirstPageSkeleton.value) {
        return null;
      }

      return (
        <LogResultException
          message={exceptionMsg.value}
          type={exceptionType.value}
        />
      );
    };

    const renderFirstPageSkeleton = () => {
      if (!shouldShowFirstPageSkeleton.value) {
        return null;
      }

      return (
        <RetrieveLoader
          class='bklog-first-page-skeleton'
          isLoading={true}
          isOriginalField={showCtxType.value !== 'table'}
          maxLength={12}
          static={true}
          visibleFields={visibleFields.value.length ? visibleFields.value : fullColumns.value}
        />
      );
    };

    const renderFullRowViewer = () => (
      <FullRowViewerComponent
        visible={fullRowViewerState.visible}
        rowKey={fullRowViewerState.rowKey}
        rowData={fullRowViewerState.rowData}
        fields={visibleFields.value.length ? visibleFields.value : fullColumns.value}
        truncatedFields={fullRowViewerState.truncatedFields}
        onUpdate:visible={(value: boolean) => {
          fullRowViewerState.visible = value;
        }}
      />
    );

    const renderDelineatePopContent = () => {
      return <div style='display: none;'>{useSegmentPop.createSegmentContent(refSegmentContent)}</div>;
    };

    onBeforeUnmount(() => {
      clearHoverOperatorHideTimer();
      popInstanceUtil.uninstallInstance();
      window.clearTimeout(columnWidthChangeTimer);
      requestingTimer && clearTimeout(requestingTimer);
      while (layoutTimers.length) {
        clearTimeout(layoutTimers.pop());
      }
      hoverOperatorState.visible = false;
      hoverOperatorState.row = null;
      renderList = Object.freeze([]);
    });

    return () => (
      <div
        ref={refRootElement}
        class='bklog-result-container'
      >
        {renderHeadVNode()}
        <div
          id={resultContainerId.value}
          ref={refResultRowBox}
          class='bklog-row-box'
          data-local-update-counter={localUpdateCounter.value}
        >
          {renderRowVNode()}
        </div>
        {renderHoverOperatorOverlay()}
        {renderFirstPageSkeleton()}
        {getExceptionRender()}
        {renderScrollXBar()}
        {renderLoader()}
        {renderScrollTop()}
        {renderDelineatePopContent()}
        {renderFullRowViewer()}
        <div class='resize-guide-line' />
      </div>
    );
  },
});
