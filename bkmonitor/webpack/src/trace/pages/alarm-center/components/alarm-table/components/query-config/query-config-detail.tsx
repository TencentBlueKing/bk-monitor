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

import { type PropType, computed, defineComponent } from 'vue';

import ConditionDetail from './components/condition/condition-detail';
import DimensionDetail from './components/dimension/dimension-detail';
import FunctionDetail from './components/function/function-detail';
import IntervalDetail from './components/interval/interval-detail';
import MethodDetail from './components/method/method-detail';
import MetricDetail from './components/metric/metric-detail';

import type { DimensionField, QueryConfig } from 'monitor-pc/pages/query-template/typings';

import './query-config-detail.scss';

export default defineComponent({
  name: 'QueryConfigDetail',
  props: {
    queryConfig: {
      type: Object as PropType<QueryConfig>,
    },
    showAlias: {
      type: Boolean,
      default: true,
    },
  },
  setup(props) {
    const getAllDimensionMap = computed<Record<string, DimensionField>>(() => {
      const options = props.queryConfig?.metricDetail?.dimensionList || [];
      if (!options?.length) {
        return {};
      }
      return options?.reduce?.((prev, curr) => {
        prev[curr.id] = curr;
        return prev;
      }, {});
    });

    return {
      getAllDimensionMap,
    };
  },
  render() {
    return (
      <div class='alert-query-config-detail-component'>
        {this.showAlias ? (
          <div class='alias-wrap'>
            <span>{this.queryConfig?.alias || 'a'}</span>
          </div>
        ) : null}
        <div class='query-config-wrap'>
          <MetricDetail metricDetail={this.queryConfig.metricDetail} />
          <MethodDetail value={this.queryConfig?.agg_method} />
          <IntervalDetail value={this.queryConfig?.agg_interval} />
          <DimensionDetail
            allDimensionMap={this.getAllDimensionMap}
            value={this.queryConfig?.agg_dimension}
          />
          <ConditionDetail
            allDimensionMap={this.getAllDimensionMap}
            value={this.queryConfig.agg_condition}
          />
          <FunctionDetail value={this.queryConfig?.functions} />
        </div>
      </div>
    );
  },
});
