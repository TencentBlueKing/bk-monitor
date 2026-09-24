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
import { type PropType, computed, defineComponent, nextTick, shallowRef, watch } from 'vue';

import { dayjs } from '@blueking/date-picker';
import { Button, Exception, Radio } from 'bkui-vue';
import { BarChart, CustomChart, LineChart } from 'echarts/charts';
import {
  BrushComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent,
} from 'echarts/components';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { escape } from 'lodash';
import VueEcharts from 'vue-echarts';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import { formatProfileValue } from '../utils/flame-layout';
import ProfilingSkeleton from './profiling-skeleton';
import { createSeries, createYAxis } from '@/pages/trace-explore/components/explore-chart/use-echarts';

import type { ProfileSeries, SelectionRange } from '../types';
import type { SeriesItem } from '@/pages/trace-explore/components/explore-chart/types';
import type { TooltipComponentOption } from 'echarts';

use([
  LineChart,
  BarChart,
  CustomChart,
  DataZoomComponent,
  ToolboxComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  BrushComponent,
  CanvasRenderer,
]);

export default defineComponent({
  name: 'ProfilingExploreTrend',
  props: {
    series: { type: Array as PropType<ProfileSeries[]>, default: () => [] },
    title: { type: String, default: '' },
    appName: { type: String, default: '' },
    timezone: { type: String, default: '' },
    color: { type: String, default: '#ff9c01' },
    range: { type: Array as unknown as PropType<SelectionRange>, default: null },
    bounds: { type: Array as unknown as PropType<SelectionRange>, default: null },
    defaultRange: { type: Array as unknown as PropType<SelectionRange>, default: null },
    selection: Boolean,
    trace: Boolean,
    collapsed: Boolean,
    legend: { type: Object as PropType<Record<string, boolean>>, default: () => ({}) },
    loading: Boolean,
    error: { type: String, default: '' },
  },
  emits: {
    legendChange: (_legend: Record<string, boolean>) => true,
    collapseChange: (_collapsed: boolean) => true,
    select: (_range: null | SelectionRange) => true,
    traceChange: (_trace: boolean) => true,
    retry: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const router = useRouter();
    const chart = shallowRef<InstanceType<typeof VueEcharts>>();
    const canReset = computed(
      () =>
        !!props.range && !!props.defaultRange && props.range.some((value, index) => value !== props.defaultRange[index])
    );
    const traceItems = shallowRef<{ span_id: string; time: string }[]>([]);
    const prepared = computed(() =>
      createSeries(
        props.series.map(item => ({
          ...item,
          alias: item.alias === '_result_' ? item.dimensions?.device_name || item.target : item.alias || item.target,
          type: props.trace ? 'bar' : 'line',
        })) as SeriesItem[]
      )
    );
    const handleData = (range: null | SelectionRange) => range?.map(time => [time, 0]) || [];
    const formatTooltip: TooltipComponentOption['formatter'] = params => {
      const points = (Array.isArray(params) ? params : [params]).filter(item => item.seriesId !== 'selection-handles');
      if (!points.length) return '';
      // 普通趋势是分类轴的标量值，时间对比是 [毫秒时间, 数值]；两种数据统一为同一提示。
      const first = points[0] as (typeof points)[number] & { axisValue: number | string };
      const time = Number(first.axisValue ?? (Array.isArray(first.value) ? first.value[0] : first.name));
      const rows = points.map(item => {
        const value = Array.isArray(item.value) ? item.value[1] : item.value;
        if (value == null || !Number.isFinite(Number(value))) return '';
        const formatted = formatProfileValue(Number(value), props.series[item.seriesIndex]?.unit);
        // 系列名称来自接口，HTML 提示沿用公共样式时必须转义动态内容。
        return `<li class="tooltips-content-item" style="font-weight:bold">
          <span class="item-series" style="background-color:${escape(String(item.color))}"></span>
          <span class="item-name">${escape(item.seriesName)}:</span>
          <span class="item-value">${escape(formatted)}</span>
        </li>`;
      }).filter(Boolean);
      if (!rows.length) return '';
      const title = dayjs(time).tz(props.timezone).format('YYYY-MM-DD HH:mm:ssZZ');
      return `<div class="monitor-chart-tooltips">
        <p class="tooltips-header">${title}</p>
        <ul class="tooltips-content">${rows.join('')}</ul>
      </div>`;
    };
    const options = computed(() => {
      const { seriesData, xAxis } = prepared.value;
      return {
        animation: false,
        color: [props.color, props.color === '#3a84ff' ? '#ff9c01' : '#3a84ff'],
        grid: { left: 10, right: 16, top: 10, bottom: props.selection ? 10 : 28, containLabel: true },
        tooltip: {
          trigger: 'axis',
          renderMode: 'html',
          confine: true,
          backgroundColor: 'rgba(54,58,67,.88)',
          borderWidth: 0,
          textStyle: { color: '#fff', fontSize: 12 },
          extraCssText: 'border-radius: 4px',
          formatter: formatTooltip,
        },
        legend: {
          selected: props.legend,
          show: !props.selection,
          bottom: 0,
          left: 16,
          icon: 'rect',
          itemWidth: 10,
          itemHeight: 2,
          textStyle: { fontSize: 12, color: '#63656e' },
        },
        // 框选使用连续时间轴，边界可落在采样点之间，不能按分类轴索引截取。
        xAxis: props.selection
          ? [
              {
                type: 'time',
                min: props.bounds?.[0],
                max: props.bounds?.[1],
                axisLine: { lineStyle: { color: '#f0f1f5' } },
                axisTick: { show: false },
                splitLine: { show: false },
                axisLabel: {
                  color: '#979ba5',
                  formatter: (value: number) => dayjs(value).tz(props.timezone).format('HH:mm:ss'),
                },
              },
            ]
          : xAxis.map(axis => ({
              ...axis,
              boundaryGap: props.trace,
              axisLabel: {
                ...axis.axisLabel,
                formatter: (value: string) => dayjs(Number(value)).tz(props.timezone).format('HH:mm:ss'),
              },
            })),
        yAxis: createYAxis(seriesData),
        brush: props.selection
          ? {
              xAxisIndex: 'all',
              seriesIndex: props.series.map((_, index) => index),
              brushLink: 'all',
              brushType: 'lineX',
              brushMode: 'single',
              transformable: true,
              brushStyle: { color: `${props.color}15`, borderColor: props.color, borderWidth: 1, borderType: 'dashed' },
              outOfBrush: { colorAlpha: 0.1 },
              inBrush: { colorAlpha: 1 },
            }
          : undefined,
        toolbox: props.selection
          ? { show: false, feature: { brush: { type: ['lineX', 'clear'] }, dataZoom: {} } }
          : undefined,
        series: props.selection
          ? [
              ...props.series.map((item, index) => ({
                id: `trend-${index}`,
                name: props.title,
                type: 'line',
                data: item.datapoints.map(([value, time]) => [time, value]),
                showSymbol: false,
                lineStyle: { width: 1.2, color: props.color },
                itemStyle: { color: props.color },
              })),
              {
                id: 'selection-handles',
                type: 'custom',
                silent: true,
                tooltip: { show: false },
                z: 100,
                data: handleData(props.range),
                renderItem: (params, api) => ({
                  type: 'rect',
                  shape: {
                    x: api.coord([api.value(0), 0])[0] - 2,
                    y: params.coordSys.y + params.coordSys.height / 2 - 12,
                    width: 4,
                    height: 24,
                    r: 2,
                  },
                  style: { fill: props.color, stroke: '#fff', lineWidth: 1 },
                }),
              },
            ]
          : seriesData,
      };
    });

    let selectionKey = '';
    function showSelection() {
      // 等 ECharts 安装 brush 后再恢复选区；去重避免 rendered → dispatchAction 循环。
      if (!props.selection || !chart.value || !prepared.value.xAxis.length || !chart.value.getOption()?.brush) return;
      const key = JSON.stringify([props.range, prepared.value.xAxis[0].data]);
      if (selectionKey === key) return;
      selectionKey = key;
      chart.value.dispatchAction({
        type: 'takeGlobalCursor',
        key: 'brush',
        brushOption: { brushType: 'lineX', brushMode: 'single' },
      });
      chart.value.dispatchAction({
        type: 'brush',
        areas: props.range ? [{ brushType: 'lineX', xAxisIndex: 0, coordRange: props.range }] : [],
      });
    }

    function handleBrushMove(event: { areas?: { coordRange?: number[] }[] }) {
      // 拖动中只绘制手柄，结束后由 handleBrush 提交查询，避免每个像素都触发请求。
      const range = event.areas?.[0]?.coordRange;
      chart.value?.setOption(
        { series: [{ id: 'selection-handles', data: handleData(range as SelectionRange) }] },
        { silent: true }
      );
    }

    function handleBrush(event: { areas?: { coordRange?: number[] }[] }) {
      const range = event.areas?.[0]?.coordRange;
      if (!range) {
        resetSelection();
        return;
      }
      const [start, end] = range.map(Math.round);
      if (
        Number.isFinite(start) &&
        Number.isFinite(end) &&
        end > start &&
        (start !== props.range?.[0] || end !== props.range?.[1])
      ) {
        emit('select', [start, end]);
      }
    }
    function resetSelection() {
      emit('select', null);
    }

    function handlePoint(event: { dataIndex?: number | number[]; seriesIndex?: number }) {
      if (!props.trace || typeof event.seriesIndex !== 'number' || typeof event.dataIndex !== 'number') return;
      const series = props.series[event.seriesIndex];
      const time = prepared.value.seriesData[event.seriesIndex]?.alignedDatapoints?.[event.dataIndex]?.[1];
      traceItems.value = series?.trace_data?.[String(time)] || [];
    }

    function traceHref(spanId: string) {
      return router.resolve({
        name: 'home',
        query: {
          app_name: props.appName,
          ...(props.bounds
            ? {
                start_time: dayjs(props.bounds[0]).tz(props.timezone).format('YYYY-MM-DD HH:mm:ssZZ'),
                end_time: dayjs(props.bounds[1]).tz(props.timezone).format('YYYY-MM-DD HH:mm:ssZZ'),
              }
            : {}),
          timezone: props.timezone,
          where: JSON.stringify([{ key: 'span_id', operator: 'equal', value: [spanId] }]),
          filterMode: 'ui',
          sceneMode: 'span',
        },
      }).href;
    }
    watch(
      () => [props.range, props.series, props.selection, chart.value],
      () => {
        traceItems.value = [];
        selectionKey = '';
        nextTick(showSelection);
      }
    );
    return {
      t,
      chart,
      canReset,
      traceItems,
      options,
      showSelection,
      handleBrush,
      handleBrushMove,
      handlePoint,
      traceHref,
      resetSelection,
    };
  },
  render() {
    return (
      <section class={['profiling-trend', { collapsed: this.collapsed }]}>
        <div class='profiling-trend-toolbar'>
          {this.selection ? (
            <>
              <strong>{this.title}</strong>
              {this.canReset && (
                <Button
                  theme='primary'
                  text
                  onClick={this.resetSelection}
                >
                  {this.t('重置')}
                </Button>
              )}
            </>
          ) : (
            <>
              <Button
                aria-label={this.t(this.collapsed ? '展开' : '收起')}
                text
                onClick={() => {
                  this.$emit('collapseChange', !this.collapsed);
                }}
              >
                <i
                  class={`icon-monitor ${this.collapsed ? 'icon-mc-triangle-down' : 'icon-mc-triangle-down expanded'}`}
                />
              </Button>
              <Radio.Group
                modelValue={this.trace ? 'trace' : 'trend'}
                type='capsule'
                onChange={value => this.$emit('traceChange', value === 'trace')}
              >
                <Radio.Button label='trend'>{this.t('总趋势')}</Radio.Button>
                <Radio.Button label='trace'>{this.t('Trace 数据')}</Radio.Button>
              </Radio.Group>
            </>
          )}
        </div>
        {!this.collapsed && (
          <div
            class='profiling-trend-chart'
            aria-busy={this.loading}
          >
            {this.loading ? (
              <ProfilingSkeleton variant='trend' />
            ) : this.error ? (
              <div class='profiling-inline-error'>
                {this.error}
                <Button
                  theme='primary'
                  text
                  onClick={() => this.$emit('retry')}
                >
                  {this.t('重试')}
                </Button>
              </div>
            ) : !this.series.some(item => item.datapoints.length) ? (
              <Exception
                description={this.t('暂无数据')}
                scene='part'
                type='empty'
              />
            ) : (
              <VueEcharts
                ref='chart'
                option={this.options}
                updateOptions={{ notMerge: true }}
                autoresize
                onBrush={this.handleBrushMove}
                onBrushEnd={this.handleBrush}
                onClick={this.handlePoint}
                onFinished={() => nextTick(this.showSelection)}
                onLegendselectchanged={event => this.$emit('legendChange', event.selected)}
              />
            )}
          </div>
        )}
        {!!this.traceItems.length && (
          <div class='profiling-trace-points'>
            <Button
              text
              onClick={() => {
                this.traceItems = [];
              }}
            >
              {this.t('关闭')}
            </Button>
            {this.traceItems.map(item => (
              <div key={item.span_id}>
                <span>{item.time}</span>
                <a
                  href={this.traceHref(item.span_id)}
                  rel='noopener noreferrer'
                  target='_blank'
                >
                  {item.span_id}
                </a>
              </div>
            ))}
          </div>
        )}
      </section>
    );
  },
});
