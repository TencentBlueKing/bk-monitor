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

import {
  type MaybeRef,
  type PropType,
  computed,
  defineComponent,
  getCurrentInstance,
  inject,
  shallowRef,
  toValue,
  useTemplateRef,
} from 'vue';

import { ResizeLayout } from 'bkui-vue';
import VueEcharts from 'vue-echarts';
import { useI18n } from 'vue-i18n';

import { resolveGraphPanel } from '../variables/resolve';
import ChartSkeleton from '@/components/skeleton/chart-skeleton';
import { useChartLegend } from '@/pages/trace-explore/components/explore-chart/use-chart-legend';
import { useChartTitleEvent } from '@/pages/trace-explore/components/explore-chart/use-chart-title-event';
import { useEcharts } from '@/pages/trace-explore/components/explore-chart/use-echarts';
import ChartTitle from '@/plugins/components/chart-title';
import CommonLegend from '@/plugins/components/common-legend';
import TableLegend from '@/plugins/components/table-legend';

import type { HostViewsGraphPanel } from '../../../types/panels';
import type { ScopedVarMap } from '../variables/resolve';
import type { ChartViewOptions } from '@/pages/trace-explore/components/explore-chart/use-chart-view-option';

import './time-series-card.scss';

export default defineComponent({
  name: 'TimeSeriesCard',
  props: {
    /** 图表面板 JSON（含 $变量占位符） */
    panel: {
      type: Object as PropType<HostViewsGraphPanel>,
      required: true,
    },
    /** 变量取值映射，变更后会重新解析 panel 并刷新取数 */
    scopedVars: {
      type: Object as PropType<ScopedVarMap>,
      default: () => ({}),
    },
    /** echarts 联动分组 id（同分组图表共享 tooltip/缩放） */
    dashboardId: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    const { t } = useI18n();
    const instance = getCurrentInstance();
    const chartRef = useTemplateRef<HTMLElement>('chart');
    const chartMainRef = useTemplateRef<HTMLElement>('chartMain');
    const resizeLayoutRef = useTemplateRef<InstanceType<typeof ResizeLayout>>('resizeLayout');
    const viewOptions = inject<MaybeRef<ChartViewOptions>>('viewOptions', undefined);

    /** 是否展示统计值 */
    const isShowStatistics = computed(() => toValue(viewOptions)?.showStatistics ?? false);

    /** 图表区域高度 */
    const chartHeight = shallowRef(200);
    /** 最大拉伸高度 */
    const layoutDragMaxHeight = shallowRef(300);
    const handleResizing = (height: number) => {
      const { height: layoutHeight } = resizeLayoutRef.value.$el.getBoundingClientRect();
      const rowHeight = 52; // 统计值表格表头高度+一行数据的高度+间隙高度
      layoutDragMaxHeight.value = layoutHeight - rowHeight; // 图表可拖拽的最大高度
      chartHeight.value = height > layoutDragMaxHeight.value ? layoutDragMaxHeight.value : height;
    };

    /** 变量解析后的可取数面板，scopedVars 变化时自动重算并触发取数 */
    const resolvedPanel = computed(() => resolveGraphPanel(props.panel, props.scopedVars, props.dashboardId));

    const { options, loading, metricList, targets, series, chartId } = useEcharts({
      panel: resolvedPanel,
      chartRef: chartMainRef,
      $api: instance.appContext.config.globalProperties.$api,
      params: computed(() => ({})),
      customOptions: {},
    });

    const { handleAlarmClick, handleMenuClick, handleMetricClick } = useChartTitleEvent(
      metricList,
      targets,
      computed(() => props.panel.title),
      series,
      chartRef
    );
    const { legendData, handleSelectLegend } = useChartLegend(options, chartId, {});

    return {
      t,
      instance,
      options,
      loading,
      metricList,
      legendData,
      isShowStatistics,
      chartHeight,
      layoutDragMaxHeight,
      handleResizing,
      handleAlarmClick,
      handleMenuClick,
      handleMetricClick,
      handleSelectLegend,
    };
  },
  render() {
    const renderChart = () => {
      return (
        <div
          ref='chartMain'
          class='time-series-card__chart'
        >
          <VueEcharts
            ref='echart'
            group={this.dashboardId}
            option={this.options}
            autoresize
          />
        </div>
      );
    };

    return (
      <div
        ref='chart'
        class='time-series-card'
      >
        <ChartTitle
          menuList={['more', 'explore', 'drill-down', 'relate-alert']}
          metrics={this.metricList}
          showAddMetric={true}
          showMore={true}
          subtitle={this.panel.subTitle || ''}
          title={this.panel.title}
          onAlarmClick={this.handleAlarmClick}
          onAllMetricClick={this.handleMetricClick}
          onMenuClick={this.handleMenuClick}
          onMetricClick={this.handleMetricClick}
          onSelectChild={({ child }) => this.handleMenuClick(child)}
        />
        {this.loading ? (
          <ChartSkeleton />
        ) : this.options ? (
          <>
            {this.isShowStatistics ? (
              <ResizeLayout
                ref='resizeLayout'
                class='time-series-card__resize-layout'
                border={false}
                initialDivide={`${this.chartHeight}px`}
                max={this.layoutDragMaxHeight}
                min={100}
                placement='top'
                onResizing={this.handleResizing}
              >
                {{
                  aside: renderChart,
                  main: () => (
                    <TableLegend
                      legendData={this.legendData}
                      onSelectLegend={this.handleSelectLegend}
                    />
                  ),
                }}
              </ResizeLayout>
            ) : (
              <>
                {renderChart()}
                <CommonLegend
                  legendData={this.legendData}
                  onSelectLegend={this.handleSelectLegend}
                />
              </>
            )}
          </>
        ) : (
          <div class='time-series-card__empty'>{this.t('暂无数据')}</div>
        )}
      </div>
    );
  },
});
