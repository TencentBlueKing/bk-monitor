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
import { Component, Prop, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import ChartWrapper from 'monitor-ui/chart-plugins/components/chart-wrapper';
import { IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import { createAutoTimerange } from './aiops-chart';
import { IDetail } from './type';

import './outlier-detection-chart.scss';

/**
 * 事件中心离群检测算法图表
 */
@Component
export default class OutlierDetectionChart extends tsc<{}> {
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;

  @ProvideReactive('timeRange') timeRange: any = 1 * 60 * 60 * 1000;
  // 刷新间隔
  @ProvideReactive('refleshInterval') refleshInterval = -1;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 是否立即刷新
  @ProvideReactive('refleshImmediate') refleshImmediate = '';
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 对比类型
  @ProvideReactive('compareType') compareType = 'none';

  panel: PanelModel = null;

  mounted() {
    this.initPanel();
  }

  async initPanel() {
    // eslint-disable-next-line max-len
    const { startTime, endTime } = createAutoTimerange(
      this.detail.begin_time,
      this.detail.end_time,
      this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval
    );
    this.timeRange = [startTime, endTime];
    const panelSrcData = this.detail.graph_panel;
    const { id, title, subTitle, targets } = panelSrcData;
    const panelData = {
      id,
      title,
      subTitle,
      type: 'time-series-outlier',
      options: {},
      targets: targets.map(item => ({
        ...item,
        alias: '',
        options: {},
        data: {
          ...item.data,
          id: this.detail.id,
          function: undefined
        },
        api: 'alert.alertGraphQuery'
      }))
    };
    this.panel = new PanelModel(panelData);
  }
  render() {
    return (
      <div class='outlier-detection-chart'>{!!this.panel && <ChartWrapper panel={this.panel}></ChartWrapper>}</div>
    );
  }
}
