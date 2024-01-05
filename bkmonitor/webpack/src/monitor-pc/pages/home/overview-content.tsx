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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './overview-content.scss';

export interface IData {
  id: string;
  name: string;
  icon: string;
  num: number;
  unit: string;
  type: 'num' | '%' | 'time';
  borderRight?: boolean;
  tip?: string;
  allowHtml?: boolean;
}

interface IOverviewContentProps {
  data: IData[];
}

@Component({
  name: 'OverviewContent'
})
export default class OverviewContent extends tsc<IOverviewContentProps> {
  @Prop({ type: Array, default: () => [] }) data: IData[];
  @Ref('mttaTipRef') mttaTipRef: HTMLDivElement;
  @Ref('mttrTipRef') mttrTipRef: HTMLDivElement;

  getSvgIcon(icon) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require(`../../../fta-solutions/static/img/home/${icon}.svg`);
  }

  render() {
    return (
      <div class='home-data-overview-content'>
        {this.data.map(item => (
          <div
            class={['data-item', { 'border-right': item?.borderRight }]}
            v-bk-tooltips={{
              content: item.allowHtml ? this?.[item.tip] || '' : item.tip,
              delay: [500, 0],
              theme: 'light',
              placements: ['top'],
              boundary: 'window',
              maxWidth: 250
            }}
          >
            <span class='item-top'>
              <span class='num'>{item.num}</span>
              <span class='unit'>{item.unit}</span>
            </span>
            <span class='item-bottom'>
              <img
                src={this.getSvgIcon(item.icon)}
                alt=''
              />
              <span class='title'>{item.name}</span>
            </span>
          </div>
        ))}
        <div style={{ display: 'none' }}>
          <div ref='mttaTipRef'>
            <div>{window.i18n.tc('MTTA指平均应答时间 = 所有告警的总持续时间 / 总告警数量')}</div>
            <div>
              {window.i18n.tc(
                '其中持续时间指告警的首次异常时间到状态变更的时间段，状态变更如确认/屏蔽/恢复/关闭/已解决等'
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'none' }}>
          <div ref='mttrTipRef'>
            <div>{window.i18n.tc('MTTR指平均解决时间，平均解决时间=所有告警的持续时间/总告警数量')}</div>
            <div>{window.i18n.tc('其中持续时间指告警的首次异常时间到告警状态变成已解决或已恢复的时间段')}</div>
          </div>
        </div>
      </div>
    );
  }
}
