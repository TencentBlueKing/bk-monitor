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
import { type IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';
import { handleThreshold } from 'monitor-ui/chart-plugins/utils';

import { createAutoTimeRange } from './aiops-chart';

import type { IDetail } from './type';
import type { IDetectionConfig } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

import './time-series-forecasting-chart.scss';

interface IProps {
  detail: IDetail;
  detectionConfig: IDetectionConfig;
}
@Component
export default class TimeSeriesForecastingChart extends tsc<IProps> {
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  @Prop({ type: Object, default: () => ({}) }) detectionConfig: IDetectionConfig;

  @ProvideReactive('timeRange') timeRange: any = 1 * 60 * 60 * 1000;
  // 刷新间隔
  @ProvideReactive('refreshInterval') refreshInterval = -1;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 是否立即刷新
  @ProvideReactive('refreshImmediate') refreshImmediate = '';
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 对比类型
  @ProvideReactive('compareType') compareType = 'none';

  panel: PanelModel = null;

  /** 时序预测的预测时长 单位：秒 */
  get duration() {
    return (
      this.detectionConfig?.data?.find(item => item.type === 'TimeSeriesForecasting')?.config?.duration || 24 * 60 * 60
    );
  }

  mounted() {
    this.initPanel();
  }

  async initPanel() {
    const thresholdOptions = await handleThreshold(this.detectionConfig);

    const { startTime, endTime } = createAutoTimeRange(
      this.detail.begin_time,
      this.detail.end_time,
      this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval
    );

    const forecastTimeRange = [
      this.detail.latest_time,
      this.detail.latest_time + this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval,
    ];
    this.timeRange = [startTime, endTime];
    const panelSrcData = this.detail.graph_panel;
    const { id, title, subTitle, targets } = panelSrcData;
    const panelData = {
      id,
      title,
      subTitle,
      type: 'time-series-forecast',
      options: {
        time_series_forecast: {
          need_hover_style: false,
          duration: this.duration,
          ...thresholdOptions,
        },
      },
      targets: targets.map((item, index) => ({
        ...item,
        alias: '',
        options: {
          time_series_forecast: {
            forecast_time_range: index ? forecastTimeRange : undefined,
            no_result: !!index,
          },
        },
        data: {
          ...item.data,
          id: this.detail.id,
          function: undefined,
        },
        api: 'alert.alertGraphQuery',
      })),
    };
    this.panel = new PanelModel(panelData);
  }

  render() {
    return <div class='time-series-forecasting-chart'>{!!this.panel && <ChartWrapper panel={this.panel} />}</div>;
  }
}
