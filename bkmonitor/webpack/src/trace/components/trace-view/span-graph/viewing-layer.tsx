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

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useSpanBarCurrentInject, useViewRangeInject } from '../hooks';
import DraggableManager, { type DraggableBounds, type DraggingUpdate, EUpdateTypes } from '../utils/draggable-manager';
import GraphTicks from './graph-ticks';
import Scrubber from './scrubber';

import type {
  ISpanBarStore,
  IViewRange,
  IViewRangeTime,
  TNil,
  TUpdateViewRangeTimeFunction,
  ViewRangeTimeUpdate,
} from '../typings';

import './viewing-layer.scss';

const ViewingLayerProps = {
  height: {
    type: Number,
  },
  numTicks: {
    type: Number,
  },
  updateViewRangeTime: Function as PropType<TUpdateViewRangeTimeFunction>,
  updateNextViewRangeTime: Function as PropType<(update: ViewRangeTimeUpdate) => void>,
  viewRange: {
    type: Object as PropType<IViewRange>,
  },
};

/**
 * Designate the tags for the different dragging managers. Exported for tests.
 */
export const dragTypes = {
  /**
   * Tag for dragging the right scrubber, e.g. end of the current view range.
   */
  SHIFT_END: 'SHIFT_END',
  /**
   * Tag for dragging the left scrubber, e.g. start of the current view range.
   */
  SHIFT_START: 'SHIFT_START',
  /**
   * Tag for dragging a new view range.
   */
  REFRAME: 'REFRAME',
};

/**
 * Returns the layout information for drawing the view-range differential, e.g.
 * show what will change when the mouse is released. Basically, this is the
 * difference from the start of the drag to the current position.
 *
 * @returns {{ x: string, width: string, leadginX: string }}
 */
const getNextViewLayout = (start: number, position: number) => {
  const [left, right] = start < position ? [start, position] : [position, start];
  return {
    x: `${left * 100}%`,
    width: `${(right - left) * 100}%`,
    leadingX: `${position * 100}%`,
  };
};

