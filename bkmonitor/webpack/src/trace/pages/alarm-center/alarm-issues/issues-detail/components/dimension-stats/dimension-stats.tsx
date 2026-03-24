/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, defineComponent, reactive, shallowRef } from 'vue';

import BasicCard from '../basic-card/basic-card';

import type { DimensionSummaryItem, DimensionSummaryValue } from '../../../typing';

import './dimension-stats.scss';

const COLOR_LIST = ['#3370EB', '#56CCBC', '#FAC20A', '#FF7763', '#FB99ED', '#51CFFD'];
export default defineComponent({
  name: 'DimensionStats',
  props: {
    data: {
      type: Array as PropType<DimensionSummaryItem[]>,
      default: () => [],
    },
  },
  setup() {
    const popoverList = shallowRef<DimensionSummaryValue[]>([]);

    const tooltipOptions = reactive({
      show: false,
      x: 0,
      y: 0,
    });

    const handleMouseEnter = (e: MouseEvent, items: DimensionSummaryValue[]) => {
      popoverList.value = items;
      tooltipOptions.show = true;
      handleMouseMove(e);
    };

    const handleMouseMove = (e: MouseEvent) => {
      tooltipOptions.x = e.clientX + 15;
      tooltipOptions.y = e.clientY;
    };

    const handlePopoverHide = () => {
      tooltipOptions.show = false;
    };

    return {
      popoverList,
      tooltipOptions,
      handleMouseEnter,
      handleMouseMove,
      handlePopoverHide,
    };
  },
  render() {
    return (
      <BasicCard
        class='dimension-stats'
        title={this.$t('维度统计')}
      >
        {/* 内容 */}
        <div class='stats-body'>
          {this.data.map(row => (
            <div
              key={row.dimension_key}
              class='stats-row'
            >
              {/* 标签 */}
              <div class='row-label'>{row.dimension_name}</div>

              {/* 进度条 */}
              <div
                class='row-bar-wrapper'
                onMouseenter={(e: MouseEvent) => this.handleMouseEnter(e, row.items)}
                onMouseleave={this.handlePopoverHide}
                onMousemove={this.handleMouseMove}
              >
                <div class='row-bar'>
                  {row.items.map((item, index) => (
                    <div
                      key={item.value}
                      style={{
                        width: `${item.percentage}%`,
                        backgroundColor: COLOR_LIST[index],
                      }}
                      class='bar-segment'
                    >
                      <span class='segment-text'>{item.percentage}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Tooltip */}
        <div
          style={{
            display: this.tooltipOptions.show ? 'flex' : 'none',
            left: `${this.tooltipOptions.x}px`,
            top: `${this.tooltipOptions.y}px`,
          }}
          class='dimension-tooltip'
        >
          {this.popoverList.map((item, index) => (
            <div
              key={item.value}
              class='tooltip-item'
            >
              <span
                style={{ backgroundColor: COLOR_LIST[index] }}
                class='tooltip-dot'
              />
              <span class='tooltip-name'>{item.value}</span>
              <span class='tooltip-percent'>{item.percentage}%</span>
            </div>
          ))}
        </div>
      </BasicCard>
    );
  },
});
