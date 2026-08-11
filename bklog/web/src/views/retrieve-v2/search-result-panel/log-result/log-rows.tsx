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
import { computed, defineComponent, h, nextTick, onBeforeUnmount, ref, watch, type Ref, inject, reactive } from 'vue';

import { getRowFieldValue, setDefaultTableWidth, TABLE_LOG_FIELDS_SORT_REGULAR } from '@/common/util';
import { getSelectionRange, restoreSelectionRange } from '@/common/selection-util';
// import { perfStart, perfEnd } from '@/utils/performance-monitor';
import JsonFormatter from '@/global/json-formatter.vue';
import type { RetrieveRowRenderMeta } from '@/storage/utils/retrieve-render-meta';
import { getFieldNameByField } from '@/hooks/use-field-name';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import { UseSegmentProp } from '@/hooks/use-segment-pop';
import useStore from '@/hooks/use-store';
import useWheel from '@/hooks/use-wheel';

import PopInstanceUtil from '@/global/pop-instance-util';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { buildHighlightHtml, pageHighlightState, parseResultMarkedText } from '@/views/retrieve-core/page-highlight';
import RetrieveHelper, { RetrieveEvent } from '../../../retrieve-helper';
import ExpandView from '../../components/result-cell-element/expand-view.vue';
import OperatorTools from '../../components/result-cell-element/operator-tools.vue';
import RetrieveLoader from '@/skeleton/retrieve-loader.vue';
import { retrieveFieldCacheService, retrieveRowCacheService } from '@/storage';
import FullRowViewer from './full-row-viewer.vue';
import ScrollTop from '../../components/scroll-top/index';
import useSelectionSearch from '../../hooks/use-selection-search';
import useTextAction from '../../hooks/use-text-action';
import LogCell from './log-cell';
import LogResultException from './log-result-exception';
import {
  COLLECTOR_SOURCE_F,
  LOG_SOURCE_F,
  ROW_COLLECTOR,
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

/**
 * 日志检索结果行列表（table / 原始日志两种展示）。
 *
 * 职责概览：
 * - 列布局与列宽分配（固定列 + 可见字段列）
 * - 前端本地分页 / 后端 append 分页与首屏骨架
 * - 行展开、hover 操作栏、划词弹层（复制 / 高亮 / 添加到检索）
 * - 横向滚动与 wheel 预加载
 */

const FullRowViewerComponent = FullRowViewer as any;

/** 单行运行时配置（展开态、行高、粘性定位等），按 row 对象或 rowKey 缓存 */
type RowConfig = {
  expand?: boolean;
  isIntersect?: boolean;
  minHeight?: number;
  stickyTop?: number;
  rowMinHeight?: number;
};

export default defineComponent({
  props: {
    /** 内容展示类型：`table` 表格列模式 / 其它为原始日志模式 */
    contentType: {
      type: String,
      default: 'table',
    },
    /** 行工具栏点击回调（AI、全文查看、上下文等） */
    handleClickTools: {
      type: Function,
      default: undefined,
    },
  },
  setup(props, { emit }) {
    const store = useStore();
    const { $t } = useLocale();

    // —— DOM 引用 ——
    const refRootElement: Ref<HTMLElement> = ref();
    const refTableHead: Ref<HTMLElement> = ref();
    const refLoadMoreElement: Ref<HTMLElement> = ref();
    const refResultRowBox: Ref<HTMLElement> = ref();
    /** 划词弹层 tippy 内容容器 */
    const refSegmentContent: Ref<HTMLElement> = ref();
    const { handleOperation, getObjectValue, handleAddCondition } = useTextAction(emit, 'origin');

    // —— 划词选区状态 ——
    /** mouseup 时固化的选区 Range，供弹层操作回写 / 还原 */
    let savedSelection: Range = null;
    /** mouseup 时固化的划选原文，避免弹层点击后 live Range 文本漂移 */
    let savedSelectionText = '';
    /** 划选结束时的鼠标坐标，用于多矩形选区里挑最近的定位矩形 */
    let selectionAnchorPoint: { x: number; y: number } = null;
    /** 划词弹层的视口定位矩形（可随滚动刷新） */
    let selectionReferenceRect: DOMRect = null;
    /** tippy reference 占位节点（实际定位走 getReferenceClientRect） */
    let selectionPopAnchorEl: HTMLElement = null;
    /** 是否在行上按下，用于区分行内点击与外部 mouseup */
    let mousedownOnRow = false;
    /** hover 操作栏延迟隐藏定时器 */
    let hoverOperatorHideTimer: ReturnType<typeof setTimeout> = null;
    /** 字段设置布局变化后的延迟 reflow 定时器列表 */
    const layoutTimers: number[] = [];

    /** 行 hover 浮动操作栏（AI / 全文 / 上下文等）的可见态与定位 */
    const hoverOperatorState = reactive({
      visible: false,
      /** 鼠标或焦点仍在操作栏上时为 true，阻止延迟隐藏 */
      interacting: false,
      row: null,
      rowIndex: -1,
      top: 0,
      right: 12,
    });

    /**
     * 划词弹层的定位基准是选区矩形，这里实时读取而不是复用一次性快照，
     * 这样列表滚动时弹层能继续跟住被选中的文本。
     */
    const resolveSelectionReferenceRect = () => {
      if (savedSelection && selectionAnchorPoint) {
        selectionReferenceRect = getSelectionReferenceRect(savedSelection, selectionAnchorPoint);
      }

      return selectionReferenceRect ?? new DOMRect(0, 0, 1, 1);
    };

    /** 划词 tippy 实例：挂载到 body，fixed 策略兼容 monitor 宿主 */
    const popInstanceUtil = new PopInstanceUtil({
      refContent: () => refSegmentContent.value,
      tippyOptions: {
        hideOnClick: true,
        theme: 'segment-light',
        placement: 'bottom',
        appendTo: document.body,
        /**
         * 选区矩形来自 Range.getClientRects()，是视口坐标；
         * 因此 popper 必须使用 fixed 策略，否则会按文档坐标换算 —— 在
         * monitor 宿主（__IS_MONITOR_TRACE__）里弹层会被丢到视口左上角。
         * 与 search-bar 的 ui-input / sql-query 保持同一套宿主兼容策略。
         */
        getReferenceClientRect: () => resolveSelectionReferenceRect(),
        popperOptions: {
          strategy: 'fixed',
        },
      },
    });

    /**
     * 从选区 Range 中选取最接近鼠标落点的可视矩形，作为 tippy 定位基准。
     * 多行跨选时 getClientRects() 会返回多个矩形，直接用 bounding 矩形会偏中间。
     */
    const getSelectionReferenceRect = (range: Range, point: { x: number; y: number }) => {
      const rects = Array.from(range.getClientRects()).filter(rect => rect.width && rect.height);

      if (!rects.length) {
        const boundingRect = range.getBoundingClientRect();
        if (boundingRect.width || boundingRect.height) {
          return boundingRect;
        }

        /**
         * 选区已经拿不到任何可用矩形（例如 Range 已失效）时退回到鼠标位置。
         * 不能把全 0 的矩形交给 popper，否则弹层会被定位到视口左上角。
         */
        return new DOMRect(point.x, point.y, 1, 1);
      }

      return rects.reduce((closestRect, rect) => {
        const getDistance = (targetRect: DOMRect) => {
          const offsetX = point.x < targetRect.left ? targetRect.left - point.x : Math.max(point.x - targetRect.right, 0);
          const offsetY = point.y < targetRect.top ? targetRect.top - point.y : Math.max(point.y - targetRect.bottom, 0);
          return offsetX ** 2 + offsetY ** 2;
        };

        return getDistance(rect) < getDistance(closestRect) ? rect : closestRect;
      }, rects[rects.length - 1]);
    };

    /** 表格模式下可用的全量字段列（无可见字段时的兜底） */
    const fullColumns = ref([]);
    /** 当前内容展示类型，跟随 props.contentType */
    const showCtxType = ref(props.contentType);

    /**
     * 划词「添加到本次检索」入口。
     *
     * SelectionRange
     *   → addSelectionToCurrentSearch（字段类型 / 最小分词补齐）
     *   → emitAddCondition → resolveAddToSearch（UI + 语句统一）
     *   → handleAddCondition / setQueryCondition
     */
    const { stripSelectionMarkup, getFieldByName, addSelectionToCurrentSearch } = useSelectionSearch({
      handleAddCondition,
      getObjectValue,
      fullColumns,
      showCtxType,
      enableMinimalTokenCompletion: false,
    });

    const getSelectionTextByRange = (range?: Range | null) => stripSelectionMarkup(range?.toString?.() ?? '');

    /**
     * tippy 需要一个真实节点作为 reference（hideOnClick 等逻辑依赖它），
     * 但实际定位完全由 getReferenceClientRect 提供，所以这里只是一个身份占位节点。
     *
     * 必须每个组件实例独占一个节点：APM 与 Trace 在宿主页里是两个独立构建产物，
     * 若按 class 去 body 上查找复用同一个节点，两个包会互相覆盖对方的定位基准。
     */
    const getSelectionPopAnchor = () => {
      if (!selectionPopAnchorEl?.isConnected) {
        selectionPopAnchorEl = document.createElement('span');
        selectionPopAnchorEl.className = 'bklog-selection-pop-target';
        selectionPopAnchorEl.style.cssText
          = 'position: fixed; top: 0; left: 0; width: 1px; height: 1px; visibility: hidden; pointer-events: none; z-index: -1;';
        document.body.appendChild(selectionPopAnchorEl);
      }

      return selectionPopAnchorEl;
    };

    /** 划词分段操作弹层（复制 / 添加到检索 / 高亮 / AI 等） */
    const useSegmentPop = new UseSegmentProp({
      delineate: true,
      aiBluekingEnabled: store.state.features.isAiAssistantActive,
      stopPropagation: true,
      highlightEnabled: true,
      allowDelineateSearch: true,
      onclick: (...args) => {
        const type = args[1];
        const selectionValue = savedSelectionText || getSelectionTextByRange(savedSelection);
        // 复制只处理剪贴板，不参与任何检索条件添加；显式提前返回，避免后续事件链误落到“添加到本次检索”。
        if (type === 'copy') {
          handleOperation('copy', { value: selectionValue });
          popInstanceUtil.hide();
          return;
        }
        if (type === 'add-to-ai') {
          props.handleClickTools(type, selectionValue);
        } else if (type === 'is' && savedSelection && hoverOperatorState.row) {
          addSelectionToCurrentSearch(savedSelection, hoverOperatorState.row, savedSelectionText);
        } else if (type === 'highlight') {
          // 仅划词弹层「高亮」：保留整串关键词；跨分词命中由渲染侧拼接匹配保证完整高亮
          const selectionText = selectionValue.trim();
          if (selectionText) {
            RetrieveHelper.fire(RetrieveEvent.HILIGHT_TRIGGER, {
              event: 'mark',
              value: selectionText,
            });
          }
        } else {
          handleOperation(type, { value: selectionValue, operation: type });
        }
        popInstanceUtil.hide();
        restoreSelectionRange(savedSelection);

        // 添加到检索后必须清空选区：若还原划选，下次点击会被判定为“点在选区上”
        // 从而误走划词链路，表现为同词多次操作 KEY/操作符漂移。
        if (type === 'is' || type === 'not' || type === 'new-search-page-is') {
          window.getSelection()?.removeAllRanges();
          savedSelection = null;
          savedSelectionText = '';
        } else if (savedSelection) {
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(savedSelection);
        }
      },
    });

    // —— 分页与渲染列表 ——
    /** 前端本地分页页码（从 1 开始） */
    const handleRelatedTraceClick = inject<any>('handleRelatedTraceClick');

    const pageIndex = ref(1);
    /** 前端本地分页每页条数 */
    const pageSize = ref(50);
    const isRending = ref(false);

    /** 按 row 对象弱引用缓存行配置（展开态等） */
    let tableRowConfig = new WeakMap();
    /** 按 rowKey 强引用缓存行配置，跨对象重建时仍可命中 */
    const tableRowConfigByKey = new Map();
    /** 检索进行中（首屏搜索） */
    const isPageLoading = ref(RetrieveHelper.isSearching);
    /** 后端 append 分页请求进行中 */
    const isPaginationLoading = ref(false);
    // 前端本地分页 loadmore 触发器：
    // renderList 没有使用响应式，这里需要手动触发更新，所以这里使用一个计数器来触发更新
    const localUpdateCounter = ref(0);
    /** 是否还有更多数据可加载（本地分页未耗尽或后端仍有下一页） */
    const hasMoreList = ref(true);
    /**
     * 当前实际渲染的行列表（非响应式，配合 localUpdateCounter 驱动视图更新）。
     * 项结构：{ item, renderMeta, [ROW_KEY] }
     */
    let renderList = Object.freeze([]);
    /** 递增令牌：丢弃过期的 setRenderList / IndexedDB 异步结果 */
    let renderTaskToken = 0;
    /** 递增令牌：丢弃过期的后端分页响应 */
    let paginationRequestToken = 0;
    /** 后端分页单飞锁，避免 IntersectionObserver 与 wheel 预加载并发取消 */
    let paginationRequestPromise: Promise<boolean> | null = null;
    const isRequesting = ref(false);
    let requestingTimer: ReturnType<typeof setTimeout> = null;
    /**
     * 分页 append 结束时跳过「loading 结束重置横向滚动」：
     * append 不应把用户已滚动的位置拉回左侧。
     */
    let skipNextLoadingEndReset = false;
    /** 全文行查看器（字段截断后的完整内容） */
    const fullRowViewerState = reactive({
      visible: false,
      rowKey: '',
      rowData: null as Record<string, any> | null,
      truncatedFields: [] as string[],
    });

    // —— Store 派生状态 ——
    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const filteredFieldList = computed(() => store.getters.filteredFieldList);
    const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
    const visibleFields = computed(() => store.getters.visibleFields);
    const indexSetOperatorConfig = computed(() => store.state.indexSetOperatorConfig);
    const tableShowRowIndex = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX]);
    const showFieldAlias = computed(() => store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]);
    const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
    const timeField = computed(() => indexFieldInfo.value.time_field);
    const timeFieldType = computed(() => indexFieldInfo.value.time_field_type);
    const isLoading = computed(() => indexSetQueryResult.value.is_loading || indexFieldInfo.value.is_loading);
    /** 展开行 KV 视图可展示的字段名列表 */
    const kvShowFieldsList = computed(() => filteredFieldList.value?.map(f => f.field_name));
    const userSettingConfig = computed(() => store.state.retrieve.catchFieldCustomConfig);
    /** 字段宽度等配置的作用域（索引集 / 默认） */
    const fieldScope = computed(() => indexFieldInfo.value.field_scope || store.state.indexId || 'default');
    /** IndexedDB 行缓存 key 列表；有值时优先走缓存渲染路径 */
    const rowKeys = computed<string[]>(() => indexSetQueryResult.value?.row_keys ?? []);
    const tableDataSize = computed(() => rowKeys.value.length || (indexSetQueryResult.value?.list?.length ?? 0));
    const isUnionSearch = computed(() => store.getters.isUnionSearch);
    /** 内存中的结果 list（无 row_keys 时的兜底数据源） */
    const tableList = computed<any[]>(() => Object.freeze(indexSetQueryResult.value?.list ?? []));
    /** 日志级别着色配置 */
    const gradeOption = computed(() => store.state.indexFieldInfo.custom_config?.grade_options ?? { disabled: false });
    const indexSetType = computed(() => store.state.indexItem.isUnionIndex);
    /** 单元格 JSON 内容最多展示行数 */
    const limitRow = computed(() => {
      // if (store.state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT]) {
      //   return 'auto';
      // }

      return store.state.storage[BK_LOG_STORAGE.RESULT_DISPLAY_LINES];
    });

    /** 通知消费方字段宽度计算结果已更新 */
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
    const isShowCollectorField = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_COLLECTOR_FIELD]);
    const flatIndexSetList = computed(() => store.state.retrieve.flatIndexSetList);
    const isSceneMode = computed(() => store.getters.isSceneMode);
    /** 列布局版本号：变更时强制 getFieldColumns 重算 */
    const columnLayoutVersion = ref(0);
    /**
     * 首屏列宽布局未稳定前为 true，此时用骨架屏挡住真实行，
     * 避免 monitor 包外部挂载时首帧列宽抖动。
     */
    const isFirstPageLayoutPending = ref(false);
    /** 递增令牌：取消过期的 scheduleFirstPageTableReveal */
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
      renderTaskToken += 1;
      paginationRequestToken += 1;
      paginationRequestPromise = null;
      requestingTimer && clearTimeout(requestingTimer);
      requestingTimer = null;
      isRequesting.value = false;
      isPaginationLoading.value = false;
      skipNextLoadingEndReset = false;
      renderList = Object.freeze([]);
      localUpdateCounter.value += 1;
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

    /**
     * 按目标长度同步 renderList。
     * - 有 rowKeys：从 IndexedDB 增量读取，尽量复用已有前缀，避免整表重建
     * - 无 rowKeys：直接从 tableList 切片构造
     * @param length 目标渲染条数；缺省为当前 tableDataSize
     */
    const setRenderList = (length?: number) => {
      renderTaskToken += 1;
      const taskToken = renderTaskToken;
      const queryKey = indexSetQueryResult.value?.row_query_key ?? '';
      const endIndex = length ?? tableDataSize.value;

      if (rowKeys.value.length) {
        const lastIndex = Math.min(endIndex, rowKeys.value.length);
        const targetKeys = rowKeys.value.slice(0, lastIndex);
        const reusableLength = Math.min(renderList.length, lastIndex);
        const canReusePrefix = Array.from({ length: reusableLength }).every(
          (_, index) => renderList[index]?.[ROW_KEY] === targetKeys[index],
        );

        // 本地分页回到较短列表时直接裁剪，不重新读取 IndexedDB 和重建已有行。
        if (canReusePrefix && renderList.length >= lastIndex) {
          if (renderList.length !== lastIndex) {
            renderList = renderList.slice(0, lastIndex);
            localUpdateCounter.value += 1;
          }
          return;
        }

        // 后端分页只读取并追加新增区间。旧实现每次都重新读取 0..N 行，
        // 同时替换所有 row 对象，600 行后会导致整表重复 diff、布局和绘制。
        const startIndex = canReusePrefix ? renderList.length : 0;
        const keysToLoad = targetKeys.slice(startIndex);
        if (!keysToLoad.length) {
          return;
        }

        retrieveRowCacheService.getRenderEntries(keysToLoad).then((entries) => {
          const isCurrentTask = taskToken === renderTaskToken
            && queryKey === (indexSetQueryResult.value?.row_query_key ?? '')
            && targetKeys.every((key, index) => key === rowKeys.value[index])
            && (!startIndex || Array.from({ length: startIndex }).every(
              (_, index) => renderList[index]?.[ROW_KEY] === targetKeys[index],
            ));
          if (!isCurrentTask) {
            return;
          }

          const nextRows = entries.flatMap((entry, index) => (entry ? [{
            item: entry.row,
            renderMeta: entry.renderMeta as RetrieveRowRenderMeta | undefined,
            [ROW_KEY]: keysToLoad[index] ?? getRowCacheKey(entry.row, startIndex + index),
          }] : []));
          renderList = startIndex ? renderList.concat(nextRows) : nextRows;
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
      localUpdateCounter.value += 1;
    };

    const searchContainerHeight = ref(52);
    const resultContainerId = ref(RetrieveHelper.logRowsContainerId);
    const resultContainerIdSelector = `#${resultContainerId.value}`;

    /**
     * 行对象 → 渲染元信息（截断字段、rowKey）的弱引用映射。
     * 避免把 meta 挂到业务 row 上造成污染，同时随 GC 自动回收。
     */
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

    /** 行内是否有字段被截断，决定是否展示「全文」入口 */
    const shouldShowFullRowAction = (row: Record<string, any>) => {
      const meta = getRowRenderMeta(row);
      return !!meta?.hasTruncatedField;
    };

    /** 打开全文查看器；若已打开则先关后开以强制刷新内容 */
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

    /** 原始日志模式的两列：时间 + 原文 JSON */
    const originalColumns = computed(() => {
      const formatDate = store.state.isFormatDate;
      // 依赖划词高亮 version，确保时间列在关键字变化后同步重绘
      void pageHighlightState.version;
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
            const fieldName = timeField.value;
            const rawValue = row[fieldName];
            const formatValue = formatDate
              ? RetrieveHelper.formatTimeZoneValue(rawValue, fieldType, timezone)
              : (rawValue === null || rawValue === undefined || rawValue === '' ? '--' : rawValue);
            // formatTimeZoneValue 可能返回 <mark>格式化时间</mark>，需先解析再渲染，避免标签被 escape
            const { plainText, markRanges } = parseResultMarkedText(formatValue);
            const displayText = plainText || String(formatValue ?? '');

            return h(
              'span',
              {
                class: 'time-field',
                // 划词添加到本次检索时，通过 data-field-name 定位真实时间字段
                attrs: {
                  'data-field-name': fieldName,
                },
                domProps: {
                  // resultRanges 还原检索结果 mark；同时叠加页面划词高亮
                  innerHTML: buildHighlightHtml({
                    text: displayText,
                    resultRanges: markRanges,
                  }),
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
                onMenu-click={({ option, isLink }) => handleMenuClick(option, isLink, {
                  row,
                  field: getFieldByName(option.fieldName),
                })}
              />
            );
          },
        },
      ];
    });

    /**
     * 将索引字段描述转为表头/单元格列配置（含排序头、JSON 单元格渲染）。
     */
    const formatColumn = (field) => {
      return {
        field: field.field_name,
        key: field.field_name,
        title: getFieldNameByField(field, store),
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

    /** 将列宽配置统一为数字；百分比宽度退回 fallback */
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

    /** 字段列与容器宽度之间的安全间隙，避免贴边出现横向溢出抖动 */
    const TABLE_WIDTH_SAFE_GAP = 4;

    /** 左侧固定列总宽度（展开 / 序号 / 来源 / 采集项） */
    const getFixedColumnsWidth = () => {
      const expandColumnWidth = 36;
      const rowIndexColumnWidth = tableShowRowIndex.value ? 50 : 0;
      const sourceColumnWidth = isShowSourceField.value && indexSetType.value ? 230 : 0;
      const collectorColumnWidth = isShowCollectorField.value && isSceneMode.value ? 230 : 0;

      return expandColumnWidth + rowIndexColumnWidth + sourceColumnWidth + collectorColumnWidth;
    };

    /** 字段列可分配的剩余宽度 */
    const getFieldsAvailableWidth = () => offsetWidth.value - getFixedColumnsWidth() - TABLE_WIDTH_SAFE_GAP;

    const getColumnWidthTotal = (columnList: Record<string, any>[]) => {
      return columnList.reduce((total, item) => total + getNumericWidth(item.width, item.minWidth), 0);
    };

    /** 多余宽度优先分给 log / text / 宽列，避免空白挤在窄字段上 */
    const getExtraWidthTargetColumns = (columnList: Record<string, any>[]) => {
      const longTextColumns = columnList.filter((item) => {
        return item.field === 'log' || item.field_type === 'text' || getNumericWidth(item.width) >= 800;
      });

      return longTextColumns;
    };

    /**
     * 当字段列总宽小于可用宽度时，把差额均分给长文本列。
     */
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
    /** 字段列配置：table 模式走可见字段，否则走原始日志双列 */
    const getFieldColumns = computed(() => {
      columnLayoutVersion.value;
      // 别名开关变化时重建 title / header 文案，不改 column key
      showFieldAlias.value;

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

    /** 展开后高亮展开面板内的检索命中 */
    const hanldeAfterExpandClick = (target: HTMLElement) => {
      const expandTarget = target
        .closest('.bklog-row-container')
        ?.querySelector('.bklog-row-observe .expand-view-wrapper');
      if (expandTarget) {
        RetrieveHelper.highlightElement(expandTarget as HTMLElement);
      }
    };

    /** 左侧固定列：展开、行号、联合检索来源、场景化采集项 */
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
      {
        field: '',
        key: ROW_COLLECTOR,
        title: '来源采集项',
        width: 230,
        align: 'left',
        resize: false,
        fixed: 'left',
        disabled: !(isShowCollectorField.value && isSceneMode.value),
        renderBodyCell: ({ row }) => {
          const rowIndexSetId = row.__index_set_id__;
          const collectorName = rowIndexSetId !== null
            ? flatIndexSetList.value.find(
              item => item.index_set_id === String(rowIndexSetId),
            )?.index_set_name ?? '--'
            : '--';
          const hanldeSoureClick = (event) => {
            event.stopPropagation();
            event.preventDefault();
            event.stopImmediatePropagation();
          };

          return <span onClick={hanldeSoureClick}>{collectorName}</span>;
        },
      },
    ]);

    /** 行 AI 助手入口：高亮当前行并回调父级工具栏 */
    const handleRowAIClcik = (e: MouseEvent, row: any, rowIndex: number) => {
      const displayRowIndex = ensureTableRowConfig(row, rowIndex).value[ROW_INDEX] + 1;
      const targetRow = (e.target as HTMLElement).closest('.bklog-row-container');
      const oldRow = targetRow?.parentElement.querySelector('.bklog-row-container.ai-active');

      oldRow?.classList.remove('ai-active');
      targetRow?.classList.add('ai-active');

      props.handleClickTools('ai', row, indexSetOperatorConfig.value, displayRowIndex);
    };

    /** 单元格图标操作（复制、添加到检索等）统一转发到 useTextAction */
    const handleIconClick = (type, content, field, row, isLink, depth, isNestedField) => {
      handleOperation(type, { content, field, row, isLink, depth, isNestedField, operation: type });
    };

    /** JSON / 分词菜单点击：时间字段需取原始时间戳构造检索条件 */
    const handleMenuClick = (option, isLink, fieldOption?: { row: any; field?: any }) => {
      if (window.__IS_MONITOR_APM__ && isLink && option.operation === 'trace-view') {
        const apmRelation = store.state.indexSetFieldConfig?.apm_relation;
        const { app_name: appName, bk_biz_id: bkBizId } = apmRelation.extra;
        handleRelatedTraceClick({
          appName,
          bkBizId,
          traceId: option.value,
        });
        return;
      }
      const timeTypes = ['date', 'date_nanos'];
      const field = fieldOption?.field ?? getFieldByName(option.fieldName);
      const fieldType = field?.field_type ?? option.fieldType;

      handleOperation(option.operation, {
        ...option,
        // 时间格式化只影响展示；构造检索条件时必须回取当前行中的原始时间戳。
        value: timeTypes.includes(fieldType) && fieldOption?.row && field
          ? String(getObjectValue(fieldOption.row, field)).replace(/<\/?mark>/gim, '')
          : option.value,
        fieldName: option.fieldName,
        operation: option.operation,
        field,
        isLink,
        depth: option.depth,
        displayFieldNames: option.displayFieldNames,
        fullPlain: option.fullPlain,
        isSoleToken: option.isSoleToken,
        tokenIndex: option.tokenIndex,
        tokenCount: option.tokenCount,
      });
    };

    const { renderHead } = useHeaderRender();
    /**
     * 可见字段为空时的兜底渲染字段：优先 log/body，否则取前 4 个可渲染字段。
     */
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
    /**
     * 构建 fullColumns：时间 → log → 其它索引字段，并基于样本行估算默认列宽。
     * 清空全部可见字段后表格依赖此列表兜底展示。
     */
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
      if (isSceneMode.value && isShowCollectorField.value) {
        sortFieldsList.unshift(COLLECTOR_SOURCE_F());
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

    /** 行配置默认值（目前仅 expand=false） */
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

    /**
     * 获取或创建行运行时配置（展开态、显示序号等）。
     * 优先按 rowKey 命中，再回落到 WeakMap(row)，保证对象重建后状态不丢。
     */
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

    /** 延迟关闭 isRequesting，避免短间隔内重复触发加载态闪烁 */
    const debounceSetLoading = (delay = 120) => {
      requestingTimer && clearTimeout(requestingTimer);
      requestingTimer = setTimeout(() => {
        isRequesting.value = false;
      }, delay);
    };

    /** 行展开面板渲染配置（KV 字段列表） */
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
            render-meta={getRowRenderMeta(row)}
            row-index={realRowIndex}
            row-key={getRowComponentKey(row) || rowKeys.value[realRowIndex] || ''}
            onValue-click={(type, content, isLink, field, depth, isNestedField) => {
              return handleIconClick(type, content, field, row, isLink, depth, isNestedField);
            }}
          />
        );
      },
    };

    /** 首屏渲染前同步结果区尺寸（由下方 useLazyRender 后再赋值实现） */
    let syncResultBoxRectBeforeRender = () => {};
    /** 首屏列宽稳定后再揭开真实行（由下方赋值实现） */
    let scheduleFirstPageTableReveal = () => {};

    /**
     * 数据量变化时刷新 renderList；
     * 若仍在等首屏布局，先同步尺寸并调度揭开。
     */
    const resetRowListState = () => {
      const shouldWaitFirstPageLayout = isFirstPageLayoutPending.value && tableDataSize.value > 0;

      if (shouldWaitFirstPageLayout) {
        syncResultBoxRectBeforeRender();
      }

      setRenderList(null);
      debounceSetLoading();

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
      () => [tableShowRowIndex.value, isShowSourceField.value, indexSetType.value, isShowCollectorField.value, isSceneMode.value],
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
    /**
     * 可见字段变化后重算列宽并触发横向布局刷新。
     * 用 layoutToken 丢弃过期的异步样本行读取结果。
     */
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

    /** 标记列宽拖拽进行中，短暂抑制 resize 时重置横向滚动 */
    const markColumnWidthChanging = () => {
      isColumnWidthChanging = true;
      window.clearTimeout(columnWidthChangeTimer);
      columnWidthChangeTimer = window.setTimeout(() => {
        isColumnWidthChanging = false;
      }, 300);
    };

    /** 列宽变更后尽量保持用户当前的横向滚动位置 */
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

    /**
     * 用户拖拽列宽：缩小时把差额补给 log/长文本列，并持久化到用户字段配置。
     */
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

    /** 从分页接口响应中解析本页条数，用于判断是否还有下一页 */
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

    /**
     * 加载更多：
     * 1) 本地分页未耗尽 → 仅扩大 renderList
     * 2) 本地已展示完当前已拉取数据 → 发起后端 append 分页（单飞）
     */
    const loadMoreTableData = () => {
      // IntersectionObserver 与 wheel 预加载可能在同一帧命中。Promise 锁用于保证后端分页严格单飞，
      // 不依赖会被渲染定时器重置的 isRequesting，避免后一请求取消前一请求。
      if (paginationRequestPromise) {
        return paginationRequestPromise;
      }

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
        requestingTimer && clearTimeout(requestingTimer);
        requestingTimer = null;
        isRequesting.value = true;
        pageIndex.value += 1;
        const maxLength = Math.min(pageSize.value * pageIndex.value, tableDataSize.value);
        setRenderList(maxLength);
        debounceSetLoading(0);
        return Promise.resolve(false);
      }

      if (hasMoreList.value) {
        paginationRequestToken += 1;
        const requestToken = paginationRequestToken;
        const requestQueryKey = indexSetQueryResult.value?.row_query_key ?? '';
        const requestStartSize = rowKeys.value.length;
        requestingTimer && clearTimeout(requestingTimer);
        requestingTimer = null;
        isRequesting.value = true;
        isPaginationLoading.value = true;
        skipNextLoadingEndReset = true;
        const currentPromise = store
          .dispatch('requestIndexSetQuery', { isPagination: true })
          .then((resp) => {
            const isCurrentRequest = requestToken === paginationRequestToken
              && requestQueryKey === (indexSetQueryResult.value?.row_query_key ?? '')
              && !resp?.ignored;
            if (!isCurrentRequest) {
              return false;
            }

            const responseSize = getPaginationResponseSize(resp);
            if (rowKeys.value.length < requestStartSize) {
              return false;
            }

            pageIndex.value += 1;
            handleResultBoxResize(false);

            if (responseSize !== null && responseSize < pageSize.value) {
              hasMoreList.value = false;
            }
            return true;
          })
          .finally(() => {
            if (requestToken !== paginationRequestToken) {
              return;
            }
            paginationRequestPromise = null;
            isPaginationLoading.value = false;
            debounceSetLoading(0);
            nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
          });
        paginationRequestPromise = currentPromise;
        return currentPromise;
      }

      return Promise.resolve(false);
    };

    useResizeObserve(SECTION_SEARCH_INPUT, (entry) => {
      searchContainerHeight.value = entry.contentRect.height;
    });

    let scrollXOffsetLeft = 0;
    const refScrollXBar = ref();

    /** 回到顶部后重置为第一页可见窗口 */
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

    // 监听滚动条滚动位置，判定是否需要拉取更多数据
    const { offsetWidth, scrollWidth, computeRect, computeRectSync, getScrollElement } = useLazyRender({
      loadMoreFn: loadMoreTableData,
      container: resultContainerIdSelector,
      rootElement: refRootElement,
      refLoadMoreElement,
    });

    /** 首屏渲染前同步结果区宽度，并 bump 列布局版本 */
    syncResultBoxRectBeforeRender = () => {
      computeRectSync(refResultRowBox.value);
      triggerColumnLayoutReflow();
    };

    /**
     * 双 rAF + nextTick：等浏览器完成列宽布局后再关闭首屏骨架，避免列宽抖动。
     */
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

    /** 同步表头 transform 与内容区 scrollLeft，实现自定义横向滚动 */
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

    /** 容器宽度变化后重算横向滚动，必要时清零偏移 */
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

    /** 左侧字段设置面板显隐/宽度变化时重置横向滚动并多次延迟 reflow */
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

    // —— Wheel 预加载与横向滚动 ——
    const isPreloading = ref(false);     // 是否正在预加载
    const preloadThreshold = 32 * 50;        // 距离底部多少 px 开始预加载
    let lastPreloadTime = 0;
    const preloadCooldown = 300;         // ms

    /** 向下滚动且接近底部时触发预加载（带冷却） */
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

    /** 是否存在真实业务异常（排除用户主动 cancel） */
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

    /** 无数据且检索中：进入首屏骨架条件之一 */
    const shouldEnterFirstPageSkeleton = computed(() => {
      return (
        !hasResultException.value
        && !isPaginationLoading.value
        && tableDataSize.value === 0
        && (isLoading.value || isPageLoading.value || isRequesting.value)
      );
    });

    /** 是否展示首屏骨架（含字段加载中、布局待稳定） */
    const shouldShowFirstPageSkeleton = computed(() => {
      if (hasResultException.value || isPaginationLoading.value) {
        return false;
      }

      return shouldEnterFirstPageSkeleton.value || isFieldLoadingForFirstPage.value || isFirstPageLayoutPending.value;
    });

    /** 骨架展示期间屏蔽表头与真实行渲染 */
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

    /** 将列宽配置转为单元格内联 style（支持 number / 百分比 / 100% 通栏） */
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

    /** 最终渲染列 = 左侧固定列 + 字段列，过滤 disabled */
    const allColumns = computed(() => {
      const columns = [...leftColumns.value, ...getFieldColumns.value].filter(
        item => !(item as any).disabled,
      );
      return columns;
    });

    // —— 行 hover 浮动操作栏 ——
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

    /**
     * 按行相对视口位置更新浮动操作栏坐标。
     * 使用 fixed 浮层，避免被 .bklog-result-container overflow 裁切。
     */
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

    /** 渲染单行单元格 +（可选）展开面板 */
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

    /** 行 mousedown：记录按下态并清空旧选区，为划词 / 点击展开做准备 */
    const handleRowMousedown = (e: MouseEvent) => {
      mousedownOnRow = true;

      if (RetrieveHelper.isClickOnSelection(e, 2)) {
        RetrieveHelper.stopEventPropagation(e);
        return;
      }

      RetrieveHelper.setMousedownEvent(e);
      savedSelection = null;
      savedSelectionText = '';
    };

    /**
     * 行 mouseup：
     * - 有划选文本 → 弹出划词操作层
     * - 点击展开图标 / 行空白 → 切换展开
     * - 点击分词等内容 → 不联动外层行展开
     */
    const handleRowMouseup = (e: MouseEvent, item: any, rowIndex: number) => {
      if (!mousedownOnRow) {
        RetrieveHelper.setMousedownEvent(null);
        return;
      }

      // 选中文本不弹出复制等选项框
      // if (window.__IS_MONITOR_TRACE__ && window.getSelection().toString().length > 1) {
      //   RetrieveHelper.setMousedownEvent(null);
      //   return;
      // }

      mousedownOnRow = false;

      if (RetrieveHelper.isClickOnSelection(e, 2) || RetrieveHelper.isMouseSelectionUpEvent(e)) {
        RetrieveHelper.stopEventPropagation(e);
        RetrieveHelper.setMousedownEvent(null);

        /**
         * 选区必须按行容器所在的 shadow root 读取：monitor Trace 宿主把日志组件挂在
         * `<trace-explore>` 的 shadow root 内，document 选区会被 retarget 到 shadow host 所在的树，
         * 拿到的 Range 端点是 `div.trace-wrap-iframe`，toString() 为空串，
         * 复制 / 高亮 / 添加到本次检索都会失效。
         */
        const selectionRange = getSelectionRange(refRootElement.value ?? (e.target as Node));
        if (getSelectionTextByRange(selectionRange).length) {
          savedSelection = selectionRange;
          selectionAnchorPoint = { x: e.clientX, y: e.clientY };
          selectionReferenceRect = getSelectionReferenceRect(savedSelection, selectionAnchorPoint);
          popInstanceUtil.uninstallInstance();
          popInstanceUtil.show(getSelectionPopAnchor(), true, true);
        }
        return;
      }

      const target = e.target as HTMLElement;
      const expandPanel = target.closest('.bklog-row-observe')?.querySelector('.expand-view-wrapper');

      // 仅「展开图标」或「行空白」触发行展开/收起；
      // 分词等内容点击只响应自身下拉，不联动外层 ROW。
      const isExpandIconClick = Boolean(target.closest('.bklog-expand-icon'));
      const isRowContentClick = Boolean(
        target.closest(
          [
            '.valid-text',
            '.others-text',
            '.blob-text',
            '.segment-content',
            '.field-value',
            '.field-name',
            '.black-mark',
            '.bklog-root-field',
            '.bklog-json-view-node',
            '.bklog-json-view-row',
            '.bklog-json-view-field',
            '.bklog-json-view-text',
            '.bklog-json-view-object',
            '.bklog-word-segment',
            '.btn-more-action',
            '.btn-json-leaf-more',
            '.btn-original-value-action',
            'a',
            'button',
            'input',
            'textarea',
            '[role="button"]',
            '.bk-link-text',
          ].join(', '),
        ),
      );

      if (!isExpandIconClick && (isRowContentClick || expandPanel?.contains(target))) {
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

    /** 渲染当前页可见行（含日志级别 class、hover 操作态） */
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

    /** 更新底部 load-more 占位文案与宽度 */
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
    /** 空态 / 异常态展示类型，供 LogResultException 消费 */
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
      renderTaskToken += 1;
      paginationRequestToken += 1;
      clearHoverOperatorHideTimer();
      popInstanceUtil.uninstallInstance();
      selectionPopAnchorEl?.remove();
      selectionPopAnchorEl = null;
      savedSelection = null;
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
          data-page-highlight-version={pageHighlightState.version}
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
