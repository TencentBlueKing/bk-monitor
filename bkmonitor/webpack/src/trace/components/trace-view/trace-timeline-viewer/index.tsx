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

import { type PropType, computed, defineComponent, inject, nextTick, onMounted, reactive, ref, toRefs } from 'vue';

import { useTraceStore } from '../../../store/modules/trace';
import { useChildrenHiddenProvide } from '../hooks';
import TimelineHeaderRow from './timeline-header-row';
import VirtualizedTraceView from './virtualized-trace-view';

import type { ITraceTree } from '../../../typings';
import type { Span, TUpdateViewRangeTimeFunction, ViewRangeTimeUpdate } from '../typings';

interface IState {
  height: number;
  resizeObserver: any;
}

const DEFAULT_MIN_VALUE = 240;
/** 「服务 & 操作」列自适应宽度的上限（占容器宽度比例） */
const AUTO_FIT_MAX_RATIO = 0.8;
/** 调用树每一层缩进的宽度（与 span-tree-offset 的 indent-guide 宽度保持一致） */
const INDENT_PER_DEPTH = 29;
/** span 名称单元格除文本外的固定占位（图标、内边距、收起标记等）的估算宽度 */
const SPAN_NAME_EXTRA_WIDTH = 112;

let measureCanvas: HTMLCanvasElement | null = null;
const measureTextWidth = (text: string, font: string) => {
  if (!measureCanvas) {
    measureCanvas = document.createElement('canvas');
  }
  const ctx = measureCanvas.getContext('2d');
  if (!ctx) return 0;
  ctx.font = font;
  return ctx.measureText(text || '').width;
};

const TProps = {
  updateViewRangeTime: Function as PropType<TUpdateViewRangeTimeFunction>,
  updateNextViewRangeTime: Function as PropType<(update: ViewRangeTimeUpdate) => void>,
};

const NUM_TICKS = 5;

