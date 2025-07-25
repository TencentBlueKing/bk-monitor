/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
  type CSSProperties,
  computed,
  defineComponent,
  getCurrentInstance,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from 'vue';

import { useRoute } from 'vue-router';

import { useTraceStore } from '../../../../store/modules/trace';
import { PEER_SERVICE } from '../../constants/tag-keys';
import { useChildrenHiddenInject, useFocusMatchesInject, useSpanBarCurrentInject } from '../../hooks';
import SpanBarRow from '../span-bar-row';
import {
  type ViewedBoundsFunctionType,
  createViewedBoundsFunc,
  findServerChildSpan,
  isErrorSpan,
  isKindClient,
  spanContainsErredSpan,
} from '../utils';
import { DEFAULT_HEIGHTS, generateRowStates } from '../virtualized-trace-view';
import Positions from './positions';

import type { Span, TNil } from '../../typings';

type RowState = {
  bgColorIndex?: number;
  isDetail: boolean;
  span: Span;
  spanIndex: number;
};

type TWrapperProps = {
  onScroll?: () => void;
  style: CSSProperties;
};

const NUM_TICKS = 5;

const DEFAULT_INITIAL_DRAW = 100;

/**
 * @typedef
 */
const TListViewProps = {
  /**
   * Number of elements in the list.
   */
  dataLength: {
    type: Number,
    default: 0,
  },
  /**
   * `className` for the HTMLElement that holds the items.
   */
  itemsWrapperClassName: {
    type: String,
    required: false,
  },
  /**
   * When adding new items to the DOM, this is the number of items to add above
   * and below the current view. E.g. if list is 100 items and is srcolled
   * halfway down (so items [46, 55] are in view), then when a new range of
   * items is rendered, it will render items `46 - viewBuffer` to
   * `55 + viewBuffer`.
   */
  viewBuffer: {
    type: Number,
    default: 0,
  },
  /**
   * The minimum number of items offscreen in either direction; e.g. at least
   * `viewBuffer` number of items must be off screen above and below the
   * current view, or more items will be rendered.
   */
  viewBufferMin: {
    type: Number,
    default: 0,
  },
  /**
   * When `true`, expect `_wrapperElm` to have `overflow: visible` and to,
   * essentially, be tall to the point the entire page will will end up
   * scrolling as a result of the ListView. Similar to react-virtualized
   * window scroller.
   *
   * - Ref: https://bvaughn.github.io/react-virtualized/#/components/WindowScroller
   * - Ref:https://github.com/bvaughn/react-virtualized/blob/497e2a1942529560681d65a9ef9f5e9c9c9a49ba/docs/WindowScroller.md
   */
  windowScroller: {
    type: Boolean,
    required: false,
  },
  detailStates: {
    type: Object,
  },
  spanNameColumnWidth: {
    type: Number,
  },
  haveReadSpanIds: {
    type: Array,
    default: [],
  },
  activeSpanId: {
    type: String,
  },
};

