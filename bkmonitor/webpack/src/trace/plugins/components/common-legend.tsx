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
import { defineComponent } from 'vue';

import { ILegendItem, LegendActionType } from '../typings';

import type { PropType } from 'vue';

import './common-legend.scss';

export function useCommonLegend(emit: (event: 'selectLegend', ...args: any[]) => void) {
  function handleLegendEvent(e: MouseEvent, actionType: LegendActionType, item: ILegendItem) {
    let eventType = actionType;
    if (e.shiftKey && actionType === 'click') {
      eventType = 'shift-click';
    }
    emit('selectLegend', { actionType: eventType, item });
  }
  return { handleLegendEvent };
}
export const commonLegendProps = {
  // 图例数据
  legendData: {
    type: Array as PropType<ILegendItem[]>,
    required: true,
  },
};
export const commonLegendEmits = ['selectLegend'];

export default defineComponent({
  name: 'CommonLegend',
  props: commonLegendProps,
  emits: commonLegendEmits,
  setup(props, { emit }) {
    const { handleLegendEvent } = useCommonLegend(emit);
    return {
      handleLegendEvent,
    };
  },
  render() {
    return (
      <div class='common-legend'>
        {this.legendData?.map((legend, index) => {
          if (legend.hidden) return undefined;
          return (
            <div
              key={index}
              class='common-legend-item'
              onClick={e => this.handleLegendEvent(e, 'click', legend)}
              // onMouseenter={e => this.handleLegendEvent(e, 'highlight', legend)}
              // onMouseleave={e => this.handleLegendEvent(e, 'downplay', legend)}
            >
              <span
                style={{ backgroundColor: legend.show ? legend.color : '#ccc' }}
                class='legend-icon'
              ></span>
              <div
                style={{ color: legend.show ? '#63656e' : '#ccc' }}
                class='legend-name'
              >
                {legend.alias || legend.name}
              </div>
            </div>
          );
        })}
      </div>
    );
  },
});
