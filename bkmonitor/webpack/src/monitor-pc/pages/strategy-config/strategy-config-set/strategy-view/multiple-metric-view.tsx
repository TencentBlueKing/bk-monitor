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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random, typeTools } from 'monitor-common/utils';
import ChartWrapper from 'monitor-ui/chart-plugins/components/chart-wrapper';
import { DEFAULT_INTERVAL } from 'monitor-ui/chart-plugins/constants';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { echartsConnect, echartsDisconnect } from 'monitor-ui/monitor-echarts/utils';

import { LETTERS } from '../../../../constant/constant';

import type { IMetricDetail, MetricDetail } from '../../strategy-config-set-new/typings';

import './multiple-metric-view.scss';

interface IProps {
  dimensions?: Record<string, any>;
  metrics?: MetricDetail[];
  nearNum?: number;
  refreshKey?: string;
  strategyTarget?: any[];
  onRefreshCharKey: () => void;
}

@Component
export default class MultipleMetricView extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) metrics: IMetricDetail[];
  @Prop({ default: () => [], type: Array }) strategyTarget: any[];
  /* 近多条数据 */
  @Prop({ default: 20, type: Number }) nearNum: number;
  /** 维度数据 */
  @Prop({ default: () => ({}), type: Object }) dimensions: string;
  @Prop({ default: '', type: String }) refreshKey: string;

  panels = [];
  dashboardId = random(10);

  @Emit('refreshCharKey')
  handleRefreshCharView() {}

  @Watch('refreshKey', { immediate: true })
  handleWatchRefleshKey() {
    this.initPanel();
  }

  initPanel() {
    const datas = this.metrics.map((metric, mIndex) => {
      const {
        data_label,
        metric_field_name: metricFieldName,
        data_source_label: dataSourceLabel,
        agg_interval,
        result_table_id: resultTableId,
        agg_dimension,
        agg_condition,
        default_dimensions,
        data_type_label: dataTypeLabel,
        metric_field: metricField,
        agg_method: aggMethod,
        alias,
        functions = [],
        time_field: timeField,
        bkmonitor_strategy_id: bkmonitorStrategyId,
        custom_event_name: customEventName,
        name,
      } = metric;
      const tableValue = () => {
        if (dataSourceLabel === 'bk_monitor' && dataTypeLabel === 'alert') {
          return 'strategy'; // 此类情况table固定为strategy
        }
        return resultTableId;
      };
      const fieldValue = () => {
        if (dataSourceLabel === 'bk_log_search' && dataTypeLabel === 'log') {
          return '_index'; // 此类情况field固定为_index
        }
        if (dataSourceLabel === 'custom' && dataTypeLabel === 'event') {
          return customEventName;
        }
        return metricField || bkmonitorStrategyId;
      };
      const localMetrics = [
        {
          field: fieldValue(),
          method: aggMethod || 'AVG',
          alias: alias || LETTERS[mIndex] || 'a',
          display: dataTypeLabel === 'alert',
        },
      ];
      const fieldDictParams =
        typeTools.isObject(this.dimensions) &&
        Object.keys(this.dimensions).reduce(
          (prev, key) => {
            if (!typeTools.isNull(this.dimensions[key])) {
              prev.fidldDict[key] = this.dimensions[key];
              prev.hasFilter = true;
            }
            return prev;
          },
          {
            fidldDict: {},
            hasFilter: false,
          }
        );

      const queryConfigs = {
        series_num: fieldDictParams?.hasFilter ? undefined : 20,
        expression: LETTERS[mIndex] || 'a',
        functions: [],
        target: this.strategyTarget || [],
        query_configs: [
          {
            data_source_label: dataSourceLabel,
            data_type_label: dataTypeLabel,
            data_label,
            metrics: localMetrics,
            table: tableValue(),
            group_by: agg_dimension || default_dimensions || [],
            where: agg_condition?.filter(item => item.key && item.value?.length) || [],
            interval: agg_interval || DEFAULT_INTERVAL,
            time_field: timeField || 'time',
            filter_dict: fieldDictParams.fidldDict || {},
            functions,
            target: this.strategyTarget || [],
          },
        ],
      };
      return {
        id: this.dashboardId,
        dashboardId: this.dashboardId,
        type: 'graph',
        title: name || metricFieldName,
        subTitle: '',
        options: {
          time_series: {
            type: 'line',
            only_one_result: false,
            custom_timerange: true,
            noTransformVariables: false,
            nearSeriesNum: this.nearNum,
          },
        },
        targets: [
          {
            data: queryConfigs,
            alias: '',
            datasource: 'time_series',
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
          },
        ],
      };
    });
    this.panels = datas.map(data => new PanelModel(data as any));
    echartsConnect(this.dashboardId);
    this.handleRefreshCharView();
  }

  destroyed() {
    echartsDisconnect(this.dashboardId);
  }

  render() {
    return (
      <div class='multiple-metric-view-component'>
        {this.panels.map((panel, index) => (
          <div
            key={index}
            class='panel-item'
          >
            <ChartWrapper
              needCheck={false}
              needHoverStyle={false}
              panel={panel}
            />
          </div>
        ))}
      </div>
    );
  }
}
