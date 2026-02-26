/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import {
  type PropType,
  computed,
  defineComponent,
  inject,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
} from 'vue';

import * as authorityMap from 'apm/pages/home/authority-map';
import { traceDetail } from 'monitor-api/modules/apm_trace';

import SpanDetails from '../../../pages/main/span-details';
import { QUERY_TRACE_RELATION_APP } from '../../../store/constant';
import { useAuthorityStore } from '../../../store/modules/authority';
import { useTraceStore } from '../../../store/modules/trace';
import { useChildrenHiddenInject } from '../hooks';
import ListView from './list-view';

import type { Span, TNil, Trace } from '../typings';

import './virtualized-trace-view.scss';

type RowState = {
  bgColorIndex?: number;
  isDetail: boolean;
  span: Span;
  spanIndex: number;
};

const VirtualizedTraceViewProps = {
  registerAccessors: Function as PropType<(accesors: any) => void>,
  setSpanNameColumnWidth: Function as PropType<(width: number) => void>,
  setTrace: Function as PropType<(trace: TNil | Trace, uiFind: string | TNil) => void>,
  focusUiFindMatches: Function as PropType<(trace: Trace, uiFind: string | TNil, allowHide?: boolean) => void>,
  shouldScrollToFirstUiFindMatch: {
    type: Boolean,
  },
  uiFind: {
    type: String,
  },
  detailStates: {
    type: Object,
  },
  hoverIndentGuideIds: {
    type: Array as PropType<string[]>,
  },
  spanNameColumnWidth: {
    type: Number,
  },
  traceID: {
    type: String,
  },
  handleShowSpanDetail: Function as PropType<(span: Span) => void>,
};

export function generateRowStates(
  spans: Span[] | TNil,
  childrenHiddenIDs: Set<unknown>,
  detailStates: Record<string, any> | undefined
): RowState[] {
  if (!spans) {
    return [];
  }

  let collapseDepth = null;
  let rowStates: RowState[] = [];
  for (let i = 0; i < spans.length; i++) {
    const span = spans[i];
    const { spanID, depth } = span;
    let hidden = false;

    if (collapseDepth != null) {
      if (depth >= collapseDepth) {
        hidden = true;
      } else {
        collapseDepth = null;
      }
    }
    if (hidden) {
      continue;
    }
    if (childrenHiddenIDs.has(spanID)) {
      collapseDepth = depth + 1;
    }
    rowStates.push({
      span,
      isDetail: false,
      spanIndex: i,
    });
    if (detailStates?.has(spanID)) {
      rowStates.push({
        span,
        isDetail: true,
        spanIndex: i,
      });
    }
  }
  rowStates = handleSetBgColorIndex(rowStates);

  return rowStates;
}

/** 设置背景色层级 */
function handleSetBgColorIndex(list: RowState[]) {
  let bgColorIndex = 0;
  return list.map((item: RowState, index: number) => {
    if (index) {
      const curDepth = item.span.depth;
      const prevDepth = list[index - 1]?.span.depth;
      if (curDepth !== prevDepth) {
        // 与上一层层级不同则说明为间隔新区间
        bgColorIndex += 1;
      }
    }

    return { ...item, bgColorIndex };
  });
}

export const DEFAULT_HEIGHTS = {
  bar: 28,
  detail: 161,
  detailWithLogs: 197,
};

