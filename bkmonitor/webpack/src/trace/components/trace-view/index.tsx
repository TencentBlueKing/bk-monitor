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

import { type PropType, computed, defineComponent, nextTick, onMounted, ref } from 'vue';

import { useTraceStore } from '../../store/modules/trace';
import { useFocusMatchesProvide, useSpanBarCurrentProvide, useViewRangeProvide } from './hooks';
import SpanGraph from './span-graph';
import TraceTimelineViewer from './trace-timeline-viewer';
import filterSpans from './utils/filter-spans';

import type { ITraceTree } from '../../typings';
// import { trackRange } from './index.track';
import type { IViewRange, Span, TUpdateViewRangeTimeFunction, ViewRangeTimeUpdate } from './typings';

import './index.scss';

const TraceProps = {
  handleShowSpanDetail: Function as PropType<(span: Span) => void>,
  updateMatchedSpanIds: Function as PropType<(count: number) => void>,
};

export default defineComponent({
  name: 'TracePlugin',
  props: TraceProps,
  setup(props, { expose }) {
    const store = useTraceStore();
    const traceTimelineViewer = ref<HTMLDivElement>();
    const focusMatchesId = ref<string>('');
    const curFocusIndex = ref<number>(-1);
    const focusMatchesIdIndex = ref<number>(-1);
    const findMatchesIDs = ref(new Set());
    const viewRange = ref<IViewRange>({
      time: {
        current: [0, 1],
      },
    });
    const current = ref<[number, number]>([0, 1]);

    /** trace 瀑布图完整数据 */
    const traceTree = computed<ITraceTree>(() => store.traceTree);
    /** trace span 瀑布树 */
    const spanTree = computed<Span[]>(() => store.spanGroupTree);

    useViewRangeProvide({
      viewRange,
      onViewRangeChange: (val: IViewRange) => {
        viewRange.value = val;
      },
    });
    useSpanBarCurrentProvide({
      current,
      onCurrentChange: (val: [number, number]) => {
        current.value = val;
      },
    });
    useFocusMatchesProvide({
      focusMatchesId,
      focusMatchesIdIndex,
      findMatchesIDs,
    });

    const nextResult = () => {
      curFocusIndex.value = curFocusIndex.value + 1;
      focusMatchSpan();
    };
    const prevResult = () => {
      curFocusIndex.value = curFocusIndex.value - 1;
      focusMatchSpan();
    };
    const isInContainer = (el: HTMLDivElement, container: HTMLDivElement) => {
      if (!el || !container) return false;

      const elRect = el.getBoundingClientRect();
      let containerRect;

      if ([window, document, document.documentElement, null, undefined].includes(container)) {
        containerRect = {
          top: 0,
          right: window.innerWidth,
          bottom: window.innerHeight,
          left: 0,
        };
      } else {
        containerRect = container.getBoundingClientRect();
      }
      return (
        elRect.top < containerRect.bottom &&
        elRect.top > containerRect.top &&
        elRect.bottom > containerRect.top &&
        elRect.bottom < containerRect.bottom
      );
    };
    const focusMatchSpan = () => {
      const sortResultMatches: string[] = [];
      const { expandAll, virtualizedTraceView } = traceTimelineViewer.value as any;
      expandAll();
      nextTick(() => {
        const matchedSpanIds = Array.from(findMatchesIDs.value) || [];
        (virtualizedTraceView?.getRowStates || []).forEach((row: { span: Span }) => {
          const { span } = row;
          if (matchedSpanIds.includes(span.spanID)) {
            sortResultMatches.push(span.spanID);
          }
        });
        focusMatchesId.value = sortResultMatches[curFocusIndex.value];

        const targetElem = document.querySelector(`[id='${focusMatchesId.value}']`) as HTMLDivElement;
        const containerElem = document.querySelector('.trace-detail-wrapper') as HTMLDivElement;
        if (isInContainer(targetElem, containerElem)) {
          return;
        }

        focusMatchesIdIndex.value = (spanTree.value || []).findIndex(item => item.spanID === focusMatchesId.value);
      });
    };
    const updateNextViewRangeTime = (update: ViewRangeTimeUpdate) => {
      const time = { ...viewRange.value.time, ...update };
      viewRange.value = { ...viewRange.value, time };
    };
    const updateViewRangeTime: TUpdateViewRangeTimeFunction = (start: number, end: number) => {
      const current: [number, number] = [start, end];
      const time = { current };
      viewRange.value = { ...viewRange.value, time };
    };
    const trackFilter = (value: string[]) => {
      let matchedSpanIds = new Set();
      // eslint-disable-next-line @typescript-eslint/prefer-for-of
      for (let index = 0; index < value.length; index++) {
        const curMatched = filterSpans(value[index], spanTree.value);
        if (!curMatched?.size) {
          matchedSpanIds = new Set();
          break;
        } else if (!matchedSpanIds.size) {
          matchedSpanIds = curMatched;
        } else {
          matchedSpanIds = new Set([...new Set([...curMatched].filter(x => matchedSpanIds.has(x)))]);
        }
      }
      findMatchesIDs.value = matchedSpanIds;
      props.updateMatchedSpanIds?.(matchedSpanIds.size);

      if (findMatchesIDs.value.size) {
        curFocusIndex.value = 0;
        focusMatchSpan();
      } else {
        clearSearch();
      }
    };
    const handleClassifyFilter = (matchedSpanIds: Set<string>) => {
      findMatchesIDs.value = matchedSpanIds;
      props.updateMatchedSpanIds?.(matchedSpanIds.size);

      if (findMatchesIDs.value.size) {
        curFocusIndex.value = 0;
        focusMatchSpan();
      } else {
        clearSearch();
      }
    };
    const clearSearch = () => {
      curFocusIndex.value = -1;
      focusMatchesId.value = '';
      focusMatchesIdIndex.value = -1;
      findMatchesIDs.value = new Set();
    };

    onMounted(() => {
      updateViewRangeTime(0, 1);
    });

    expose({
      handleClassifyFilter,
      trackFilter,
      nextResult,
      prevResult,
      clearSearch,
      findMatchesIDs,
    });

    return {
      focusMatchesId,
      curFocusIndex,
      focusMatchesIdIndex,
      viewRange,
      traceTimelineViewer,
      updateViewRangeTime,
      updateNextViewRangeTime,
      trackFilter,
      nextResult,
      prevResult,
      clearSearch,
      traceTree,
    };
  },

  render() {
    return (
      <div
        key={this.traceTree.traceID}
        class='trace-view'
      >
        <div class='trace-page-header'>
          <SpanGraph
            updateNextViewRangeTime={this.updateNextViewRangeTime}
            updateViewRangeTime={this.updateViewRangeTime}
            viewRange={this.viewRange as IViewRange}
          />
        </div>
        <section class='trace-page-content'>
          <TraceTimelineViewer ref='traceTimelineViewer' />
        </section>
      </div>
    );
  },
});
