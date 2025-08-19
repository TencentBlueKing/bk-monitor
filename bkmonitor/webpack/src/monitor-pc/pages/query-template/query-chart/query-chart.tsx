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
import { Component, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';
import QueryTemplateGraph from 'monitor-ui/chart-plugins/plugins/quey-template-graph/query-template-graph';
import { PanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import TimeRange, { type TimeRangeType } from '@/components/time-range/time-range';
import { DEFAULT_TIME_RANGE } from '@/components/time-range/utils';

import type { Expression } from '../typings/expression';
import type { QueryConfig } from '../typings/query-config';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './query-chart.scss';

@Component
export default class QueryChart extends tsc<{
  expressionConfig: Expression;
  queryConfigs: QueryConfig[];
  title: string;
}> {
  @Prop({ type: Array, default: () => [] }) queryConfigs: QueryConfig[];
  @Prop({ type: Object, default: () => {} }) expressionConfig: Expression;
  @Prop({ type: String, default: '' }) title: string;

  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions & { unit?: string } = {};
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;

  panel: PanelModel = null;
  limit = 10;
  timezone = window.timezone;
  get hasMetricSet() {
    return !!this.queryConfigs?.some?.(item => item.metricDetail?.metric_id);
  }
  created() {
    this.updateViewOptions();
  }
  @Watch('queryConfigs', { immediate: true })
  handleQueryConfigsChange() {
    this.createPanel();
  }
  updateViewOptions() {
    this.viewOptions = {
      interval: 'auto',
    };
  }
  createPanel() {
    this.panel = new PanelModel({
      id: random(10),
      type: 'query-template-graph',
      title: this.title,
      subTitle: '',
      targets: [
        {
          data: {
            series_num: this.limit,
            expression: this.expressionConfig.expression || 'a',
            query_configs: this.queryConfigs.map(item => ({
              data_label: item.metricDetail.data_label || undefined,
              data_source_label: item.data_source_label,
              data_type_label: item.data_type_label,
              interval: item.agg_interval,
              alias: item.alias || 'a',
              functions: item.functions,
              group_by: item.agg_dimension,
              filter_dict: {},
              metrics: [
                {
                  field: item.metricDetail.metric_field,
                  method: item.agg_method,
                  alias: item.alias || 'a',
                  display: false,
                },
              ],
              table: item.metricDetail.result_table_id,
              where: item.agg_condition,
            })),
          },
          datasource: 'time_series',
          api: 'grafana.graphUnifyQuery',
        },
      ],
    });
  }
  handleLimitChange(v: number) {
    this.limit = v;
  }
  handleTimeRangeChange(val: TimeRangeType) {
    this.timeRange = [...val];
  }
  handleTimezoneChange(v: string) {
    this.timezone = v;
  }
  render() {
    return (
      <div class='query-chart'>
        <div class='query-chart-header'>
          <div class='query-chart-header-title'>{this.title}</div>
          <div class='query-chart-header-limit'>
            <span style='margin-right: 8px;'>Limit</span>
            <bk-input
              style='width: 80px;'
              behavior='simplicity'
              max={100}
              min={1}
              placeholder={this.$t('请输入1~100的数字')}
              size='small'
              type='number'
              value={this.limit}
              onChange={this.handleLimitChange}
            />
          </div>
          <TimeRange
            class='query-timerange'
            timezone={this.timezone}
            value={this.timeRange}
            onChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          />
        </div>
        {this.hasMetricSet ? (
          <QueryTemplateGraph
            class='query-chart-content'
            panel={this.panel}
          />
        ) : (
          <div class='query-chart-content'>{this.$t('暂无数据')}</div>
        )}
      </div>
    );
  }
}
