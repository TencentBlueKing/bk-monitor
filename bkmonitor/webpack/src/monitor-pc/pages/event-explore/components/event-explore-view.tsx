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
import { Component, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { eventTotal } from 'monitor-api/modules/data_explorer';

import EventExploreChart from './event-explore-chart';

import './event-explore-view.scss';

interface IEventExploreViewProps {
  /** 请求接口公共请求参数 */
  commonParams: Record<string, any>;
}

@Component
export default class EventExploreView extends tsc<IEventExploreViewProps> {
  /** 请求接口公共请求参数 */
  @Prop({ type: Object, default: () => ({}) }) commonParams: Record<string, any>;
  /** 是否立即刷新 */
  @InjectReactive('refleshImmediate') refleshImmediate: string;
  /** 数据总数 */
  total = 0;

  @Watch('commonParams', { deep: true })
  commonParamsChange() {
    this.getEventTotal();
  }

  @Watch('refleshImmediate')
  refleshImmediateChange() {
    this.getEventTotal();
  }

  /**
   * @description 获取数据总数
   */
  async getEventTotal() {
    const {
      start_time: commonStartTime,
      end_time: commonEndTime,
      query_configs: [commonQueryConfig],
    } = this.commonParams;
    if (!commonQueryConfig?.table || !commonStartTime || !commonEndTime) {
      return;
    }
    const { total } = await eventTotal(this.commonParams).catch(() => ({ total: 0 }));
    this.total = total;
  }

  render() {
    return (
      <div class='event-explore-view-wrapper'>
        <div class='event-explore-chart-wrapper'>
          <EventExploreChart
            commonParams={this.commonParams}
            total={this.total}
          />
        </div>
        <div class='event-explore-table'>table</div>
      </div>
    );
  }
}
