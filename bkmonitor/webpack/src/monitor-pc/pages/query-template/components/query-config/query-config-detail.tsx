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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getMetricListV2 } from 'monitor-api/modules/strategies';

import { VariableTypeEnum } from '../../constants';
import DimensionDetail from '../dimension/dimension-detail';
import IntervalDetail from '../interval/interval-detail';
import MethodDetail from '../method/method-detail';
import MetricDetail from '../metric/metric-detail';
import { type TMetricDetail, MetricDetail as MetricDetailPanel } from '../type/query-config';

import type { VariableModelType } from '../../variables';

import './query-config-detail.scss';

interface IProps {
  queryConfig?: IQueryConfig;
  variables?: VariableModelType[];
}

interface IQueryConfig {
  agg_dimension: string[];
  agg_interval: number;
  agg_method: string;
  alias?: string;
  metric_id: string;
}

@Component
export default class QueryConfigDetail extends tsc<IProps> {
  @Prop({ default: null }) queryConfig: IQueryConfig;
  @Prop({ default: () => [] }) variables: VariableModelType[];

  /* 指标详情类实例 */
  metricInstance: TMetricDetail = null;
  loading = false;

  get getMethodVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.METHOD);
  }
  get getDimensionVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.DIMENSION);
  }

  @Watch('queryConfig.metric_id', { immediate: true })
  async handleWatchMetricId() {
    this.getMetricDetail();
  }

  async getMetricDetail() {
    if (this.queryConfig?.metric_id && this.metricInstance?.metric_id !== this.queryConfig?.metric_id) {
      this.loading = true;
      const { metric_list: metricList = [] } = await getMetricListV2({
        conditions: [{ key: 'metric_id', value: [this.queryConfig?.metric_id] }],
      }).catch(() => ({}));
      const metric = metricList[0];
      if (metric) {
        this.metricInstance = new MetricDetailPanel(metric);
      }
      this.loading = false;
    }
  }
  render() {
    return (
      <div class='template-query-config-detail-component'>
        <div class='alias-wrap'>
          <span>{this.queryConfig?.alias || 'a'}</span>
        </div>
        <div class='query-config-wrap'>
          <MetricDetail metric={this.metricInstance} />
          <MethodDetail
            method={this.queryConfig?.agg_method}
            variables={this.getMethodVariables}
          />
          <IntervalDetail interval={this.queryConfig?.agg_interval} />
          <DimensionDetail
            dimensions={this.queryConfig?.agg_dimension}
            options={this.metricInstance?.dimensions}
            variables={this.getDimensionVariables}
          />
          {/* <MethodCreator
            key={'method'}
            showVariables={true}
            variables={this.getMethodVariables}
          />
          ,
          <DimensionCreator key={'dimension'} />, */}
        </div>
      </div>
    );
  }
}
