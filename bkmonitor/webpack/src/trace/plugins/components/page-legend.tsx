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
import { type PropType, defineComponent, nextTick, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue';

import type { ILegendItem, LegendActionType } from '../typings';

import './page-legend.scss';

export default defineComponent({
  name: 'PageLegend',
  props: {
    wrapHeight: {
      type: Number,
      default: 40,
    },
    // 图例数据
    legendData: {
      type: Array as PropType<ILegendItem[]>,
      required: true,
    },
  },
  emits: ['selectLegend'],
  setup(props, { emit }) {
    /** 当前页 */
    const currentPageNum = shallowRef(1);
    /** 所有页 */
    const legendMaxPageNum = shallowRef(1);
    /** 是否展示分页ICON */
    const isShowPageIcon = shallowRef(false);
    const commonLegend = useTemplateRef<HTMLDivElement>('commonLegend');

    watch(
      () => props.legendData,
      () => {
        nextTick(() => {
          isShowPageIcon.value = commonLegend.value.scrollHeight > commonLegend.value.clientHeight;
          if (isShowPageIcon.value) {
            commonLegend.value.addEventListener('wheel', legendWheel);
            legendMaxPageNum.value = Math.ceil(commonLegend.value.scrollHeight / props.wrapHeight);
          } else {
            commonLegend.value.removeEventListener('wheel', legendWheel);
          }
        });
      },
      { immediate: true }
    );

    const legendWheel = (event: WheelEvent) => {
      event.preventDefault();
      // 根据 event.deltaY 判断滚动方向
      if (event.deltaY < 0) {
        // 向上滚动
        if (currentPageNum.value > 1) currentPageNum.value -= 1;
      } else {
        // 向下滚动
        if (currentPageNum.value < legendMaxPageNum.value) currentPageNum.value += 1;
      }
    };

    const handleLegendEvent = (e: MouseEvent, actionType: LegendActionType, item: ILegendItem) => {
      let eventType = actionType;
      if (e.shiftKey && actionType === 'click') {
        eventType = 'shift-click';
      }
      emit('selectLegend', { actionType: eventType, item });
    };

    watch(
      () => currentPageNum.value,
      v => {
        commonLegend.value.scrollTo({
          top: (v - 1) * props.wrapHeight,
        });
      }
    );

    onUnmounted(() => {
      commonLegend.value?.removeEventListener('wheel', legendWheel);
    });

    return {
      currentPageNum,
      legendMaxPageNum,
      isShowPageIcon,
      commonLegend,
      handleLegendEvent,
    };
  },

  render() {
    return (
      <div
        style={{ height: `${this.wrapHeight}px` }}
        class='page-legend-box-component'
      >
        <div
          ref='commonLegend'
          class='common-legend'
        >
          {this.legendData.map((legend, index) => {
            return (
              <div
                key={index}
                class='common-legend-item'
                onClick={e => this.handleLegendEvent(e, 'click', legend)}
              >
                <span
                  style={{ backgroundColor: legend.show ? legend.color : '#ccc' }}
                  class='legend-icon'
                />
                <div
                  style={{ color: legend.show ? '#63656e' : '#ccc' }}
                  class='legend-name'
                  v-overflow-tips
                >
                  {legend.name}
                </div>
              </div>
            );
          })}
        </div>
        {this.isShowPageIcon && (
          <div class='legend-icon-box'>
            <i
              class={{
                'icon-monitor icon-mc-arrow-down last-page-up': true,
                disabled: this.currentPageNum === 1,
              }}
              onClick={() => {
                if (this.currentPageNum > 1) this.currentPageNum -= 1;
              }}
            />
            <i
              class={{
                'icon-monitor icon-mc-arrow-down': true,
                disabled: this.currentPageNum === this.legendMaxPageNum,
              }}
              onClick={() => {
                if (this.currentPageNum < this.legendMaxPageNum) this.currentPageNum += 1;
              }}
            />
          </div>
        )}
      </div>
    );
  },
});
