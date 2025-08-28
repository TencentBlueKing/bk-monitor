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
import {
  type PropType,
  computed,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from 'vue';

import dayjs from 'dayjs';
import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import { handleYAxisLabelFormatter, removeTrailingZeros } from '../../utils';

import type { IMetricItem, MetricEvent } from '../../types';

const baseLineSeriesConfig = {
  type: 'line',
  connectNulls: true,
  yAxisIndex: 0,
  lineStyle: { width: 2 },
  showSymbol: false,
  markPoint: {
    symbol: 'circle',
    symbolSize: 7,
    itemStyle: {
      color: '#EA3636',
      borderColor: '#ea363652',
      borderWidth: 5,
    },
    label: { show: false },
  },
};

export default defineComponent({
  name: 'MetricChart',
  props: {
    // 指标数据项
    metricItem: {
      type: Object as PropType<IMetricItem>,
      required: true,
    },
    // 图表在列表中的索引
    index: {
      type: Number,
      required: true,
    },
    showEventAnalyze: {
      type: Boolean,
      required: true,
    },
    eventsData: {
      type: Array as PropType<MetricEvent[]>,
      default: () => [],
    },
    isNodeView: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['init', 'destroy', 'eventClick'],
  setup(props, { emit }) {
    const chartDomRef = shallowRef<HTMLDivElement | null>(null);
    const chart = shallowRef<echarts.ECharts | null>(null);
    // 图表是否在可视区域
    const isChartVisible = ref(true);
    let observer: IntersectionObserver | null = null;
    // 是否为多维度指标数据
    const isMultiDimension = shallowRef(Object.keys(props.metricItem.time_series).length > 1);
    // 指标数据
    const seriesList = ref(Object.values(props.metricItem.time_series));
    // 指标数据名称集合
    const dimensionNameList = computed(() => Object.keys(props.metricItem.time_series));

    /** 隐藏tooltip */
    const forceHideTooltip = () => {
      if (!chart.value) return;
      try {
        const tooltipEl = chart.value.getDom().querySelector('.echarts-tooltip');
        if (tooltipEl) {
          (tooltipEl as HTMLElement).style.display = 'none';
        }
      } catch (e) {
        console.error('Hide tooltip failed:', e);
      }
    };

    /** 监听图表是否在可视区域内 */
    const initVisibilityListener = () => {
      if (!chartDomRef.value || typeof IntersectionObserver === 'undefined') return;

      observer = new IntersectionObserver(
        entries => {
          const isVisible = entries.some(entry => entry.isIntersecting && entry.intersectionRatio > 0.1);
          isChartVisible.value = isVisible;
          if (!isVisible) {
            // 图表不可见时强制隐藏tooltip
            forceHideTooltip();
          }

          // 更新图表状态
          renderChart();
          updateEventAnalyze();
        },
        {
          root: null,
          threshold: [0.5, 1],
          rootMargin: '0px 0px -30px 0px',
        }
      );

      observer.observe(chartDomRef.value);
    };

    /** 初始化图表 */
    const initChart = () => {
      if (!chartDomRef.value) return;

      chart.value = echarts.init(chartDomRef.value);
      renderChart();

      // 初始化可视区域监听
      initVisibilityListener();
    };

    /** 生成ECharts系列数据 */
    const getSeriesData = (data: Array<[number, number, number]>) => {
      return data.map(entry => ({
        value: [entry[0], entry[1], entry[2]],
        symbol: 'circle',
        symbolSize: 7,
      }));
    };

    /** 计算图表网格布局*/
    const getGridOptions = () => {
      return {
        left: '2%',
        right: '2%',
        top: '10%',
        bottom: isMultiDimension.value ? '25' : '0',
        containLabel: true,
      };
    };

    /** 动态单位转换 */
    const unitFormatter = !['', 'none', undefined, null].includes(seriesList.value[0]?.unit)
      ? getValueFormat(seriesList.value[0].unit)
      : (v: any) => ({ text: v, suffix: '' });

    const getTooltipFormatter = (params: any) => {
      if (!params?.length) return '';
      const time = dayjs.tz(params[0].value[0]).format('YYYY-MM-DD HH:mm:ss');
      let html = `<div style='color:rgb(241, 243, 250);font-weight:700;line-height:1;margin-bottom:6px;'>${time}</div>`;

      for (const item of params) {
        let color = item.color;
        // 异常点特殊处理
        if (item.seriesId.includes('line') && item.value?.[2] > 0) {
          color = '#EA3636';
        }
        // 事件系列特殊颜色
        if (item.seriesId === 'scatter-event') {
          color = '#55D3F0';
        }
        // 带单位转换后的数据，精确度precision默认为2
        const valueObj = unitFormatter(item.value[1], 2);

        const itemValue =
          item.seriesId === 'scatter-event' ? item.value[1] : `${valueObj?.text} ${valueObj?.suffix || ''}`;
        html += `<div class='metric-chart-tooltip'>
                  <span style='display:flex;align-items:center;'>
                    <span class='item-circle' style='background-color:${color};'></span>
                    <span class='item-name'>${item.seriesName}:</span>
                  </span>
                  <span class='item-value' style='font-weight:700;'>${itemValue}</span>
                </div>`;
      }
      return `<div style='color:#fff;font-size:12px;'>${html}</div>`;
    };

    /** 创建折线series */
    const getLineSeries = () => {
      // 创建标记点markPoint
      const createMarkPoints = (data: Array<[number, number, number]>) =>
        data.filter(entry => entry[2] > 0).map(entry => ({ coord: [entry[0], entry[1]], name: '异常点' }));

      // 创建单条线配置
      const createLineSeries = (name: string, dataSource: Array<[number, number, number]>) => ({
        ...baseLineSeriesConfig,
        name,
        id: `line-${name}`,
        data: getSeriesData(dataSource),
        markPoint: {
          ...baseLineSeriesConfig.markPoint,
          data: createMarkPoints(dataSource),
        },
      });

      // 单维度数据处理，仅展示一条折线
      if (!props.metricItem.display_by_dimensions) {
        return [createLineSeries(props.metricItem.metric_name, props.metricItem.time_series.default.datapoints)];
      }

      // 多维度数据处理，展示多条折线
      return Object.entries(props.metricItem.time_series).map(([key, value]) =>
        createLineSeries(key, value.datapoints as Array<[number, number, number]>)
      );
    };

    /** 渲染图表 */
    const renderChart = () => {
      if (!chart.value) return;
      const option: echarts.EChartsCoreOption = {
        color: COLOR_LIST,
        grid: getGridOptions(),
        legend: {
          show: isMultiDimension.value,
          type: 'plain',
          icon: 'roundRect',
          data: dimensionNameList.value,
          itemWidth: 16,
          itemHeight: 9,
          left: 0,
          bottom: 0,
          textStyle: {
            width: 100,
            color: '#c4c6cc',
            overflow: 'truncate',
          },
        },
        tooltip: {
          trigger: 'axis',
          appendToBody: true,
          backgroundColor: 'rgba(54, 58, 67, 0.88)',
          borderWidth: 0,
          padding: 10,
          textStyle: { fontSize: 12, color: '#fff' },
          show: isChartVisible.value,
          formatter: params => getTooltipFormatter(params),
        },
        xAxis: {
          type: 'time',
          minInterval: 20 * 1000,
          splitNumber: 4,
          axisLabel: {
            align: 'right',
            hideOverlap: true,
            margin: 10,
            formatter(value: number) {
              return dayjs.tz(value).format('HH:mm');
            },
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            lineStyle: {
              color: '#979BA5',
            },
          },
        },
        yAxis: [
          {
            type: 'value',
            splitNumber: 3,
            axisLabel: {
              color: '#979BA5',
              formatter: seriesList.value.every((item: any) => item.unit === seriesList.value[0].unit)
                ? (v: any) => {
                    if (seriesList.value[0].unit && seriesList.value[0].unit !== 'none') {
                      // 精确度precision默认为2
                      const obj = getValueFormat(seriesList.value[0].unit)(v, 2);
                      return removeTrailingZeros(obj.text) + obj.suffix;
                    }
                    return v;
                  }
                : (v: number) => handleYAxisLabelFormatter(v),
            },
            // axisTick: {
            //   length: 3,
            // },
            splitLine: {
              lineStyle: {
                type: 'solid',
                color: '#63656E',
              },
            },
          },
        ],
        series: getLineSeries(),
      };
      chart.value.setOption(option, { replaceMerge: ['series'] });

      nextTick(() => {
        // 向父组件传递图表实例用于联动
        emit('init', chart.value);
      });
    };

    /** 统一处理事件分析显示 */
    const updateEventAnalyze = () => {
      // 边概览不需要事件分析相关功能
      if (!props.isNodeView) return;

      if (props.showEventAnalyze && props.eventsData.length > 0) {
        updateScatterChart();
        setupEventListeners();
      } else {
        removeScatterChart();
      }
    };

    /** 添加/更新散点图 */
    const updateScatterChart = () => {
      if (!chart.value) return;

      const option = chart.value.getOption() as any;
      // 清除旧的事件散点图
      const filteredSeries = option.series.filter((s: any) => s.id !== 'scatter-event');
      // 添加散点图series
      const scatterSeries = {
        type: 'scatter',
        name: '事件数',
        id: 'scatter-event',
        data: props.eventsData,
        yAxisIndex: 1,
        z: 1000,
        zlevel: 1000,
        symbolSize: (data: any) => {
          const size = data[2] || 12;
          return Math.min(Math.max(size * 1.8, 12), 29);
        },
        itemStyle: { color: '#55D3F0', opacity: 0.36 },
        emphasis: { scale: 1.666, itemStyle: { opacity: 0.8 } },
      };
      // 保留原左轴，添加右侧Y轴
      const rightAxis = {
        scale: true,
        show: true,
        position: 'right',
        max: 'dataMax',
        min: 0,
        minInterval: 1,
        splitLine: false,
        splitNumber: 2,
        axisLabel: { color: '#979BA5' },
      };

      chart.value.setOption(
        {
          series: [...filteredSeries, scatterSeries],
          yAxis: [...(option.yAxis || []).filter((y: any) => y.position !== 'right'), rightAxis],
        },
        // 替换yAxis和series
        { replaceMerge: ['yAxis', 'series'] }
      );
    };

    /** 移除散点图 */
    const removeScatterChart = () => {
      if (!chart.value) return;

      const option = chart.value.getOption() as any;
      // 过滤掉散点图系列
      const filteredSeries = option.series.filter((s: any) => s.id !== 'scatter-event');
      // 移除右侧Y轴，保留原左轴
      const filteredYAxis = (option.yAxis || []).filter((y: any) => y.position !== 'right');

      chart.value.setOption(
        {
          series: filteredSeries,
          yAxis: filteredYAxis,
        },
        { replaceMerge: ['yAxis', 'series'] }
      );
    };

    /** 添加事件监听 */
    const setupEventListeners = () => {
      if (!chart.value) return;

      // 移除旧监听避免重复
      chart.value.off('click');
      chart.value.on('click', { seriesId: 'scatter-event' }, params => {
        emit('eventClick', params);
      });
    };

    // 监听数据变化
    watch(
      () => props.metricItem,
      () => {
        if (chart.value) {
          // 重用实例更新数据
          renderChart();
        } else {
          initChart();
        }
      },
      { deep: true }
    );

    watch(
      [() => props.showEventAnalyze, () => props.eventsData],
      () => {
        updateEventAnalyze();
      },
      { deep: true }
    );

    // 窗口大小变化时重绘图表
    const handleResize = () => chart.value?.resize();
    window.addEventListener('resize', handleResize);

    onMounted(() => {
      initChart();
    });

    onBeforeUnmount(() => {
      if (chart.value) {
        emit('destroy', chart.value);
        chart.value.dispose();
        chart.value = null;
      }
      if (observer) observer.disconnect();
      window.removeEventListener('resize', handleResize);
    });

    return {
      chartDomRef,
      isMultiDimension,
    };
  },
  render() {
    return (
      <>
        <div
          class={['chart-wrap_title', this.index === 0 && 'chart-wrap_title-first']}
          v-overflow-tips={{
            text: this.metricItem.metric_alias,
            placement: 'top',
          }}
        >
          {this.metricItem.metric_alias}
        </div>
        <div
          ref='chartDomRef'
          style={{ width: '316px', height: this.isMultiDimension ? '150px' : '118px' }}
        />
      </>
    );
  },
});