export default defineComponent({
  name: 'TraceTimelineViewer',
  props: TProps,
  setup() {
    const store = useTraceStore();

    const spanNameColumnWidth = ref<number>(0.25);
    const minSpanNameColumnWidth = ref<number>(0.25);
    const wrapperRef = ref<HTMLDivElement>();
    const virtualizedTraceView = ref<HTMLDivElement>();
    const childrenHiddenIds = ref(new Set());

    const state = reactive<IState>({
      height: 0,
      resizeObserver: null,
    });

    const trace = computed<ITraceTree>(() => store.traceTree);
    const spans = computed<Span[]>(() => store.spanGroupTree);

    useChildrenHiddenProvide({
      childrenHiddenIds,
      onChange: (spanId: string) => childrenToggle(spanId),
    });

    const isFullscreen = inject('isFullscreen', false);

    onMounted(() => {
      resizeObsever();
      // getSpanNameColumnWidth();
      nextTick(() => getAutoFitColumnWidth());
    });
    const resizeObsever = () => {
      state.resizeObserver = new ResizeObserver(entries => {
        const rect = entries[0].contentRect;
        state.height = rect.height;
        getSpanNameColumnWidth();
      });
      state.resizeObserver.observe(wrapperRef.value);
    };
    const shouldDisableCollapse = (allSpans: Span[], hiddenSpansIds: any) => {
      const allParentSpans = allSpans.filter(s => s.hasChildren);
      return allParentSpans.length === hiddenSpansIds.size;
    };
    const collapseAll = () => {
      if (shouldDisableCollapse(spans.value, childrenHiddenIds.value)) {
        return;
      }
      const childrenHiddenIDs = spans.value.reduce((res, s) => {
        if (s.hasChildren) {
          res.add(s.spanID);
        }
        return res;
      }, new Set<string>());
      childrenHiddenIds.value = childrenHiddenIDs;
    };
    const collapseOne = () => {
      if (shouldDisableCollapse(spans.value, childrenHiddenIds.value)) {
        return;
      }
      let nearestCollapsedAncestor: Span | undefined;
      const childrenHiddenIDs = spans.value.reduce((res, curSpan) => {
        if (nearestCollapsedAncestor && curSpan.depth <= nearestCollapsedAncestor.depth) {
          res.add(nearestCollapsedAncestor.spanID);
          if (curSpan.hasChildren) {
            nearestCollapsedAncestor = curSpan;
          }
        } else if (curSpan.hasChildren && !res.has(curSpan.spanID)) {
          nearestCollapsedAncestor = curSpan;
        }
        return res;
      }, new Set(childrenHiddenIds.value));
      // The last one
      if (nearestCollapsedAncestor) {
        childrenHiddenIDs.add(nearestCollapsedAncestor.spanID);
      }
      childrenHiddenIds.value = childrenHiddenIDs;
    };
    const expandOne = () => {
      if (childrenHiddenIds.value.size === 0) {
        return;
      }
      let prevExpandedDepth = -1;
      let expandNextHiddenSpan = true;
      const childrenHiddenIDs = spans.value.reduce((res, s) => {
        if (s.depth <= prevExpandedDepth) {
          expandNextHiddenSpan = true;
        }
        if (expandNextHiddenSpan && res.has(s.spanID)) {
          res.delete(s.spanID);
          expandNextHiddenSpan = false;
          prevExpandedDepth = s.depth;
        }
        return res;
      }, new Set(childrenHiddenIds.value));
      childrenHiddenIds.value = childrenHiddenIDs;
    };
    const expandAll = () => {
      const childrenHiddenIDs = new Set<string>();
      childrenHiddenIds.value = childrenHiddenIDs;
    };
    const setSpanNameColumnWidth = (width: number) => {
      spanNameColumnWidth.value = width;
      nextTick(() => getSpanNameColumnWidth());
    };
    const childrenToggle = (spanID: string) => {
      const childrenHiddenIDs = new Set(childrenHiddenIds.value);
      if (childrenHiddenIDs.has(spanID)) {
        childrenHiddenIds.value.delete(spanID);
      } else {
        childrenHiddenIds.value.add(spanID);
      }
    };
    const getSpanNameColumnWidth = () => {
      const elemWidth = wrapperRef.value?.getBoundingClientRect()?.width || 0;
      const minRact = Number((DEFAULT_MIN_VALUE / elemWidth).toFixed(2));
      minSpanNameColumnWidth.value = minRact > 0.25 ? minRact : 0.25;
      if (minRact < spanNameColumnWidth.value) return;

      spanNameColumnWidth.value = Number(minRact);
    };
    /** 根据调用树内容（缩进 + 服务名 + 接口名）自适应「服务 & 操作」列宽，上限 40% */
    const getAutoFitColumnWidth = () => {
      const elemWidth = wrapperRef.value?.getBoundingClientRect()?.width || 0;
      if (!elemWidth || !spans.value.length) return;
      const fontFamily = getComputedStyle(wrapperRef.value as HTMLElement).fontFamily;
      const serviceFont = `14px ${fontFamily}`;
      const operationFont = `12px ${fontFamily}`;
      let maxContentWidth = 0;
      for (const s of spans.value) {
        const serviceName = s.service_name || s.process?.serviceName || '';
        const operationName = s.operationName || '';
        const indentWidth = (s.depth + 1) * INDENT_PER_DEPTH;
        const textWidth = measureTextWidth(serviceName, serviceFont) + measureTextWidth(operationName, operationFont);
        const contentWidth = indentWidth + textWidth + SPAN_NAME_EXTRA_WIDTH;
        if (contentWidth > maxContentWidth) {
          maxContentWidth = contentWidth;
        }
      }
      const fitRatio = maxContentWidth / elemWidth;
      const ratio = Math.min(Math.max(fitRatio, minSpanNameColumnWidth.value), AUTO_FIT_MAX_RATIO);
      spanNameColumnWidth.value = Number(ratio.toFixed(2));
    };
    return {
      ...toRefs(state),
      wrapperRef,
      virtualizedTraceView,
      spanNameColumnWidth,
      minSpanNameColumnWidth,
      isFullscreen,
      collapseAll,
      collapseOne,
      expandOne,
      expandAll,
      setSpanNameColumnWidth,
      trace,
      childrenHiddenIds,
    };
  },

  render() {
    return (
      <div
        ref='wrapperRef'
        style='position:relative;height:100%;'
        class='trace-timeline-viewer'
      >
        <TimelineHeaderRow
          columnResizeHandleHeight={this.height}
          duration={this.trace?.duration as number}
          minSpanNameColumnWidth={this.minSpanNameColumnWidth}
          nameColumnWidth={this.spanNameColumnWidth}
          numTicks={NUM_TICKS}
          onCollapseAll={this.collapseAll}
          onCollapseOne={this.collapseOne}
          onColummWidthChange={this.setSpanNameColumnWidth}
          onExpandAll={this.expandAll}
          onExpandOne={this.expandOne}
        />
        <VirtualizedTraceView
          ref='virtualizedTraceView'
          detailStates={new Map()}
          spanNameColumnWidth={this.spanNameColumnWidth}
        />
      </div>
    );
  },
});