export default defineComponent({
  name: 'VirtualizedTraceView',
  props: VirtualizedTraceViewProps,
  emits: ['showSpanDetail'],
  setup(props) {
    const store = useTraceStore();
    const authorityStore = useAuthorityStore();
    const virtualizedTraceViewElm = ref();
    const listViewElm = ref(null);
    const haveReadSpanIds = ref<string[]>([]);
    const showSpanDetails = ref(false);
    const spanDetails = ref<null | Span>(null);
    const activeTab = shallowRef('BasicInfo');
    /** 缓存的滚动容器元素引用，避免重复 DOM 查询 */
    let cachedContainer: HTMLElement | null = null;
    /** 缓存的吸顶区域高度（Tab栏 + 工具栏），避免重复计算 */
    let cachedStickyHeight: null | number = null;

    const childrenHiddenStore = useChildrenHiddenInject();
    const isFullscreen = inject('isFullscreen', false);

    const traceTree = computed(() => store.traceTree);
    const spans = computed(() => store.spanGroupTree);
    const getRowStates = computed<RowState[]>(() => {
      const { detailStates } = props;

      return traceTree.value
        ? generateRowStates(spans.value, childrenHiddenStore?.childrenHiddenIds.value, detailStates)
        : [];
    });
    /**
     * @description 获取当前组件所属的根节点，用于 DOM 查询和事件监听
     * 在微前端 Shadow DOM 环境下，使用 getRootNode() 获取 ShadowRoot，确保能正确查找子应用内的元素
     * @returns {Document} 当前组件所属的根节点（ShadowRoot 或 Document）
     */
    function getRootNode(): Document {
      return virtualizedTraceViewElm.value?.getRootNode?.() || document;
    }

    onMounted(() => {
      // 在 window 上监听键盘事件，避免微前端 Shadow DOM 环境下 DOM 层级不确定导致事件无法捕获
      window.addEventListener('keydown', handleKeydown);
    });

    onUnmounted(() => {
      window.removeEventListener('keydown', handleKeydown);
    });

    /**
     * @description 判断当前焦点是否在输入元素内
     * @returns {boolean} 如果焦点在输入框、文本域或可编辑元素内返回 true，否则返回 false
     */
    function isInputElementFocused(): boolean {
      const rootNode = getRootNode();
      const activeElement = rootNode.activeElement;
      return (
        activeElement instanceof HTMLInputElement ||
        activeElement instanceof HTMLTextAreaElement ||
        activeElement?.getAttribute('contenteditable') === 'true'
      );
    }

    /**
     * @description 获取可导航的 span 行列表（过滤掉详情行）
     * @returns {RowState[]} 可导航的行状态数组
     */
    function getNavigableRows(): RowState[] {
      return getRowStates.value.filter(row => !row.isDetail);
    }

    /**
     * @description 获取当前选中 span 在列表中的索引
     * @param {RowState[]} rows - 可导航的行状态数组
     * @returns {number} 当前选中 span 的索引，未找到返回 -1
     */
    function getCurrentSpanIndex(rows: RowState[]): number {
      return rows.findIndex(row => row.span.spanID === spanDetails.value?.spanID);
    }

    /**
     * @description 导航到上一个 span，选中并滚动到该位置
     * @param {RowState[]} rows - 可导航的行状态数组
     * @returns {void}
     */
    function navigateToPrevSpan(rows: RowState[]): void {
      const currentIndex = getCurrentSpanIndex(rows);
      const prevIndex = currentIndex > 0 ? currentIndex - 1 : 0;
      const prevSpan = rows[prevIndex]?.span;
      if (prevSpan) {
        selectSpan(prevSpan);
        scrollToSpan(prevSpan.spanID, 'up');
      }
    }

    /**
     * @description 导航到下一个 span，选中并滚动到该位置。如果当前没有选中任何 span，则选中第一个
     * @param {RowState[]} rows - 可导航的行状态数组
     * @returns {void}
     */
    function navigateToNextSpan(rows: RowState[]): void {
      const currentIndex = getCurrentSpanIndex(rows);
      const nextIndex = currentIndex < rows.length - 1 ? currentIndex + 1 : rows.length - 1;
      const targetIndex = currentIndex === -1 ? 0 : nextIndex;
      const nextSpan = rows[targetIndex]?.span;
      if (nextSpan) {
        selectSpan(nextSpan);
        scrollToSpan(nextSpan.spanID, 'down');
      }
    }

    /**
     * @description 处理键盘事件，支持 Esc 关闭详情、↑/↓ 导航列表、Enter 打开详情
     * @param {KeyboardEvent} evt - 键盘事件对象
     * @returns {void}
     */
    function handleKeydown(evt: KeyboardEvent): void {
      // Esc 键始终可用于关闭详情抽屉
      if (evt.code === 'Escape') {
        showSpanDetails.value = false;
        return;
      }

      // 如果焦点在输入框内，不处理 ↑/↓/Enter 键
      if (isInputElementFocused()) return;

      const rows = getNavigableRows();
      if (!rows.length) return;

      switch (evt.key) {
        case 'ArrowUp':
          evt.preventDefault();
          navigateToPrevSpan(rows);
          break;
        case 'ArrowDown':
          evt.preventDefault();
          navigateToNextSpan(rows);
          break;
        case 'Enter':
          evt.preventDefault();
          // 复用 handleSpanClick 逻辑，避免重复代码
          if (spanDetails.value) {
            handleSpanClick(spanDetails.value);
          }
          break;
      }
    }

    /**
     * @description 获取滚动容器元素（带缓存）
     * @returns {HTMLElement | null}
     */
    function getContainer(): HTMLElement | null {
      if (!cachedContainer) {
        cachedContainer = getRootNode().querySelector('.trace-detail-wrapper');
      }
      return cachedContainer;
    }

    /**
     * @description 计算吸顶区域的总高度（带缓存）
     * @returns {number} 吸顶区域高度（Tab栏 + 工具栏）
     */
    function getStickyHeaderHeight(): number {
      if (cachedStickyHeight !== null) {
        return cachedStickyHeight;
      }
      const root = getRootNode();
      const tabElem = root.querySelector('.trace-main-tab') as HTMLElement;
      const toolsElem = root.querySelector('.view-tools') as HTMLElement;
      const tabHeight = tabElem?.offsetHeight || 0;
      const toolsHeight = toolsElem?.offsetHeight || 0;
      cachedStickyHeight = tabHeight + toolsHeight;
      return cachedStickyHeight;
    }

    /**
     * @description 滚动到指定 span 所在位置
     * @param {string} spanID - 目标 span 的 ID
     * @param {'down' | 'up'} direction - 滚动方向，up 向上导航需处理吸顶遮挡，down 向下导航无需额外处理
     * @returns {void}
     */
    function scrollToSpan(spanID: string, direction: 'down' | 'up'): void {
      const targetElem = getRootNode().getElementById(spanID);
      if (!targetElem) return;

      // 临时添加 tabIndex 使元素可聚焦
      targetElem.setAttribute('tabindex', '-1');
      targetElem.focus({ preventScroll: false });
      targetElem.removeAttribute('tabindex');

      const container = getContainer();
      if (!container) return;

      const elemRect = targetElem.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      const stickyHeaderHeight = getStickyHeaderHeight();
      const visibleTop = containerRect.top + stickyHeaderHeight;

      // 如果元素顶部被吸顶区域遮挡，额外滚动让元素完全可见
      if (elemRect.top < visibleTop) {
        const scrollOffset = visibleTop - elemRect.top;
        container.scrollBy({ top: -scrollOffset, behavior: 'instant' });
      }
    }

    /**
     * @description 键盘导航选中 span（不打开详情抽屉，不标记已读）
     * @param {Span} span - 要选中的 span 对象
     * @returns {void}
     */
    function selectSpan(span: Span): void {
      spanDetails.value = span;
    }

    /** 点击span事件 */
    const handleSpanClick = (span: Span, isEventTab = false) => {
      if (!haveReadSpanIds.value.includes(span.spanID)) {
        haveReadSpanIds.value.push(span.spanID);
      }
      showSpanDetails.value = true;
      spanDetails.value = span;
      activeTab.value = isEventTab ? 'Event' : 'BasicInfo';
    };

    /** 获取跨应用span */
    const getAcrossAppInfo = async (span: Span) => {
      const {
        app_name: appName,
        trace_id: traceId,
        bk_biz_id: bkBizId,
        permission,
        bk_app_code: appCode,
      } = span.cross_relation;
      if (!permission) {
        // 无权限查看跨应用
        handleApplyApp(appCode, bkBizId);
      } else {
        if (span.hasChildren) return; // 跨应用 span 已加载过

        store.setTraceLoaidng(true);
        const params = {
          app_name: appName,
          trace_id: traceId,
          bk_biz_id: bkBizId,
          [QUERY_TRACE_RELATION_APP]: store.traceViewFilters.includes(QUERY_TRACE_RELATION_APP),
        };
        const data = await traceDetail(params).catch(() => null);
        if (data) {
          store.setAcrossAppTraceInfo(data);
        }
        store.setTraceLoaidng(false);
      }
    };
    /** 申请应用权限 */
    const handleApplyApp = (id: number, bizId: number) => {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const action_ids = authorityMap.VIEW_AUTH;
      const resources = [{ id, type: 'apm_application' }];
      authorityStore.getIntanceAuthDetail(action_ids, resources, bizId);
    };
    /** 展开分组折叠的节点 */
    const handleToggleCollapse = (groupID, status) => {
      nextTick(() => store.updateSpanGroupCollapse(groupID, status));
    };
    /** 点击上一跳/下一跳 */
    const handlePrevNextClicked = flag => {
      // 获取当前spanId, spanIndex
      const curSpanId = spanDetails.value?.span_id;
      const curSpanIndex = spans.value.findIndex(span => span.span_id === curSpanId);

      if (curSpanIndex === -1) return; // 找不到当前 span，直接返回

      if (flag === 'next') {
        // 展开节点
        spanDetails.value.hasChildren &&
          Boolean(childrenHiddenStore?.childrenHiddenIds.value.has(curSpanId)) &&
          childrenHiddenStore?.onChange(curSpanId || '');
        spanDetails.value = spans.value[curSpanIndex + 1];
      } else {
        // 上一跳
        spanDetails.value = spans.value
          .slice(0, curSpanIndex)
          .reverse()
          .find(({ depth }) => depth === spanDetails.value.depth || depth === spanDetails.value.depth - 1);
      }
    };

    return {
      virtualizedTraceViewElm,
      listViewElm,
      getRowStates,
      handleSpanClick,
      getAcrossAppInfo,
      haveReadSpanIds,
      showSpanDetails,
      isFullscreen,
      spanDetails,
      traceTree,
      spans,
      handlePrevNextClicked,
      handleToggleCollapse,
      activeTab,
    };
  },

  render() {
    const { spanNameColumnWidth } = this.$props;

    return (
      <div
        ref='virtualizedTraceViewElm'
        class='virtualized-trace-view-spans'
      >
        <ListView
          ref='listViewElm'
          activeSpanId={this.spanDetails?.span_id || ''}
          dataLength={this.getRowStates.length}
          detailStates={this.detailStates}
          haveReadSpanIds={this.haveReadSpanIds}
          // key={this.spans.length}
          itemsWrapperClassName='virtualized-trace-view-rows-wrapper'
          spanNameColumnWidth={spanNameColumnWidth}
          viewBuffer={300}
          viewBufferMin={100}
          windowScroller
          onGetCrossAppInfo={this.getAcrossAppInfo}
          onItemClick={this.handleSpanClick}
          onToggleCollapse={this.handleToggleCollapse}
        />
        <SpanDetails
          activeTab={this.activeTab}
          isFullscreen={this.isFullscreen}
          isShowPrevNextButtons={true}
          show={this.showSpanDetails}
          spanDetails={this.spanDetails as Span}
          onPrevNextClicked={flag => {
            this.handlePrevNextClicked(flag);
          }}
          onShow={v => (this.showSpanDetails = v)}
        />
      </div>
    );
  },
});
