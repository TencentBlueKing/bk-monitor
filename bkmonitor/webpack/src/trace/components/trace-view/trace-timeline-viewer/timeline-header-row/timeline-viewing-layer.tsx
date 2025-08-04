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

import { type PropType, defineComponent, onBeforeUnmount, ref } from 'vue';

import { useSpanBarCurrentInject, useViewRangeInject } from '../../hooks';
import DraggableManager, { type DraggableBounds, type DraggingUpdate } from '../../utils/draggable-manager';

import type {
  IViewRange,
  IViewRangeTime,
  TNil,
  TUpdateViewRangeTimeFunction,
  ViewRangeTimeUpdate,
} from '../../typings';

import './timeline-viewing-layer.scss';

const TimelineViewingLayerProps = {
  boundsInvalidator: {
    type: Number as PropType<any | null | undefined>,
  },
  updateViewRangeTime: Function as PropType<TUpdateViewRangeTimeFunction>,
  updateNextViewRangeTime: Function as PropType<(update: ViewRangeTimeUpdate) => void>,
  viewRangeTime: {
    type: Object as PropType<IViewRangeTime>,
  },
};

type TDraggingLeftLayout = {
  isDraggingLeft: boolean;
  left: string;
  width: string;
};

type TOutOfViewLayout = {
  isOutOfView: true;
};

/**
 * Render the visual indication of the "next" view range.
 */
function getMarkers(viewStart: number, viewEnd: number, from: number, to: number, isShift: boolean) {
  const mappedFrom = mapToViewSubRange(viewStart, viewEnd, from);
  const mappedTo = mapToViewSubRange(viewStart, viewEnd, to);
  const layout = getNextViewLayout(mappedFrom, mappedTo);
  if (isOutOfView(layout)) {
    return null;
  }
  const { isDraggingLeft, left, width } = layout;
  return (
    <div
      style={{ left, width }}
      class={[
        'timeline-viewing-layer-dragged',
        {
          isDraggingLeft,
          isDraggingRight: !isDraggingLeft,
          isReframeDrag: !isShift,
          isShiftDrag: isShift,
        },
      ]}
    />
  );
}

/**
 * Get the layout for the "next" view range time, e.g. the difference from the
 * drag start and the drag end. This is driven by `shiftStart`, `shiftEnd` or
 * `reframe` on `props.viewRangeTime`, not by the current state of the
 * component. So, it reflects in-progress dragging from the span minimap.
 */
function getNextViewLayout(start: number, position: number): TDraggingLeftLayout | TOutOfViewLayout {
  let [left, right] = start < position ? [start, position] : [position, start];
  if (left >= 1 || right <= 0) {
    return { isOutOfView: true };
  }
  if (left < 0) {
    left = 0;
  }
  if (right > 1) {
    right = 1;
  }
  return {
    isDraggingLeft: start > position,
    left: `${left * 100}%`,
    width: `${(right - left) * 100}%`,
  };
}

function isOutOfView(layout: TDraggingLeftLayout | TOutOfViewLayout): layout is TOutOfViewLayout {
  return Reflect.has(layout, 'isOutOfView');
}

/**
 * Map from a sub range to the greater view range, e.g, when the view range is
 * the middle half ([0.25, 0.75]), a value of 0.25 befomes 3/8.
 * @returns {number}
 */
function mapFromViewSubRange(viewStart: number, viewEnd: number, value: number) {
  return viewStart + value * (viewEnd - viewStart);
}

/**
 * Map a value from the view ([0, 1]) to a sub-range, e.g, when the view range is
 * the middle half ([0.25, 0.75]), a value of 3/8 becomes 1/4.
 * @returns {number}
 */
function mapToViewSubRange(viewStart: number, viewEnd: number, value: number) {
  return (value - viewStart) / (viewEnd - viewStart);
}

