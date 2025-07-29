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

import { type PropType, computed, defineComponent } from 'vue';

import { useTraceStore } from '../../../store/modules/trace';
import CanvasSpanGraph from './canvas-span-graph';
import TickLabels from './tick-labels';
import ViewingLayer from './viewing-layer';

import type { ITraceTree } from '../../../typings';
import type { IViewRange, Span, TUpdateViewRangeTimeFunction, ViewRangeTimeUpdate } from '../typings';

interface ComplexMessage {
  color: string;
  isVirtual: boolean;
  serviceName: string;
  valueOffset: number;
  valueWidth: number;
}

const DEFAULT_HEIGHT = 56;
const TIMELINE_TICK_INTERVAL = 4;

const SpanGraphProps = {
  height: {
    type: Number,
  },
  viewRange: {
    type: Object as PropType<IViewRange>,
  },
  updateViewRangeTime: Function as PropType<TUpdateViewRangeTimeFunction>,
  updateNextViewRangeTime: Function as PropType<(update: ViewRangeTimeUpdate) => void>,
};

export default defineComponent({
  name: 'SpanGraph',
  props: SpanGraphProps,
  setup() {
    const store = useTraceStore();

    const trace = computed<ITraceTree>(() => store.traceTree);
    const spans = computed<Span[]>(() => store.spanGroupTree);
    const items = computed(() =>
      (spans.value || []).map(item => ({
        valueOffset: item.relativeStartTime,

        valueWidth:
          item.group_info && item.group_info.id === item.span_id && !item.is_expand
            ? item.group_info.duration
            : item.duration,
        serviceName: item.process.serviceName,
        color: item.color,
        isVirtual: item.is_virtual,
      }))
    );
    return {
      items,
      trace,
    };
  },

  render() {
    const { height, viewRange, updateViewRangeTime, updateNextViewRangeTime } = this.$props;

    if (!this.trace) {
      return <div />;
    }

    return (
      <div class='span-graph'>
        <TickLabels
          duration={this.trace.duration || 0}
          numTicks={TIMELINE_TICK_INTERVAL}
        />
        <div style='position:relative;'>
          <CanvasSpanGraph
            items={this.items as ComplexMessage[]}
            valueWidth={this.trace.duration}
          />
          <ViewingLayer
            height={height || DEFAULT_HEIGHT}
            numTicks={TIMELINE_TICK_INTERVAL}
            updateNextViewRangeTime={updateNextViewRangeTime}
            updateViewRangeTime={updateViewRangeTime}
            viewRange={viewRange}
          />
        </div>
      </div>
    );
  },
});
