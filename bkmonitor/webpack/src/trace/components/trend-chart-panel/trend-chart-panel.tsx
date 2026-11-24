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
import { type PropType, computed, defineComponent, inject, provide, shallowRef, toRef, toValue } from 'vue';

import { useI18n } from 'vue-i18n';

import ChartCollapse from '../../pages/trace-explore/components/explore-chart/chart-collapse';
import ExploreChart from '../../pages/trace-explore/components/explore-chart/explore-chart';
import IntervalSelect from '../interval-select/interval-select';

import type { CustomOptions } from '../../pages/trace-explore/components/explore-chart/use-echarts';
import type { TimeRangeType } from '../time-range/utils';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './trend-chart-panel.scss';

export default defineComponent({
  name: 'TrendChartPanel',
  props: {
    /** 面板配置，接口与图表样式全部由外层构造 */
    panel: {
      type: Object as PropType<PanelModel>,
      required: true,
    },
    /** 接口查询参数，汇聚周期由组件内部合并 */
    params: {
      // biome-ignore lint/suspicious/noExplicitAny: 查询参数结构由各页面自定义
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    /** 时间范围，与列表等其它视图同源 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      required: true,
    },
    /** 手动刷新信号 */
    refreshImmediate: {
      type: String,
      default: '',
    },
    /** 时区，未传时沿用上层的注入值 */
    timezone: {
      type: String,
      default: undefined,
    },
    /** 系列数据适配，透传给 ExploreChart */
    customOptions: {
      type: Object as PropType<CustomOptions>,
      default: () => ({}),
    },
    /** 折叠面板标题 */
    title: {
      type: String,
      default: '',
    },
    /** 头部统计的结果数 */
    total: {
      type: Number,
      default: 0,
    },
    /** 外部加载状态，与图表自身加载状态合并后驱动头部骨架 */
    loading: {
      type: Boolean,
      default: false,
    },
    defaultHeight: {
      type: Number,
      default: 166,
    },
    minHeight: {
      type: Number,
      default: 120,
    },
    maxHeight: {
      type: Number,
      default: 360,
    },
  },
  emits: ['dataZoomChange'],
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 先取上层注入值，再覆写，避免未传时区时把上层的时区清空 */
    const inheritedTimezone = inject('timezone', '');
    provide('timeRange', toRef(props, 'timeRange'));
    provide('refreshImmediate', toRef(props, 'refreshImmediate'));
    provide(
      'timezone',
      computed(() => props.timezone ?? toValue(inheritedTimezone))
    );

    /** 汇聚周期，auto 由服务端按时间范围推导 */
    const interval = shallowRef<number | string>('auto');
    const handleIntervalChange = (value: number | string) => {
      interval.value = value;
    };

    /** 图表请求耗时与加载状态，由 ExploreChart 回传 */
    const duration = shallowRef(0);
    const chartLoading = shallowRef(false);
    const summaryLoading = computed(() => props.loading || chartLoading.value);

    /** 汇聚周期是图表的查询参数，统一在此合并，外层无需关心 */
    const chartParams = computed(() => ({ ...props.params, interval: interval.value }));

    return {
      t,
      interval,
      chartParams,
      duration,
      summaryLoading,
      handleIntervalChange,
      handleDurationChange: (value: number) => {
        duration.value = value;
      },
      handleLoadingChange: (value: boolean) => {
        chartLoading.value = value;
      },
      handleDataZoomChange: (value: [number, number]) => {
        emit('dataZoomChange', value);
      },
    };
  },
  render() {
    return (
      <div class='trend-chart-panel'>
        <ChartCollapse
          defaultHeight={this.defaultHeight}
          hasResize={true}
          maxHeight={this.maxHeight}
          minHeight={this.minHeight}
          title={this.title}
        >
          {{
            triggerDescription: () =>
              this.summaryLoading ? (
                <span
                  class='trend-summary-skeleton'
                  aria-hidden='true'
                />
              ) : (
                <i18n-t
                  class='trend-summary'
                  keypath='（找到 {0} 条结果，用时 {1} 毫秒）'
                  tag='span'
                >
                  <span class='count'>{this.total}</span>
                  <span class='duration'>{this.duration}</span>
                </i18n-t>
              ),
            headerCustom: () => (
              <div class='header-custom'>
                <IntervalSelect
                  interval={this.interval}
                  label={this.t('汇聚周期')}
                  onChange={this.handleIntervalChange}
                />
              </div>
            ),
            default: () => (
              <div class='trend-chart-panel-container'>
                <ExploreChart
                  customOptions={this.customOptions}
                  panel={this.panel}
                  params={this.chartParams}
                  retainOnRefresh={true}
                  showTitle={false}
                  onDataZoomChange={this.handleDataZoomChange}
                  onDurationChange={this.handleDurationChange}
                  onLoadingChange={this.handleLoadingChange}
                />
              </div>
            ),
          }}
        </ChartCollapse>
      </div>
    );
  },
});
