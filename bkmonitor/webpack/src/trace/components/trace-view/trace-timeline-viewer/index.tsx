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
      setDefaultExpandSpan();
      getSpanNameColumnWidth();
    });

    /** 默认展开三层 其他的先收起 */
    const setDefaultExpandSpan = () => {
      const childrenHiddenIDs = spans.value.reduce((res, s) => {
        if (s.depth > 1) {
          res.add(s.spanID);
        }
        return res;
      }, new Set<string>());
      childrenHiddenIds.value = childrenHiddenIDs;
    };
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
