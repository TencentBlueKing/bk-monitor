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
import { type PropType, computed, defineComponent, inject, toRef, useTemplateRef, watch } from 'vue';
import { getCurrentInstance } from 'vue';
import { shallowRef } from 'vue';

import { get } from '@vueuse/core';
import VueEcharts from 'vue-echarts';
import { useI18n } from 'vue-i18n';

import ChartSkeleton from '../../../../../../../components/skeleton/chart-skeleton';
import { DEFAULT_TIME_RANGE } from '../../../../../../../components/time-range/utils';
import ChartTitle from '../../../../../../../plugins/components/chart-title';
import CommonLegend from '../../../../../../../plugins/components/common-legend';
import { commOpenUrl, getMetricId } from '../../../../../../../plugins/utls/menu';
import {
  type LegendCustomOptions,
  useChartLegend,
} from '../../../../../../trace-explore/components/explore-chart/use-chart-legend';
import { useChartTitleEvent } from '../../../../../../trace-explore/components/explore-chart/use-chart-title-event';
import { useK8sEcharts } from './hooks/use-k8s-echarts';

import type { IDataQuery, IMenuItem } from '../../../../../../../plugins/typings';
import type { DataZoomEvent } from '../../../../../../trace-explore/components/explore-chart/types';
import type { CustomOptions } from '../../../../../../trace-explore/components/explore-chart/use-echarts';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './k8s-custom-chart.scss';
export default defineComponent({
  name: 'K8sCustomChart',
  props: {
    /** 面板数据配置 */
    panel: {
      type: Object as PropType<PanelModel>,
      required: true,
    },
    /** 是否显示图表 Title 组件 */
    showTitle: {
      type: Boolean,
      default: true,
    },
    /** 图表数据格式化函数 */
    customOptions: {
      type: Object as PropType<CustomOptions>,
      default: () => ({}),
    },
    /** 图例配置 */
    customLegendOptions: {
      type: Object as PropType<LegendCustomOptions>,
      default: () => ({}),
    },
    /** 查询参数 */
    params: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    /** 是否展示复位按钮 */
    showRestore: {
      type: Boolean,
      default: false,
    },
    /** 所有联动图表中存在有一个图表触发 hover 是否展示所有联动图表的 tooltip(默认 false) */
    hoverAllTooltips: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['dataZoomChange', 'durationChange', 'restore'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const chartInstance = useTemplateRef<InstanceType<typeof VueEcharts>>('echart');
    const instance = getCurrentInstance();
    const chartRef = useTemplateRef<HTMLElement>('chart');
    const chartMainRef = useTemplateRef<HTMLElement>('chartMain');
    const mouseIn = shallowRef(false);
    const panel = computed(() => props.panel);
    const panelTitle = computed(() => panel.value?.title);
    const params = computed(() => props.params);
    const timeRange = inject('timeRange', DEFAULT_TIME_RANGE);

    const { options, loading, metricList, targets, series, duration, chartId } = useK8sEcharts(
      panel,
      chartMainRef,
      instance.appContext.config.globalProperties.$api,
      params,
      props.customOptions,
      {
        isMouseOver: mouseIn,
        hoverAllTooltips: toRef(props, 'hoverAllTooltips'),
      }
    );
    const { handleAlarmClick, handleMenuClick, handleMetricClick } = useChartTitleEvent(
      metricList,
      targets,
      panelTitle,
      series,
      chartRef
    );
    const { legendData, handleSelectLegend } = useChartLegend(options, chartId, props.customLegendOptions);
    const handleDataZoom = (event: DataZoomEvent, echartOptions) => {
      chartInstance.value.dispatchAction({
        type: 'restore',
      });
      if (!mouseIn.value) return;
      const xAxisData = echartOptions.xAxis[0]?.data;
      if (!xAxisData.length || xAxisData.length <= 2) return;
      let { startValue, endValue } = event.batch[0];
      startValue = Math.max(0, startValue);
      endValue = Math.min(endValue, xAxisData.length - 1);
      let endTime = xAxisData[endValue];
      let startTime = xAxisData[startValue];
      if (startValue === endValue) {
        endTime = xAxisData[endValue + 1];
      }
      if (!endTime) {
        endTime = xAxisData[startValue] + 1000;
      }
      if (!startTime) {
        startTime = xAxisData[0];
      }
      emit('dataZoomChange', [startTime, endTime]);
    };

    const handleMouseInChange = (v: boolean) => {
      mouseIn.value = v;
    };

    /**
     * @method handleRelateAlert 代理菜单点击事件
     * @description 由于本处的 相关告警 跳转逻辑比较特殊，需要特殊处理，其他类型任然使用原逻辑
     * @param targets 图表 targets 配置
     * @param timeRange 时间范围
     */
    const handleRelateAlert = (targets: IDataQuery[], timeRange: string[]) => {
      const metricIdMap: any = {};
      const promqlSet = new Set<string>();
      for (const target of targets) {
        if (target.data?.query_configs?.length) {
          for (const item of target.data.query_configs) {
            if (item.promql) {
              promqlSet.add(JSON.stringify(item.promql));
            } else {
              const metricId = getMetricId(
                item.data_source_label,
                item.data_type_label,
                item.metrics?.[0]?.field,
                item.table,
                item.index_set_id
              );
              if (metricId) {
                metricIdMap[metricId] = 'true';
              }
            }
          }
        }
      }
      let queryString = '';
      for (const metricId of Object.keys(metricIdMap)) {
        queryString += `${queryString.length ? ' OR ' : ''}指标ID : ${metricId}`;
      }
      let promqlString = '';
      for (const promql of promqlSet) {
        promqlString = `promql=${promql}`;
      }
      queryString = promqlString ? promqlString : `queryString=${queryString}`;
      queryString.length &&
        window.open(commOpenUrl(`#/event-center?${queryString}&from=${timeRange[0]}&to=${timeRange[1]}`));
    };

    /**
     * @method handleMenuClickProxy 代理菜单点击事件
     * @description 由于本处的 相关告警 跳转逻辑比较特殊，需要特殊处理，其他类型任然使用原逻辑
     * @param item 菜单项
     */
    const handleMenuClickProxy = (item: IMenuItem) => {
      switch (item.id) {
        case 'relate-alert':
          handleRelateAlert(get(targets), get(timeRange));
          return;
        default:
          handleMenuClick(item);
          return;
      }
    };

    watch(
      () => duration.value,
      val => {
        emit('durationChange', val);
      }
    );

    watch(
      [loading, options],
      async () => {
        if (!loading.value && options.value) {
          setTimeout(() => {
            chartInstance.value?.dispatchAction({
              type: 'takeGlobalCursor',
              key: 'dataZoomSelect',
              dataZoomSelectActive: true,
            });
          }, 1000);
        }
      },
      {
        immediate: false,
        flush: 'post',
      }
    );
    return {
      loading,
      options,
      metricList,
      legendData,
      handleAlarmClick,
      handleMenuClickProxy,
      handleMetricClick,
      handleSelectLegend,
      handleDataZoom,
      handleMouseInChange,
      t,
    };
  },
  render() {
    return (
      <div
        ref='chart'
        class='k8s-custom-chart'
      >
        {this.panel && this.showTitle && (
          <ChartTitle
            class='draggable-handle'
            dragging={this.panel.dragging}
            isInstant={this.panel.instant}
            menuList={['more', 'explore', 'area', 'drill-down', 'relate-alert']}
            metrics={this.metricList}
            showAddMetric={true}
            showMore={true}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleMetricClick}
            onMenuClick={this.handleMenuClickProxy}
            onMetricClick={this.handleMetricClick}
            onSelectChild={({ child }) => this.handleMenuClickProxy(child)}
          />
        )}
        {this.loading ? (
          <ChartSkeleton />
        ) : this.options ? (
          <>
            <div
              ref='chartMain'
              class='k8s-custom-chart-container'
              onMouseout={() => this.handleMouseInChange(false)}
              onMouseover={() => this.handleMouseInChange(true)}
            >
              <VueEcharts
                ref='echart'
                group={this.panel.dashboardId}
                option={this.options}
                autoresize
                onDatazoom={e => this.handleDataZoom(e, this.options)}
              />

              {this.showRestore && (
                <span
                  class='chart-restore'
                  onClick={() => this.$emit('restore')}
                >
                  {this.$t('复位')}
                </span>
              )}
            </div>
            <CommonLegend
              legendData={this.legendData}
              onSelectLegend={this.handleSelectLegend}
            />
          </>
        ) : (
          <div class='empty-chart'>{this.t('暂无数据')}</div>
        )}
      </div>
    );
  },
});
