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

import { type PropType, computed, defineComponent, onScopeDispose, shallowRef, watch } from 'vue';

import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { useI18n } from 'vue-i18n';

import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import TrendChartPanel from '../../../../components/trend-chart-panel/trend-chart-panel';
import { useRumExploreStore } from '../../../../store/modules/rum-explore';
import { RUM_MODE_TAB_LIST, SPAN_TYPE_FIELD, SPAN_TYPE_META } from '../../constants';
import { getTotal } from '../../services/rum-search';

import type { IRumCommonParams } from '../../typings';

/** time_series 接口返回的系列结构，见接口文档 2.14 */
interface IRumTimeSeriesItem {
  datapoints?: [number, number][];
  dimensions?: Record<string, unknown>;
  unit?: string;
}

interface IRumTimeSeriesResponse {
  query_config?: Record<string, unknown>;
  series?: IRumTimeSeriesItem[];
}

export default defineComponent({
  name: 'RumTrendChart',
  props: {
    /** 当前检索条件，与列表同源；变化时重新统计总数 */
    commonParams: {
      type: Object as PropType<IRumCommonParams>,
      required: true,
    },
  },
  emits: {
    dataZoomChange: (_value: [number, number]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useRumExploreStore();

    /** 检索结果总数，统计耗时由趋势图面板回传 */
    const total = shallowRef(0);
    const totalLoading = shallowRef(false);
    let abortController: AbortController = null;

    async function fetchTotal() {
      if (!props.commonParams?.app_name) {
        abortController?.abort();
        abortController = null;
        total.value = 0;
        totalLoading.value = false;
        return;
      }
      abortController?.abort();
      abortController = new AbortController();
      const { signal } = abortController;
      const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
      totalLoading.value = true;
      const value = await getTotal({ ...props.commonParams, start_time: startTime, end_time: endTime }, { signal });
      // 期间已有新请求触发，丢弃过期结果
      if (signal.aborted) return;
      total.value = value;
      totalLoading.value = false;
    }

    watch(() => [props.commonParams, store.timeRange, store.refreshImmediate], fetchTotal, { immediate: true });

    onScopeDispose(() => abortController?.abort());

    /** 趋势面板：接口按 span_type 分组返回 series，统一渲染为折线 */
    const panel = new PanelModel({
      title: '',
      gridPos: {
        x: 0,
        y: 0,
        w: 24,
        h: 4,
      },
      id: 'rum-trend-chart',
      type: 'graph',
      options: {
        time_series: {
          type: 'line',
        },
      },
      targets: [
        {
          datasource: 'time_series',
          dataType: 'time_series',
          api: 'rum_query.rumTimeSeries',
          data: {
            interval: 'auto',
          },
        },
      ],
    });

    /** 只带检索条件，时间、时区与汇聚周期由趋势图面板补充 */
    const params = computed(() => ({ ...props.commonParams }));

    /** 系列展示名：span 视角取 span_type 元数据；View / Session 视角接口不分组，用视角名 */
    function getSeriesLabel(spanType: string) {
      if (spanType) return SPAN_TYPE_META[spanType]?.label || spanType;
      return RUM_MODE_TAB_LIST.find(item => item.value === store.mode)?.label || store.mode;
    }

    /** 把接口 series 转成图表数据：显式给 alias 并去掉 dimensions，避免系列名被拼上维度值 */
    const formatterData = (res: IRumTimeSeriesResponse) => ({
      series: (res?.series || []).map(item => {
        const spanType = String(item?.dimensions?.[SPAN_TYPE_FIELD] ?? '');
        return {
          datapoints: item?.datapoints || [],
          alias: getSeriesLabel(spanType),
          color: SPAN_TYPE_META[spanType]?.color,
          type: 'line',
          unit: item?.unit,
        };
      }),
      query_config: res?.query_config || {},
      metrics: [],
    });

    /** 系列名取 alias，颜色复用 span 类型主色 */
    const customSeries = series =>
      series.map(item => ({
        ...item,
        name: item.alias || item.name,
        ...(item.color
          ? {
              color: item.color,
              itemStyle: { color: item.color },
              lineStyle: { ...(item.lineStyle || {}), color: item.color },
            }
          : {}),
      }));

    /** 框选区间交给页面写回时间范围，图表自身已在抛事件前复位 */
    const handleDataZoomChange = (value: [number, number]) => {
      emit('dataZoomChange', value);
    };

    return {
      t,
      store,
      panel,
      params,
      total,
      totalLoading,
      formatterData,
      customSeries,
      handleDataZoomChange,
    };
  },
  render() {
    return (
      <TrendChartPanel
        customOptions={{
          formatterData: this.formatterData,
          series: this.customSeries,
        }}
        defaultHeight={173}
        loading={this.totalLoading}
        panel={this.panel}
        params={this.params}
        refreshImmediate={this.store.refreshImmediate}
        timeRange={this.store.timeRange}
        timezone={this.store.timezone}
        title={this.t('总趋势')}
        total={this.total}
        onDataZoomChange={this.handleDataZoomChange}
      />
    );
  },
});
