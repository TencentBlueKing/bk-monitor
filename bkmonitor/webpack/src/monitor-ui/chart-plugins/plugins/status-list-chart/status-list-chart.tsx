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

import { Component } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import ChartHeader from '../../components/chart-title/chart-title';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';

import type { IExtendMetricData, IStatusItemData, IStatusListData, PanelModel } from '../../typings';

import './status-list-chart.scss';

interface IStatusListChartProps {
  panel: PanelModel;
}
@Component
class StatusListChart extends CommonSimpleChart {
  data: IStatusListData[][] = [];
  emptyText = window.i18n.tc('加载中...');
  empty = true;
  metrics: IExtendMetricData[];

  /**
   * @description: 获取图表数据
   */
  async getPanelData(start_time?: string, end_time?: string) {
    this.handleLoadingChange(true);
    this.empty = true;
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
      };
      const variablesService = new VariablesService({
        ...this.scopedVars,
      });
      const promiseList = this.panel.targets.map(item =>
        (this as any).$api[item.apiModule]
          ?.[item.apiFunc](
            {
              ...variablesService.transformVariables(item.data),
              ...params,
              view_options: {
                ...this.viewOptions,
              },
            },
            { needMessage: false }
          )
          .then(res => {
            this.clearErrorMsg();
            return res;
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
          })
      );
      const res = await Promise.all(promiseList);
      if (res?.every?.(item => item.length)) {
        this.inited = true;
        this.empty = false;
        this.data = res;
      } else {
        this.emptyText = window.i18n.tc('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.handleLoadingChange(false);
  }

  handleJump(item: IStatusItemData) {
    if (!item.link?.url) return;
    let { target } = item.link;
    if (!target) target = '_target';
    if (target[0] !== '_') target = `_${target}`;
    window.open(item.link.url, target);
  }

  chartContent() {
    return (
      <div class='status-list-chart-content'>
        {this.data[0].map(item => (
          <div class='content-item'>
            <span class='item-title'>{item.name}</span>
            <div class='item-val-box'>
              {item.items.map(v => (
                <div
                  style={{ cursor: v.link ? 'pointer' : '' }}
                  class='item-val'
                  onClick={() => this.handleJump(v)}
                >
                  <div
                    style={{ 'background-color': v.color }}
                    class='dot'
                  />
                  <span>{v.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  render() {
    return (
      <div class='status-list-chart'>
        <ChartHeader
          class='draggable-handle'
          metrics={this.metrics}
          title={this.panel.title}
        />
        {!this.empty ? this.chartContent() : <span class='empty-chart'>{this.emptyText}</span>}
      </div>
    );
  }
}

export default ofType<IStatusListChartProps>().convert(StatusListChart);
