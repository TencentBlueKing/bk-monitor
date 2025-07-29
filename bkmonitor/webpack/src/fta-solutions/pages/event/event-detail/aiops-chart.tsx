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

import dayjs from 'dayjs';
import { random } from 'monitor-common/utils/utils';
import { transformSensitivityValue } from 'monitor-pc/pages/strategy-config/util';
import ChartWrapper from 'monitor-ui/chart-plugins/components/chart-wrapper';
import { type IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';
import { handleThreshold, parseMetricId } from 'monitor-ui/chart-plugins/utils';

import type { IDetail } from './type';
import type { IDetectionConfig } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

/** 自动生成一个时间范围
 * 1、时间的起始时间，当发生时是发生时间往前60个周期
 * 2、当发生时间一直往后延，起始时间变成 初次异常+5周期数据
 * 3、结束时间一直到事件结束后的五个周期，或最多不超过1440个周期
 */

export const createAutoTimeRange = (
  startTime: number,
  endTime: number,
  interval = 60
): { endTime: string; startTime: string } => {
  // const interval = this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
  const INTERVAL_5 = 5 * interval * 1000;
  const INTERVAL_1440 = 1440 * interval * 1000;
  const INTERVAL_60 = 60 * interval * 1000;
  let newStartTime = startTime * 1000;
  let newEndTime = endTime ? endTime * 1000 : +new Date();
  newEndTime = Math.min(newEndTime + INTERVAL_5, newStartTime + INTERVAL_1440);
  let diff = INTERVAL_1440 - (newEndTime - newStartTime);
  if (diff < INTERVAL_5) {
    diff = INTERVAL_5;
  } else if (diff > INTERVAL_60) {
    diff = INTERVAL_60;
  }
  newStartTime -= diff;
  const result = {
    startTime: dayjs.tz(newStartTime).format('YYYY-MM-DD HH:mm:ss'),
    endTime: dayjs.tz(newEndTime).format('YYYY-MM-DD HH:mm:ss'),
  };
  return result;
};
interface IProps {
  detail: IDetail;
  detectionConfig: IDetectionConfig;
}
@Component
export default class AiopsChartEvent extends tsc<IProps> {
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
  dashboardId = random(10);

  /** 图表的targets */
  get graphPanelTargets() {
    return this.detail.graph_panel.targets;
  }

  get queryConfigs() {
    return this.detail.extra_info?.strategy?.items?.[0]?.query_configs;
  }

  /** 异常分值阈值线数据 */
  get scoreThreshold(): IDetectionConfig {
    const aiDetectionConfig = this.detectionConfig.data.find(item => item.type === 'IntelligentDetect');
    let val = aiDetectionConfig?.config?.args?.$sensitivity;
    if (val === undefined) return null;
    /** 敏感度阈值转换规则 threshold = (1 - sensitivity / 10) * 0.8 + 0.1 */
    val = transformSensitivityValue(val);
    return {
      connector: 'and',
      data: [
        {
          level: 1,
          type: 'Threshold',
          config: [[{ method: 'gte', threshold: val, name: this.$t('异常分值阈值') }]],
          title: this.$t('异常分值阈值'),
        },
      ],
      unit: '',
      unitList: [],
      unitType: '',
    };
  }

  /** 指标图的图表title */
  get metricName() {
    return this.detail?.extra_info?.strategy?.items?.[0]?.name || this.$t('指标');
  }

  mounted() {
    this.initPanel();
  }

  /** 初始化图表的panel */
  async initPanel() {
    const panelData = {
      id: random(10),
      title: '',
      type: 'graphs',
      options: {
        time_series_list: {
          need_hover_style: false,
        },
      },
      panels: await Promise.all(this.graphPanelTargets.map(async (item, index) => this.createPanel(item, index === 0))),
    };
    this.panel = new PanelModel(panelData as any);

    const { startTime, endTime } = createAutoTimeRange(
      this.detail.begin_time,
      this.detail.end_time,
      this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval
    );
    this.timeRange = [startTime, endTime];
  }

  /** 创建一个图表的配置 */
  async createPanel(data, isMetric = true) {
    const thresholdOptions = await handleThreshold(isMetric ? this.detectionConfig : this.scoreThreshold);
    const result = {
      id: this.dashboardId,
      type: 'graph',
      title: isMetric ? this.metricName : this.$t('异常分值'),
      subTitle: '',
      dashboardId: this.dashboardId,
      options: {
        time_series: {
          // only_one_result: true,
          custom_timerange: true,
          ...thresholdOptions,
        },
        legend: isMetric ? {} : { displayMode: 'hidden' },
        header: {
          tips: this.$t('异常分值范围从0～1，越大越异常'),
        },
      },
      targets: [
        {
          data: {
            ...data.data,
            function: isMetric ? data.data.function : undefined,
            id: this.detail.id,
            bk_biz_id: this.detail.bk_biz_id,
            query_configs: data.data.query_configs.map(item => {
              const parseData = parseMetricId(this.queryConfigs?.[0].metric_id);
              /** 原始的指标数据 */
              const originMetricData = {
                dataSourceLabel: parseData.data_source_label ?? '',
                resultTableId: parseData.result_table_id ?? '',
                metricField: parseData.metric_field ?? '',
                dataTypeLabel: parseData.data_type_label ?? '',
              };
              return {
                ...item,
                originMetricData,
              };
            }),
          },
          alias: '',
          datasource: 'time_series',
          data_type: 'time_series',
          api: 'alert.alertGraphQuery',
          // api: 'grafana.graphUnifyQuery'
        },
      ],
    };
    return new PanelModel(result as any);
  }

  render() {
    return <div class='event-detial-aiops-chart'>{!!this.panel && <ChartWrapper panel={this.panel} />}</div>;
  }
}