export default defineComponent({
  name: 'ListView',
  props: TListViewProps,
  emits: ['itemClick', 'getCrossAppInfo', 'toggleCollapse'],
  setup(props, { emit }) {
    const { traceTree: trace } = useTraceStore();
    const route = useRoute();
    const spanBarCurrentStore = useSpanBarCurrentInject();
    const focusMatchesStore = useFocusMatchesInject();
    const childrenHiddenStore = useChildrenHiddenInject();
    const span_id = ref('');

    const wrapperElm = ref<HTMLElement | TNil>(null);
    const itemHolderElm = ref<HTMLElement | TNil>(null);
    const knownHeights = ref(new Map());
    const startIndexDrawn = ref(2 ** 20);
    const endIndexDrawn = ref(-(2 ** 20));
    const startIndex = ref(0);
    const endIndex = ref(0);
    const viewHeight = ref(-1);
    const scrollTop = ref(-1);
    const isScrolledOrResized = ref(false);
    const htmlTopOffset = ref(-1);
    const windowScrollListenerAdded = ref(false);
    const htmlElm = ref(document.documentElement as any);

    const yPositions = new Positions(200);
    const internalInstance = getCurrentInstance() as any;
    const forceUpdate = internalInstance?.ctx.$forceUpdate;

    const spans = computed(() => useTraceStore().spanGroupTree);
    const getRowStates = computed<RowState[]>(() => {
      const { detailStates } = props;
      return trace ? generateRowStates(spans.value, childrenHiddenStore?.childrenHiddenIds.value, detailStates) : [];
    });

    onMounted(() => {
      if (props.windowScroller) {
        if (wrapperElm.value) {
          const { top } = wrapperElm.value.getBoundingClientRect();
          htmlTopOffset.value = top + htmlElm.value.scrollTop;
        }
        const elem = document.querySelector('.trace-detail-wrapper');
        elem?.addEventListener('scroll', onScroll);
        windowScrollListenerAdded.value = true;
      }

      if (itemHolderElm.value) {
        scanItemHeights();
      }
    });

    onUnmounted(() => {
      if (windowScrollListenerAdded.value) {
        window.removeEventListener('scroll', onScroll);
      }
    });

    watch(
      () => focusMatchesStore?.focusMatchesIdIndex.value,
      (val: any) => {
        if (val > -1) {
          const elem = document.querySelector('.trace-detail-wrapper');
          elem?.scrollTo({ top: val * 28, behavior: 'smooth' });
        }
      }
    );

    const getRowHeight = (index: number) => {
      const { span, isDetail } = getRowStates.value[index];
      if (!isDetail) {
        return DEFAULT_HEIGHTS.bar;
      }
      if (Array.isArray(span.logs) && span.logs.length) {
        return DEFAULT_HEIGHTS.detailWithLogs;
      }
      return DEFAULT_HEIGHTS.detail;
    };

    const getKeyFromIndex = (index: number) => {
      const { isDetail, span } = getRowStates.value[index];
      return `${span.spanID}--${isDetail ? 'detail' : 'bar'}`;
    };

    const getIndexFromKey = (key: string) => {
      const parts = key.split('--');
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const _spanID = parts[0];
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const _isDetail = parts[1] === 'detail';
      const max = getRowStates.value.length;
      for (let i = 0; i < max; i++) {
        const { span, isDetail } = getRowStates.value[i];
        if (span.spanID === _spanID && isDetail === _isDetail) {
          return i;
        }
      }
      return -1;
    };

    const getRowPosition = (index: number): { height: number; y: number } =>
      yPositions.getRowPosition(index, getHeight);

    /**
     * Recalculate _startIndex and _endIndex, e.g. which items are in view.
     */
    const calcViewIndexes = () => {
      const useRoot = props.windowScroller;
      // funky if statement is to satisfy flow
      if (!useRoot) {
        /* istanbul ignore next */
        if (!wrapperElm.value) {
          viewHeight.value = -1;
          startIndex.value = 0;
          endIndex.value = 0;
          return;
        }
        viewHeight.value = wrapperElm.value.clientHeight;
        scrollTop.value = wrapperElm.value.scrollTop;
      } else {
        // viewHeight.value = window.innerHeight - state.htmlTopOffset;
        // scrollTop.value = window.scrollY;
        const elem = document.querySelector('.trace-detail-wrapper');
        if (!elem) {
          return;
        }
        const rect = elem?.getBoundingClientRect();
        scrollTop.value = elem?.scrollTop as number;
        viewHeight.value = rect?.height as number;
      }
      const yStart = scrollTop.value;
      const yEnd = scrollTop.value + viewHeight.value;
      startIndex.value = yPositions.findFloorIndex(yStart, getHeight);
      endIndex.value = yPositions.findFloorIndex(yEnd, getHeight);
    };

    /**
     * Checked to see if the currently rendered items are sufficient, if not,
     * force an update to trigger more items to be rendered.
     */
    const positionList = () => {
      isScrolledOrResized.value = false;
      if (!wrapperElm.value) {
        return;
      }
      calcViewIndexes();
      // indexes drawn should be padded by at least props.viewBufferMin
      const maxStart = props.viewBufferMin > startIndex.value ? 0 : startIndex.value - props.viewBufferMin;
      const minEnd =
        props.viewBufferMin < props.dataLength - endIndex.value
          ? endIndex.value + props.viewBufferMin
          : props.dataLength - 1;
      if (maxStart < startIndexDrawn.value || minEnd > endIndexDrawn.value) {
        forceUpdate();
      }
    };

    const onScroll = () => {
      if (!isScrolledOrResized.value) {
        isScrolledOrResized.value = true;
        window.requestAnimationFrame(positionList);
      }
    };

    /**
     * Get the height of the element at index `i`; first check the known heigths,
     * fallbck to `.props.itemHeightGetter(...)`.
     */
    const getHeight = (i: number) => {
      // const key = props.getKeyFromIndex?.(i);
      const key = getKeyFromIndex?.(i);
      const known = knownHeights.value.get(key);
      // known !== known iff known is NaN

      if (known != null) {
        return known;
      }
      // return props.itemHeightGetter?.(i, key as string);
      return getRowHeight(i);
    };

    /**
     * Returns true is the view height (scroll window) or scroll position have
     * changed.
     */
    const isViewChanged = () => {
      if (!wrapperElm.value) {
        return false;
      }
      const useRoot = props.windowScroller;
      const clientHeight = useRoot ? htmlElm.value.clientHeight : wrapperElm.value.clientHeight;
      const scrollTop = useRoot ? htmlElm.value.scrollTop : wrapperElm.value.scrollTop;
      return clientHeight !== viewHeight.value || scrollTop !== scrollTop.value;
    };

    /**
     * Go through all items that are rendered and save their height based on their
     * item-key (which is on a data-* attribute). If any new or adjusted heights
     * are found, re-measure the current known y-positions (via .yPositions).
     */
    const scanItemHeights = () => {
      // const { getIndexFromKey } = props;
      if (!itemHolderElm.value) {
        return;
      }
      // note the keys for the first and last altered heights, the `yPositions`
      // needs to be updated
      let lowDirtyKey = null;
      let highDirtyKey = null;
      let isDirty = false;
      // iterating childNodes is faster than children
      // https://jsperf.com/large-htmlcollection-vs-large-nodelist
      const nodes = itemHolderElm.value.childNodes;
      const max = nodes.length;
      for (let i = 0; i < max; i++) {
        const node: HTMLElement = nodes[i] as any;
        // use `.getAttribute(...)` instead of `.dataset` for jest / JSDOM
        // const itemKey = node?.getAttribute('data-item-key');
        const itemKey = node.nextElementSibling?.getAttribute('data-item-key');
        if (!itemKey) {
          // console.warn('itemKey not found');
          continue;
        }
        // measure the first child, if it's available, otherwise the node itself
        // (likely not transferable to other contexts, and instead is specific to
        // how we have the items rendered)
        const measureSrc: Element = node.firstElementChild || node;
        const observed = measureSrc.clientHeight;
        const known = knownHeights.value.get(itemKey);
        if (observed !== known) {
          knownHeights.value.set(itemKey, observed);
          if (!isDirty) {
            isDirty = true;

            lowDirtyKey = highDirtyKey = itemKey;
          } else {
            highDirtyKey = itemKey;
          }
        }
      }

      if (lowDirtyKey != null && highDirtyKey != null) {
        // update yPositions, then redraw
        const imin = getIndexFromKey?.(lowDirtyKey);
        const imax = highDirtyKey === lowDirtyKey ? imin : getIndexFromKey?.(highDirtyKey);
        yPositions.calcHeights(imax as number, getHeight, imin);
        forceUpdate();
      }
    };

    const getClippingCssClasses = () => {
      const [zoomStart, zoomEnd] = spanBarCurrentStore?.current.value as [number, number];

      return {
        'clipping-left': zoomStart > 0,
        'clipping-right': zoomEnd < 1,
      };
    };

    const getViewedBounds = (): ViewedBoundsFunctionType => {
      const [zoomStart, zoomEnd] = spanBarCurrentStore?.current.value as [number, number];

      return createViewedBoundsFunc({
        min: trace?.startTime || 0,
        max: trace?.endTime || 0,
        viewStart: zoomStart,
        viewEnd: zoomEnd,
      });
    };

    const renderRow = (key: string, style: CSSProperties, index: number, attrs: object) => {
      const { span, spanIndex, bgColorIndex } = getRowStates.value[index];
      return renderSpanBarRow(span, spanIndex, key, style, attrs, bgColorIndex as number);
    };

    const renderSpanBarRow = (
      span: Span,
      spanIndex: number,
      key: string,
      style: CSSProperties,
      attrs: object,
      bgColorIndex: number
    ) => {
      const { spanID } = span;
      const { detailStates, spanNameColumnWidth, haveReadSpanIds } = props;
      // to avert flow error
      if (!trace) {
        return null;
      }
      const highlightSpanId = span_id.value;
      const isCollapsed = childrenHiddenStore?.childrenHiddenIds.value.has(spanID);
      const isDetailExpanded = detailStates?.has(spanID);
      const isMatchingFilter = focusMatchesStore?.findMatchesIDs.value?.has(spanID) ?? false;
      const isFocusMatching = spanID === focusMatchesStore?.focusMatchesId.value;
      const isActiveMatching = spanID === props.activeSpanId || spanID === highlightSpanId;
      const isHaveRead = haveReadSpanIds.includes(spanID);
      const showErrorIcon = isErrorSpan(span) || (isCollapsed && spanContainsErredSpan(spans.value, spanIndex));
      const attributes = { ...attrs, id: spanID };

      // Check for direct child "server" span if the span is a "client" span.
      let rpc = null;

      if (isCollapsed) {
        const rpcSpan = findServerChildSpan(spans.value.slice(spanIndex));
        if (rpcSpan) {
          const rpcViewBounds = getViewedBounds()(rpcSpan.startTime, rpcSpan.startTime + rpcSpan.duration);
          rpc = {
            color: rpcSpan.color,
            operationName: rpcSpan.operationName,
            serviceName: rpcSpan.process.serviceName,
            viewEnd: rpcViewBounds.end,
            viewStart: rpcViewBounds.start,
          };
        }
      }
      const peerServiceKV = span.tags.find(kv => kv.key === PEER_SERVICE);
      // Leaf, kind == client and has peer.service tag, is likely a client span that does a request
      // to an uninstrumented/external service
      let noInstrumentedServer = null;

      if (!span.hasChildren && peerServiceKV && isKindClient(span)) {
        noInstrumentedServer = {
          serviceName: peerServiceKV.value,
          color: span.color,
        };
      }

      return (
        <div
          key={key}
          style={style}
          class='virtualized-trace-view-row'
          onClick={() => handleClick(span)}
          {...attributes}
        >
          <SpanBarRow
            class={getClippingCssClasses()}
            bgColorIndex={bgColorIndex}
            color={span.color}
            columnDivision={spanNameColumnWidth}
            isActiveMatching={isActiveMatching}
            isChildrenExpanded={!isCollapsed}
            isDetailExpanded={isDetailExpanded}
            isFocusMatching={isFocusMatching}
            isHaveRead={isHaveRead}
            isMatchingFilter={isMatchingFilter}
            noInstrumentedServer={noInstrumentedServer}
            numTicks={NUM_TICKS}
            rpc={rpc}
            showErrorIcon={showErrorIcon}
            span={span}
            onLoadCrossAppInfo={getCrossAppInfo}
            onToggleCollapse={(groupID, status) => emit('toggleCollapse', groupID, status)}
          />
        </div>
      );
    };

    function getCrossAppInfo(span: Span) {
      emit('getCrossAppInfo', span);
    }

    function handleClick(itemKey: Span) {
      emit('itemClick', itemKey);
    }

    watch(
      () => route.query,
      () => {
        if (!route.query.incident_query) return;
        const spanInfo = JSON.parse(decodeURIComponent((route.query.incident_query as string) || '{}'));
        if (Object.keys(spanInfo).length > 0) {
          span_id.value = spanInfo.span_id;
          // 打开span详情抽屉
          if (spanInfo.type === 'spanDetail') {
            const data = getRowStates.value.find(f => f.span.id === spanInfo.span_id);
            if (data) {
              setTimeout(() => {
                document.getElementById(spanInfo.span_id)?.scrollIntoView({ behavior: 'smooth' });
              }, 50);
              emit('itemClick', data.span, true);
            }
          }
        }
      },
      { immediate: true }
    );

    return {
      yPositions,
      wrapperElm,
      itemHolderElm,
      onScroll,
      isViewChanged,
      calcViewIndexes,
      getHeight,
      getRowPosition,
      renderRow,
      startIndexDrawn,
      endIndexDrawn,
      startIndex,
      endIndex,
      getKeyFromIndex,
    };
  },

  render() {
    const { dataLength, viewBuffer, viewBufferMin } = this.$props;
    const heightGetter = this.getHeight;
    const items = [];
    let start: number;
    let end: number;

    this.yPositions.profileData(dataLength);

    if (!this.wrapperElm) {
      start = 0;
      end = (DEFAULT_INITIAL_DRAW < dataLength ? DEFAULT_INITIAL_DRAW : dataLength) - 1;
    } else {
      if (this.isViewChanged()) {
        this.calcViewIndexes();
      }
      const maxStart = viewBufferMin > this.startIndex ? 0 : this.startIndex - viewBufferMin;
      const minEnd = viewBufferMin < dataLength - this.endIndex ? this.endIndex + viewBufferMin : dataLength - 1;
      if (maxStart < this.startIndexDrawn || minEnd > this.endIndexDrawn) {
        start = viewBuffer > this.startIndex ? 0 : this.startIndex - viewBuffer;
        end = this.endIndex + viewBuffer;
        if (end >= dataLength) {
          end = dataLength - 1;
        }
      } else {
        start = this.startIndexDrawn;
        end = this.endIndexDrawn > dataLength - 1 ? dataLength - 1 : this.endIndexDrawn;
      }
    }

    this.yPositions.calcHeights(end, heightGetter, start || -1);
    this.startIndexDrawn = start;
    this.endIndexDrawn = end;

    items.length = end - start + 1;
    for (let i = start; i <= end; i++) {
      const { y: top, height } = this.yPositions.getRowPosition(i, heightGetter);
      const style = {
        height: `${height}px`,
        top: `${top}px`,
        position: 'absolute',
      };
      const itemKey = this.getKeyFromIndex?.(i);
      const attrs = { 'data-item-key': itemKey };
      items.push(this.renderRow?.(itemKey as string, style as CSSProperties, i, attrs as Record<string, string>));
    }

    const wrapperProps: TWrapperProps = {
      style: { position: 'relative' },
    };
    if (!this.$props.windowScroller) {
      wrapperProps.onScroll = this.onScroll;
      wrapperProps.style.height = '100%';
      wrapperProps.style.overflowY = 'auto';
    }
    const scrollerStyle = {
      position: 'relative' as const,
      height: `${this.yPositions.getEstimatedHeight()}px`,
    };

    return (
      <div
        ref='wrapperElm'
        {...wrapperProps}
      >
        <div style={scrollerStyle}>
          <div
            ref='itemHolderElm'
            style={{
              position: 'absolute',
              top: 0,
              margin: 0,
              padding: 0,
            }}
            class={this.itemsWrapperClassName}
          >
            {items}
          </div>
        </div>
      </div>
    );
  },
});
