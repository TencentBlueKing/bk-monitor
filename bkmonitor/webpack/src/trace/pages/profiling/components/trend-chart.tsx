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
import { type PropType, type Ref, computed, defineComponent, inject, provide, ref, watch } from 'vue';

import { Collapse, Radio } from 'bkui-vue';
import { random } from 'monitor-common/utils/utils';
import { getDefaultTimezone } from 'monitor-pc/i18n/dayjs';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import { setTraceTooltip } from 'monitor-ui/chart-plugins/plugins/profiling-graph/trace-chart/util';
import { useI18n } from 'vue-i18n';

import TimeSeries from '../../../plugins/charts/time-series/time-series';
import {
  REFRESH_IMMEDIATE_KEY,
  REFRESH_INTERVAL_KEY,
  TIME_OFFSET_KEY,
  TIME_RANGE_KEY,
  TIMEZONE_KEY,
  VIEW_OPTIONS_KEY,
} from '../../../plugins/hooks';
import { PanelModel } from '../../../plugins/typings';
import { type ToolsFormData, SearchType } from '../typings';

import type { IQueryParams } from '../../../typings/trace';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './trend-chart.scss';
import 'monitor-ui/chart-plugins/plugins/profiling-graph/trace-chart/trace-chart.scss';

const DEFAULT_PANEL_CONFIG = {
  title: '',
  gridPos: {
    x: 16,
    y: 16,
    w: 8,
    h: 4,
  },
  type: 'graph',
  targets: [],
};

export default defineComponent({
  name: 'TrendChart',
  props: {
    content: {
      type: String,
      default: '',
    },
    comparisonDate: {
      type: Array as PropType<[number, number][]>,
      default: () => [],
    },
    queryParams: {
      type: Object as PropType<IQueryParams>,
      default: () => ({}),
    },
  },
  emits: ['chartData', 'loading'],
  setup(props, { emit }) {
    const toolsFormData = inject<Ref<ToolsFormData>>('toolsFormData');
    const searchType = inject<Ref<SearchType>>('profilingSearchType', undefined);
    const timeSeriesChartRef = ref();

    const timezone = ref<string>(getDefaultTimezone());
    const refreshImmediate = ref<number | string>('');
    const defaultViewOptions = ref<IViewOptions>({});
    const collapse = ref(true);
    const panel = ref<PanelModel>(null);
    const chartType = ref('all');
    const loading = ref(false);
    const chartRef = ref<Element>();
    const chartData = ref([]);

    const timeRange = computed(() => toolsFormData.value.timeRange);
    const refreshInterval = computed(() => toolsFormData.value.refreshInterval);
    const chartCustomTooltip = computed(() => {
      if (chartType.value === 'all') return {};

      const appName = (props.queryParams as IQueryParams)?.app_name ?? '';
      return setTraceTooltip(chartRef.value, appName);
    });

    const { t } = useI18n();

    provide(TIME_RANGE_KEY, timeRange);
    provide(TIMEZONE_KEY, timezone);
    provide(REFRESH_INTERVAL_KEY, refreshInterval);
    provide(REFRESH_IMMEDIATE_KEY, refreshImmediate);
    provide(VIEW_OPTIONS_KEY, defaultViewOptions);
    provide(TIME_OFFSET_KEY, ref([]));

    watch(
      () => [props.queryParams, chartType.value],
      () => {
        const { start, end, ...rest } = props.queryParams as IQueryParams;
        const allTrend = chartType.value === 'all'; // 根据类型构造图表配置
        const type = allTrend ? 'line' : 'bar';
        const targetApi = allTrend ? 'apm_profile.query' : 'apm_profile.queryProfileBarGraph';
        // if (JSON.stringify(newVal) === JSON.stringify(oldVal)) return;
        const targetData = {
          ...rest,
          ...(allTrend ? { diagram_types: ['tendency'] } : {}),
          /** 上传文件查询 时间参数通过选中文件信息的时间范围查询 */
          /** 文件信息的时间单位为 μs（微秒），图表插件需要统一单位为 s（秒），故在此做转换 */
          ...(searchType.value === SearchType.Upload
            ? {
                start_time: Number.parseInt(String(start / 10 ** 6), 10),
                end_time: Number.parseInt(String(end / 10 ** 6), 10),
              }
            : {}),
        };

        panel.value = new PanelModel({
          ...DEFAULT_PANEL_CONFIG,
          id: random(6),
          options: { time_series: { type } },
          targets: [
            {
              api: targetApi,
              datasource: 'time_series',
              alias: '',
              data: targetData,
            },
          ],
        });
      },
      {
        immediate: true,
        deep: true,
      }
    );

    watch(props.comparisonDate, () => {
      handleSetMarkArea();
    });

    function handleCollapseChange(v) {
      collapse.value = v;
    }

    function handleSetMarkArea() {
      const { series, ...params } = timeSeriesChartRef.value.options;
      timeSeriesChartRef.value.setOptions({
        ...params,
        series: series.map((item, ind) => ({
          ...item,
          markArea: {
            show: !!props.comparisonDate[ind]?.length,
            itemStyle: {
              color: ['rgba(58, 132, 255, 0.1)', 'rgba(255, 86, 86, 0.1)'][ind],
            },
            data: [
              [
                {
                  xAxis: props.comparisonDate[ind]?.[0] || 0,
                },
                {
                  xAxis: props.comparisonDate[ind]?.[1] || 0,
                },
              ],
            ],
          },
        })),
      });
    }

    function handleChartData(data) {
      chartData.value = data;
      emit('chartData', data);
    }

    function handleLoading(v) {
      loading.value = v;
      emit('loading', v);
    }

    return {
      chartRef,
      timeSeriesChartRef,
      chartType,
      panel,
      collapse,
      handleCollapseChange,
      loading,
      chartCustomTooltip,
      handleChartData,
      handleLoading,
      t,
    };
  },
  render() {
    return (
      <div class='trend-chart'>
        <Collapse.CollapsePanel
          v-slots={{
            content: () => (
              <div
                ref='chartRef'
                class='trend-chart-wrap'
              >
                {this.collapse && this.panel && (
                  <TimeSeries
                    key={this.chartType}
                    ref='timeSeriesChartRef'
                    customTooltip={this.chartCustomTooltip}
                    panel={this.panel}
                    showChartHeader={false}
                    showHeaderMoreTool={false}
                    onChartData={this.handleChartData}
                    onLoading={this.handleLoading}
                  />
                )}
              </div>
            ),
          }}
          modelValue={this.collapse}
          onUpdate:modelValue={this.handleCollapseChange}
        >
          <div
            class='trend-chart-header'
            onClick={e => e.stopPropagation()}
          >
            <Radio.Group
              v-model={this.chartType}
              type='capsule'
            >
              <Radio.Button label='all'>{this.t('总趋势')}</Radio.Button>
              <Radio.Button label='trace'>{this.t('Trace 数据')}</Radio.Button>
            </Radio.Group>
            {this.loading ? (
              <img
                class='chart-loading-icon'
                alt='loading'
                src={loadingIcon}
              />
            ) : undefined}
          </div>
        </Collapse.CollapsePanel>
      </div>
    );
  },
});