export default defineComponent({
  name: 'TimelineViewingLayer',
  props: TimelineViewingLayerProps,
  setup() {
    const viewingLayerRef = ref<HTMLDivElement>();

    const viewRangeStore = useViewRangeInject();
    const spanBarCurrentStore = useSpanBarCurrentInject();

    const getDraggingBounds = (): DraggableBounds => {
      const current = viewingLayerRef?.value;
      if (!current) {
        throw new Error('Component must be mounted in order to determine DraggableBounds');
      }
      const { left: clientXLeft, width } = current.getBoundingClientRect();
      return { clientXLeft, width };
    };

    const handleReframeMouseMove = ({ value }: DraggingUpdate) => {
      const [viewStart, viewEnd] = spanBarCurrentStore?.current.value as [number, number];
      const cursor = mapFromViewSubRange(viewStart, viewEnd, value);
      const newTime = { ...viewRangeStore?.viewRange.value.time, ...{ cursor } };
      const params = { ...viewRangeStore?.viewRange.value, time: newTime };
      viewRangeStore?.onViewRangeChange(params as IViewRange);
    };

    const handleReframeMouseLeave = () => {
      // props.updateNextViewRangeTime({ cursor: undefined });
      const newTime = { ...viewRangeStore?.viewRange.value.time, ...{ cursor: undefined } };
      const params = { ...viewRangeStore?.viewRange.value, time: newTime };
      viewRangeStore?.onViewRangeChange(params as IViewRange);
    };

    const getAnchorAndShift = (value: number) => {
      // const { current, reframe } = props.viewRangeTime;
      const { reframe } = viewRangeStore?.viewRange.value.time as IViewRangeTime;
      // const [viewStart, viewEnd] = current;
      const [viewStart, viewEnd] = spanBarCurrentStore?.current.value as [number, number];
      const shift = mapFromViewSubRange(viewStart, viewEnd, value);
      const anchor = reframe ? reframe.anchor : shift;
      return { anchor, shift };
    };

    const handleReframeDragUpdate = ({ value }: DraggingUpdate) => {
      const { anchor, shift } = getAnchorAndShift(value);
      const update = { reframe: { anchor, shift } };
      // props.updateNextViewRangeTime(update);
      const newTime = { ...viewRangeStore?.viewRange.value.time, ...update };
      const params = { ...viewRangeStore?.viewRange.value, time: newTime };
      viewRangeStore?.onViewRangeChange(params as IViewRange);
    };

    const handleReframeDragEnd = ({ manager, value }: DraggingUpdate) => {
      const { anchor, shift } = getAnchorAndShift(value);
      const [start, end] = shift < anchor ? [shift, anchor] : [anchor, shift];
      manager.resetBounds();
      // props.updateViewRangeTime(start, end, 'timeline-header');
      viewRangeStore?.onViewRangeChange({ ...viewRangeStore?.viewRange.value, time: { current: [start, end] } });
      spanBarCurrentStore?.onCurrentChange([start, end]);
    };

    const draggerReframe = new DraggableManager({
      getBounds: getDraggingBounds,
      onDragEnd: handleReframeDragEnd,
      onDragMove: handleReframeDragUpdate,
      onDragStart: handleReframeDragUpdate,
      onMouseLeave: handleReframeMouseLeave,
      onMouseMove: handleReframeMouseMove,
    });

    onBeforeUnmount(() => {
      draggerReframe.dispose();
    });

    return {
      viewingLayerRef,
      draggerReframe,
      viewRangeStore,
      spanBarCurrentStore,
    };
  },

  render() {
    // const { viewRangeTime } = this.$props;

    const { cursor, reframe, shiftEnd, shiftStart } = this.viewRangeStore?.viewRange?.value.time as IViewRangeTime;
    // const [viewStart, viewEnd] = current;
    const [viewStart, viewEnd] = this.spanBarCurrentStore?.current.value as [number, number];

    const haveNextTimeRange = reframe != null || shiftEnd != null || shiftStart != null;
    let cusrorPosition: string | TNil;

    if (!haveNextTimeRange && cursor != null && cursor >= viewStart && cursor <= viewEnd) {
      cusrorPosition = `${mapToViewSubRange(viewStart, viewEnd, cursor) * 100}%`;
    }

    return (
      <div
        ref='viewingLayerRef'
        class='timeline-viewing-layer'
        onMousedown={this.draggerReframe.handleMouseDown}
        onMouseleave={this.draggerReframe.handleMouseLeave}
        onMousemove={this.draggerReframe.handleMouseMove}
      >
        {}
        {cusrorPosition != null && (
          <div
            style={{ left: cusrorPosition }}
            class='timeline-viewing-layer-cursorGuide'
          />
        )}
        {}
        {reframe != null && getMarkers(viewStart, viewEnd, reframe.anchor, reframe.shift, false)}
        {}
        {shiftEnd != null && getMarkers(viewStart, viewEnd, viewEnd, shiftEnd, true)}
        {}
        {shiftStart != null && getMarkers(viewStart, viewEnd, viewStart, shiftStart, true)}
      </div>
    );
  },
});
