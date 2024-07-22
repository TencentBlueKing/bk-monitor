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
import { Component, Emit } from 'vue-property-decorator';

import { ILegendItem, LegendActionType } from '../../typings';
import CommonLegend from './common-legend';

import './pie-legend.scss';

@Component
export default class TableLegend extends CommonLegend {
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
      <div class='pie-legend'>
        {this.legendData.map((legend, index) => {
          if (legend.hidden) return undefined;
          return (
            <div
              key={index}
              class='pie-legend-item'
              onClick={e => this.handleLegendEvent(e, 'click', legend)}
              onMouseenter={e => this.handleLegendEvent(e, 'highlight', legend)}
              onMouseleave={e => this.handleLegendEvent(e, 'downplay', legend)}
            >
              <span
                style={{ backgroundColor: legend.show ? legend.color : '#ccc' }}
                class='legend-icon'
              ></span>
              <div
                style={{ color: legend.show ? '#63656e' : '#ccc' }}
                class='legend-name'
              >
                {legend.name}
              </div>
            </div>
          );
        })}
      </div>
    );
  }
}
