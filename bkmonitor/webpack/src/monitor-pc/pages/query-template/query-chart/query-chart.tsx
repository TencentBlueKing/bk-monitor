/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Debounce, random } from 'monitor-common/utils';
import QueryTemplateGraph from 'monitor-ui/chart-plugins/plugins/quey-template-graph/query-template-graph';
import { PanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import ChartSkeleton from '../components/skeletons/chart-skeleton';
import { hasVariable } from '../variables/template/utils';
import TimeRange, { type TimeRangeType } from '@/components/time-range/time-range';
import { DEFAULT_TIME_RANGE } from '@/components/time-range/utils';

import type { Expression } from '../typings/expression';
import type { AggCondition, AggFunction, QueryConfig } from '../typings/query-config';
import type { VariableModelType } from '../variables';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './query-chart.scss';

@Component
export default class QueryChart extends tsc<{
  expressionConfig: Expression;
  queryConfigs: QueryConfig[];
  title: string;
  variablesList: VariableModelType[];
}> {
  @Prop({ type: Array, default: () => [] }) queryConfigs: QueryConfig[];
  @Prop({ type: Object, default: () => {} }) expressionConfig: Expression;
  @Prop({ type: String, default: '' }) title: string;
  @Prop({ type: Array, default: () => [] }) variablesList: VariableModelType[];

  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions & { unit?: string } = {};
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  @ProvideReactive('handleUpdateQueryData') handleUpdateQueryData = () => {};

  panel: PanelModel = null;
  limit = 10;
  timezone = window.timezone;
  isLoading = false;
  get hasMetricSet() {
    return !!this.queryConfigs?.some?.(item => item.metricDetail?.metric_id);
  }

  get variablesValue() {
    return this.variablesList.reduce((acc, item) => {
      acc[item.variableName] = item.value;
      return acc;
    }, {});
  }

  created() {
    this.updateViewOptions();
  }

  @Watch('variablesValue')
  handleVariablesValueChange() {
    this.createPanel();
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
  getVariableValue<T>(variableName: string, callback?: (v: T) => void) {
    if (hasVariable(variableName)) {
      return this.variablesList.reduce((acc, item) => {
        return item.replace(acc, callback);
      }, variableName);
    }
    return variableName;
  }
  getVariableValues<T>(targets: string[]) {
    return targets.reduce((acc, target) => {
      if (hasVariable(target)) {
        this.getVariableValue<T>(target, v => {
          if (Array.isArray(v)) {
            acc.push(...v);
          } else {
            acc.push(v);
          }
        });
      } else {
        acc.push(target as T);
      }
      return acc;
    }, [] as T[]);
  }

  getFunctionsVariableValues(functions: AggFunction[]) {
    return functions.reduce((acc, item) => {
      if (hasVariable(item.id)) {
        this.getVariableValue<AggFunction>(item.id, v => {
          Array.isArray(v) ? acc.push(...v) : acc.push(v);
        });
      } else {
        acc.push(item);
      }
      return acc;
    }, [] as AggFunction[]);
  }

  @Debounce(300)
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
            expression: this.getVariableValue(this.expressionConfig.expression || 'a'), // 表达式变量解析
            query_configs: this.queryConfigs.map(item => ({
              data_label: item.metricDetail.data_label || undefined,
              data_source_label: item.data_source_label,
              data_type_label: item.data_type_label,
              interval: item.agg_interval,
              alias: item.alias || 'a',
              functions: this.getFunctionsVariableValues(item.functions || []), // 函数变量解析
              group_by: this.getVariableValues(item.agg_dimension || []), // 维度变量解析
              filter_dict: {},
              metrics: [
                {
                  field: item.metricDetail.metric_field,
                  method: this.getVariableValue(item.agg_method), // 聚合方法变量解析
                  alias: item.alias || 'a',
                  display: false,
                },
              ],
              table: item.metricDetail.result_table_id,
              where: item.agg_condition.reduce((acc, item) => {
                const { key, value } = item;
                if (hasVariable(key)) {
                  // 条件变量解析
                  acc.push(...this.getVariableValues<AggCondition>([key]));
                } else {
                  // 条件值变量解析
                  const newItem = structuredClone(item);
                  newItem.value = this.getVariableValues(value);
                  acc.push(newItem);
                }
                return acc;
              }, [] as AggCondition[]),
            })),
            functions: this.getFunctionsVariableValues(this.expressionConfig.functions || []),
          },
          datasource: 'time_series',
          api: 'grafana.graphUnifyQuery',
        },
      ],
    });
  }
  handleLimitChange(v: number) {
    this.limit = Number.isNaN(v) ? 10 : Math.min(Math.max(v, 1), 100);
    this.createPanel();
  }
  handleTimeRangeChange(val: TimeRangeType) {
    this.timeRange = [...val];
  }
  handleTimezoneChange(v: string) {
    this.timezone = v;
  }
  handleRefresh() {
    this.createPanel();
  }
  handleLoadingChange(v: boolean) {
    this.isLoading = v;
  }
  render() {
    return (
      <div class='query-chart'>
        <div class='query-chart-header'>
          <div class='query-chart-header-title'>{this.$slots.title || this.title}</div>
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
              onBlur={(v: number) => {
                this.handleLimitChange(Number(v));
              }}
              onEnter={(v: number, e: KeyboardEvent) => {
                if (e.key === 'Enter') {
                  this.handleLimitChange(Number(v));
                }
              }}
            />
          </div>
          <TimeRange
            class='query-timerange'
            timezone={this.timezone}
            value={this.timeRange}
            onChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          />
          <span
            class='icon-monitor icon-shuaxin refresh-btn'
            v-bk-tooltips={{ content: this.$t('刷新') }}
            onClick={this.handleRefresh}
          />
        </div>
        {this.isLoading && <ChartSkeleton class='query-chart-skeleton' />}
        {this.hasMetricSet && this.panel ? (
          <QueryTemplateGraph
            class='query-chart-content'
            limit={this.limit}
            panel={this.panel}
            onLoading={this.handleLoadingChange}
          />
        ) : (
          <div class='query-chart-content'>{this.$t('暂无数据')}</div>
        )}
      </div>
    );
  }
}
