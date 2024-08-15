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

import { type PropType, defineComponent, onBeforeUnmount, reactive, ref, toRefs } from 'vue';

import DraggableManager, { type DraggableBounds, type DraggingUpdate } from '../utils/draggable-manager';

import './vertical-resizer.scss';

const VerticalResizerProps = {
  max: {
    type: Number,
    default: 0,
  },
  min: {
    type: Number,
    default: 0,
  },
  onChange: Function as PropType<(newSize: number) => void>,
  position: {
    type: Number,
    default: 0,
  },
  rightSide: {
    required: false,
    type: Boolean,
  },
  columnResizeHandleHeight: {
    type: Number,
  },
};

export default defineComponent({
  name: 'VerticalResizer',
  props: VerticalResizerProps,
  setup(props) {
    const verticalResizerRef = ref<HTMLDivElement>();
    const state = reactive({
      dragPosition: null,
    });

    const getDraggingBounds = (): DraggableBounds => {
      if (!verticalResizerRef.value) {
        throw new Error('invalid state');
      }
      const { left: clientXLeft, width } = verticalResizerRef.value.getBoundingClientRect();
      const { rightSide } = props;
      let { min, max } = props;
      if (rightSide) [min, max] = [1 - max, 1 - min];
      return {
        clientXLeft,
        width,
        maxValue: max,
        minValue: min,
      };
    };

    const handleDragUpdate = ({ value }: DraggingUpdate) => {
      const dragPosition = props.rightSide ? 1 - value : value;
      state.dragPosition = dragPosition;
    };

    const handleDragEnd = ({ manager, value }: DraggingUpdate) => {
      manager.resetBounds();
      state.dragPosition = null;
      const dragPosition = props.rightSide ? 1 - value : value;
      props.onChange?.(dragPosition);
    };

    const dragManager = new DraggableManager({
      getBounds: getDraggingBounds,
      onDragEnd: handleDragEnd,
      onDragMove: handleDragUpdate,
      onDragStart: handleDragUpdate,
    });

    onBeforeUnmount(() => {
      dragManager.dispose();
    });

    return {
      ...toRefs(state),
      verticalResizerRef,
      dragManager,
    };
  },

  render() {
    let left;
    let draggerStyle;
    let isDraggingLeft = false;
    let isDraggingRight = false;
    const { position, rightSide, columnResizeHandleHeight } = this.$props;
    const { dragPosition } = this;
    left = `${position * 100}%`;
    const gripStyle = { left };

    if (this.dragManager.isDragging() && this.verticalResizerRef && dragPosition != null) {
      isDraggingLeft = dragPosition < position;
      isDraggingRight = dragPosition > position;
      left = `${dragPosition * 100}%`;
      // Draw a highlight from the current dragged position back to the original
      // position, e.g. highlight the change. Draw the highlight via `left` and
      // `right` css styles (simpler than using `width`).
      const draggerLeft = `${Math.min(position, dragPosition) * 100}%`;
      // subtract 1px for draggerRight to deal with the right border being off
      // by 1px when dragging left
      const draggerRight = `calc(${(1 - Math.max(position, dragPosition)) * 100}% - 1px)`;
      draggerStyle = { left: draggerLeft, right: draggerRight };
    } else {
      draggerStyle = gripStyle;
    }
    draggerStyle.height = `${columnResizeHandleHeight}px`;

    return (
      <div
        ref='verticalResizerRef'
        class={[
          'vertical-resizer',
          {
            isDraggingLeft,
            isDraggingRight,
            'is-flipped': rightSide,
          },
        ]}
      >
        <div
          style={gripStyle}
          class='vertical-resizer-gripIcon'
        />
        <div
          style={draggerStyle}
          class='vertical-resizer-dragger'
          aria-hidden
          onMousedown={this.dragManager.handleMouseDown}
        />
      </div>
    );
  },
});
