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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { ILegendItem, LegendActionType } from '../../typings';

import './common-legend.scss';

interface ILegendProps {
  // 图例数据
  legendData: ILegendItem[];
}
interface ILegendEvent {
  // 点击图例事件
  onSelectLegend: (p: { actionType: string; item: ILegendItem }) => void;
}

@Component
export default class CommonLegend extends tsc<ILegendProps, ILegendEvent> {
  // 图例数据
  @Prop({ required: true }) readonly legendData: ILegendItem[];

  @Emit('selectLegend')
  handleLegendEvent(e: MouseEvent, actionType: LegendActionType, item: ILegendItem) {
    let eventType = actionType;
    if (e.shiftKey && actionType === 'click') {
      eventType = 'shift-click';
    }
    return { actionType: eventType, item };
  }

  render() {
    return (
      <div class='common-legend'>
        {this.legendData.map((legend, index) => {
          if (legend.hidden) return undefined;
          return (
            <div
              class='common-legend-item'
              key={index}
              onClick={e => this.handleLegendEvent(e, 'click', legend)}
              onMouseenter={e => this.handleLegendEvent(e, 'highlight', legend)}
              onMouseleave={e => this.handleLegendEvent(e, 'downplay', legend)}
            >
              <span
                class='legend-icon'
                style={{ backgroundColor: legend.show ? legend.color : '#ccc' }}
              ></span>
              <div
                class='legend-name'
                style={{ color: legend.show ? '#63656e' : '#ccc' }}
              >
                {legend.alias || legend.name}
              </div>
            </div>
          );
        })}
        {this.$slots.expand && (
          <div
            class='common-legend-item'
            style='position: relative'
          >
            {this.$slots.expand}
          </div>
        )}
      </div>
    );
  }
}