export default defineComponent({
  name: 'ViewingLayer',
  props: ViewingLayerProps,
  setup(props, { emit }) {
    const { t } = useI18n();
    const preventCursorLine = ref(false);
    const layerGraphRef = ref<HTMLDivElement>();

    const viewRangeStore = useViewRangeInject();
    const spanBarCurrentStore = useSpanBarCurrentInject();

    const getDraggingBounds = (tag: string | TNil): DraggableBounds => {
      if (!layerGraphRef.value) {
        throw new Error('invalid state');
      }
      const { left: clientXLeft, width } = layerGraphRef.value?.getBoundingClientRect();
      const [viewStart, viewEnd] = spanBarCurrentStore?.current.value as [number, number];
      let maxValue = 1;
      let minValue = 0;
      if (tag === dragTypes.SHIFT_START) {
        maxValue = viewEnd;
      } else if (tag === dragTypes.SHIFT_END) {
        minValue = viewStart;
      }
      return { clientXLeft, maxValue, minValue, width };
    };

    const handleReframeDragEnd = ({ manager, value }: DraggingUpdate) => {
      const { time } = viewRangeStore?.viewRange.value as IViewRange;
      const anchor = time.reframe ? time.reframe.anchor : value;
      const [start, end] = value < anchor ? [value, anchor] : [anchor, value];
      manager.resetBounds();

      viewRangeStore?.onViewRangeChange({ ...viewRangeStore?.viewRange.value, time: { current: [start, end] } });
      spanBarCurrentStore?.onCurrentChange([start, end]);
    };

    const handleReframeDragUpdate = ({ value }: DraggingUpdate) => {
      const shift = value;
      const { time } = viewRangeStore?.viewRange.value as IViewRange;
      const anchor = time.reframe ? time.reframe.anchor : shift;
      const update = { reframe: { anchor, shift } };

      const newTime = { ...viewRangeStore?.viewRange.value.time, ...update };
      const params = { ...viewRangeStore?.viewRange.value, time: newTime };
      viewRangeStore?.onViewRangeChange(params as IViewRange);
    };

    const handleReframeMouseMove = ({ value }: DraggingUpdate) => {
      const newTime = { ...viewRangeStore?.viewRange.value.time, ...{ cursor: value } };
      const params = { ...viewRangeStore?.viewRange.value, time: newTime };
      viewRangeStore?.onViewRangeChange(params as IViewRange);
    };

    const handleReframeMouseLeave = () => {
      const newTime = { ...viewRangeStore?.viewRange.value.time, ...{ cursor: null } };
      const params = { ...viewRangeStore?.viewRange.value, time: newTime };
      viewRangeStore?.onViewRangeChange(params as IViewRange);
    };

    const handleScrubberDragEnd = ({ manager, tag, value }: DraggingUpdate) => {
      const [viewStart, viewEnd] = spanBarCurrentStore?.current.value as [number, number];
      let update: [number, number];
      if (tag === dragTypes.SHIFT_START) {
        update = [value, viewEnd];
      } else if (tag === dragTypes.SHIFT_END) {
        update = [viewStart, value];
      } else {
        // to satisfy flow
        throw new Error('bad state');
      }
      manager.resetBounds();
      preventCursorLine.value = false;

      viewRangeStore?.onViewRangeChange({
        ...viewRangeStore?.viewRange.value,
        time: { current: [update[0], update[1]] },
      });
      spanBarCurrentStore?.onCurrentChange([update[0], update[1]]);
    };

    const handleScrubberDragUpdate = ({ event, tag, type, value }: DraggingUpdate) => {
      if (type === EUpdateTypes.DragStart) {
        event.stopPropagation();
      }
      if (tag === dragTypes.SHIFT_START) {
        const newTime = { ...viewRangeStore?.viewRange.value.time, ...{ shiftStart: value } };
        const params = { ...viewRangeStore?.viewRange.value, time: newTime };
        viewRangeStore?.onViewRangeChange(params as IViewRange);
      } else if (tag === dragTypes.SHIFT_END) {
        const newTime = { ...viewRangeStore?.viewRange.value.time, ...{ shiftEnd: value } };
        const params = { ...viewRangeStore?.viewRange.value, time: newTime };
        viewRangeStore?.onViewRangeChange(params as IViewRange);
      }
    };

    const handleScrubberEnterLeave = ({ type }: DraggingUpdate) => {
      preventCursorLine.value = type === EUpdateTypes.MouseEnter;
    };

    const draggerReframe = new DraggableManager({
      getBounds: getDraggingBounds,
      onDragEnd: handleReframeDragEnd,
      onDragMove: handleReframeDragUpdate,
      onDragStart: handleReframeDragUpdate,
      onMouseMove: handleReframeMouseMove,
      onMouseLeave: handleReframeMouseLeave,
      tag: dragTypes.REFRAME,
    });

    const draggerStart = new DraggableManager({
      getBounds: getDraggingBounds,
      onDragEnd: handleScrubberDragEnd,
      onDragMove: handleScrubberDragUpdate,
      onDragStart: handleScrubberDragUpdate,
      onMouseEnter: handleScrubberEnterLeave,
      onMouseLeave: handleScrubberEnterLeave,
      tag: dragTypes.SHIFT_START,
    });

    const draggerEnd = new DraggableManager({
      getBounds: getDraggingBounds,
      onDragEnd: handleScrubberDragEnd,
      onDragMove: handleScrubberDragUpdate,
      onDragStart: handleScrubberDragUpdate,
      onMouseEnter: handleScrubberEnterLeave,
      onMouseLeave: handleScrubberEnterLeave,
      tag: dragTypes.SHIFT_END,
    });

    /**
     * Resets the zoom to fully zoomed out.
     */
    const resetTimeZoomClickHandler = () => {
      // props.updateViewRangeTime(0, 1);

      viewRangeStore?.onViewRangeChange({ ...viewRangeStore?.viewRange.value, time: { current: [0, 1] } });
      spanBarCurrentStore?.onCurrentChange([0, 1]);
    };

    /**
     * Renders the difference between where the drag started and the current
     * position, e.g. the red or blue highlight.
     *
     * @returns React.Node[]
     */
    const getMarkers = (from: number, to: number, isShift: boolean) => {
      const layout = getNextViewLayout(from, to);
      return [
        <rect
          key='fill'
          width={layout.width}
          height={(props.height as number) - 2}
          class={[
            'draggedShift',
            {
              isShiftDrag: isShift,
              isReframeDrag: !isShift,
            },
          ]}
          x={layout.x}
          y='0'
        />,
        <rect
          key='edge'
          width='1'
          height={(props.height as number) - 2}
          class={[
            'draggedEdge',
            {
              isShiftDrag: isShift,
              isReframeDrag: !isShift,
            },
          ]}
          x={layout.leadingX}
          y='0'
        />,
      ];
    };

    onBeforeUnmount(() => {
      draggerReframe.dispose();
      draggerEnd.dispose();
      draggerStart.dispose();
    });

    return {
      preventCursorLine,
      layerGraphRef,
      draggerReframe,
      draggerStart,
      draggerEnd,
      resetTimeZoomClickHandler,
      getMarkers,
      viewRangeStore,
      spanBarCurrentStore,
      t,
    };
  },
  render() {
    const { height, numTicks } = this.$props;
    const { cursor, shiftStart, shiftEnd, reframe } = this.viewRangeStore?.viewRange?.value.time as IViewRangeTime;
    const { current } = this.spanBarCurrentStore as ISpanBarStore;

    const haveNextTimeRange = shiftStart != null || shiftEnd != null || reframe != null;
    const [viewStart, viewEnd] = current.value;
    let leftInactive = 0;
    if (viewStart) {
      leftInactive = viewStart * 100;
    }
    let rightInactive = 100;
    if (viewEnd) {
      rightInactive = 100 - viewEnd * 100;
    }
    let cursorPosition: string | undefined;

    if (!haveNextTimeRange && cursor != null && !this.preventCursorLine) {
      cursorPosition = `${cursor * 100}%`;
    }

    return (
      <div
        style={{ height: `${height}px` }}
        class='viewing-layer'
      >
        {(viewStart !== 0 || viewEnd !== 1) && (
          <Button
            class='reset-zoom'
            size='small'
            onClick={this.resetTimeZoomClickHandler}
          >
            {this.t('重置')}
          </Button>
        )}
        <svg
          ref='layerGraphRef'
          height={height}
          class='wiewing-layer-graph'
          onMousedown={this.draggerReframe.handleMouseDown}
          onMouseleave={this.draggerReframe.handleMouseLeave}
          onMousemove={this.draggerReframe.handleMouseMove}
        >
          {leftInactive > 0 && (
            <rect
              width={`${leftInactive}%`}
              height='100%'
              class='viewing-layer-inactive'
              x={0}
              y={0}
            />
          )}
          {rightInactive > 0 && (
            <rect
              width={`${rightInactive}%`}
              height='100%'
              class='viewing-layer-inactive'
              x={`${100 - rightInactive}%`}
              y={0}
            />
          )}
          <GraphTicks numTicks={numTicks as number} />
          {}
          {shiftStart != null && this.getMarkers(viewStart, shiftStart, true)}
          {}
          {shiftEnd != null && this.getMarkers(viewEnd, shiftEnd, true)}
          {cursorPosition && (
            <line
              class='viewinglayer-cursorGuide'
              stroke-width='1'
              x1={cursorPosition}
              x2={cursorPosition}
              y1='0'
              y2={(height as number) - 2}
            />
          )}
          <Scrubber
            isDragging={shiftStart !== null}
            position={viewStart || 0}
            onMouseDown={this.draggerStart.handleMouseDown}
            onMouseEnter={this.draggerStart.handleMouseEnter}
            onMouseLeave={this.draggerStart.handleMouseLeave}
          />
          <Scrubber
            isDragging={shiftEnd !== null}
            position={viewEnd || 1}
            onMouseDown={this.draggerEnd.handleMouseDown}
            onMouseEnter={this.draggerEnd.handleMouseEnter}
            onMouseLeave={this.draggerEnd.handleMouseLeave}
          />
          {}
          {reframe != null && this.getMarkers(reframe.anchor, reframe.shift, false)}
        </svg>
        {/* fullOverlay updates the mouse cursor blocks mouse events */}
        {haveNextTimeRange && <div class='viewingLayer-fullOverlay' />}
      </div>
    );
  },
});
