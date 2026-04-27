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

import { type PropType, defineComponent, toRef } from 'vue';

import { useDataVolumeTrend } from '../../hooks/use-data-volume-trend';
import { useNoDataStrategy } from '../../hooks/use-no-data-strategy';
import AlertInfoCard from './components/alert-info-card/alert-info-card';
import DataVolumeTrend from './components/data-volume-trend/data-volume-trend';

import type { IRumAppConfig, IStrategyData } from '../../../typings';

import './data-state.scss';

export default defineComponent({
  name: 'DataState',
  props: {
    /** 应用基本信息数据 */
    detail: {
      type: Object as PropType<IRumAppConfig>,
      default: () => ({}),
    },
  },
  setup(props) {
    /** 无数据告警策略状态与处理 */
    const {
      strategyInfo,
      handleEnabledChange,
      loading: strategyLoading,
    } = useNoDataStrategy({
      bizId: toRef(props.detail.bk_biz_id),
      appName: toRef(props.detail.app_name),
    });

    /** 数据量趋势图表数据与加载状态 */
    const { dashboardPanels, loading: dashboardLoading } = useDataVolumeTrend({
      bizId: toRef(props.detail.bk_biz_id),
      appName: toRef(props.detail.app_name),
    });

    return {
      dashboardPanels,
      handleEnabledChange,
      dashboardLoading,
      strategyInfo,
      strategyLoading,
    };
  },
  render() {
    return (
      <div class='run-config-data-state'>
        <AlertInfoCard
          class='run-config-data-state-card'
          loading={this.strategyLoading}
          strategyInfo={this.strategyInfo as IStrategyData}
          onEnabledChange={this.handleEnabledChange}
        />
        <div class='run-config-data-state-chart-container'>
          <div class='run-config-data-state-chart-title'>数据量趋势</div>
          <div class='run-config-data-state-chart-content'>
            <DataVolumeTrend
              class='run-config-data-state-chart'
              dashboardPanels={this.dashboardPanels}
              loading={this.dashboardLoading}
            />
          </div>
        </div>
        <div class='run-config-data-state-table'>数据表区域</div>
      </div>
    );
  },
});
