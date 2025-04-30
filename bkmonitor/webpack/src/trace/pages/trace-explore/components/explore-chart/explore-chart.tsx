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
import { computed, defineComponent, useTemplateRef, type PropType } from 'vue';
import { getCurrentInstance } from 'vue';
import VueEcharts from 'vue-echarts';

import ChartSkeleton from '@/components/skeleton/chart-skeleton';
import ChartTitle from '@/plugins/components/chart-title';
// import { useTraceExploreStore } from '@/store/modules/explore';

import { useChartTitleEvent } from './use-chart-title-event';
import { useEcharts } from './use-echarts';

import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './explore-chart.scss';
export default defineComponent({
  name: 'ExploreChart',
  props: {
    panel: {
      type: Object as PropType<PanelModel>,
      required: true,
    },
  },
  setup(props) {
    // const store = useTraceExploreStore();
    // const panelModels = shallowRef<PanelModel[]>([]);
    // const dashboardId = random(10);
    // const traceStore = useTraceExploreStore();
    const instance = getCurrentInstance();
    const chartRef = useTemplateRef<Element>('chart');
    const panel = computed(() => props.panel);
    const { options, loading, metricList } = useEcharts(
      panel,
      chartRef,
      instance.appContext.config.globalProperties.$api
    );
    const { handleAlarmClick, handleMenuClick, handleMetricClick } = useChartTitleEvent(metricList);
    return {
      loading,
      options,
      metricList,
      handleAlarmClick,
      handleMenuClick,
      handleMetricClick,
    };
  },
  render() {
    return (
      <div
        ref='chart'
        class='explore-chart'
      >
        {this.panel && !!this.metricList?.length && (
          <ChartTitle
            class='draggable-handle'
            dragging={this.panel.dragging}
            // drillDownOption={this.drillDownOptions}
            // isInstant={this.panel.instant}
            // menuList={this.menuList}
            metrics={this.metricList}
            showAddMetric={true}
            showMore={true}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleMetricClick}
            // onMenuClick={this.handleMenuClick}
            // onMetricClick={this.handleMetricClick}
            // onSelectChild={({ child }) => this.handleMenuClick(child)}
            // onUpdateDragging={() => this.panel?.updateDragging(false)}
          />
        )}
        {this.loading ? (
          <ChartSkeleton />
        ) : this.options ? (
          <VueEcharts
            option={this.options}
            autoresize
          />
        ) : (
          <div class='empty-chart'>{this.$t('暂无数据')}</div>
        )}
      </div>
    );
  },
});
