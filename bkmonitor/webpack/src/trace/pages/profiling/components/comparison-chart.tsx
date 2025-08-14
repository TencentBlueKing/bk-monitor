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
import { type PropType, defineComponent, nextTick, ref, shallowRef, watch } from 'vue';

import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';
import { useI18n } from 'vue-i18n';

import BaseEchart from '../../../plugins/base-echart';
import { useChartResize } from '../../../plugins/hooks';
import { Toolbox } from '../../../plugins/typings';

import './comparison-chart.scss';

export default defineComponent({
  name: 'ComparisonChart',
  props: {
    data: {
      type: Object,
      default: () => null,
    },
    comparisonDate: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
    title: {
      type: String,
      default: '',
    },
    colorIndex: {
      type: Number,
      default: 0,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['brushEnd'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const baseEchart = ref(null);
    const chartContainer = ref<HTMLDivElement>(null);
    const width = ref(300);
    const height = ref(100);
    // 监听resize
    const { handleResize } = useChartResize(chartContainer, chartContainer, width, height);
    const options = ref({});
    const defaultOptions = {
      animation: false,
      xAxis: [
        {
          type: 'time',
          axisLine: {
            lineStyle: {
              color: '#F0F1F5',
            },
          },
          axisLabel: {
            color: '#979BA5',
          },
          axisTick: {
            show: false,
          },
          splitLine: {
            show: false,
          },
        },
      ],
      yAxis: {
        type: 'value',
        axisTick: {
          show: false,
        },
        axisLabel: {
          formatter: (v: any) => {
            if (props.data.unit !== 'none') {
              const obj = getValueFormat(props.data.unit)(v, 0);
              return obj.text + (obj.suffix || '');
            }
            return v;
          },
        },
        splitNumber: 2,
        minInterval: 1,
        position: 'left',
      },
      toolbox: {
        showTitle: false,
        itemSize: 0,
        feature: {
          brush: {},
        },
      },
      brush: {
        xAxisIndex: 'all',
        brushLink: 'all',
        toolbox: ['lineX', 'clear'],
        brushStyle: {
          borderType: 'dashed',
          color: ['rgba(58, 132, 255, 0.1)', 'rgba(255, 86, 86, 0.1)'][props.colorIndex],
        },
        outOfBrush: {
          colorAlpha: 0.1,
        },
      },
      series: [],
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(54,58,67,.88)',
        borderWidth: 0,
      },
      grid: {
        left: 16,
        top: 10,
        right: 40,
        bottom: 10,
        containLabel: true,
      },
    };
    const brushCoordRange = shallowRef<number[]>([]);
    const getSeriesData = (isCustom = false) => {
      if (!props.data?.datapoints?.length) return [];
      const data = props.data.datapoints.map(item => [item[1], item[0]]);
      if (!isCustom) return data;
      const customData = [];
      const [start, end] = brushCoordRange.value;
      for (let i = 0, len = data.length; i < len; i++) {
        const [time] = data[i];
        if (i === 0 || i === len - 1) {
          if (start < time || start > time) {
            customData.push([start, 1]);
          }
          if (end < time || end > time) {
            customData.push([end, 1]);
          }
          customData.push([time, null]);
          continue;
        }
        customData.push([time, null]);
        if (!brushCoordRange.value.length) continue;
        const [preTime] = data[i - 1];
        const [nextTime] = data[i + 1];
        if (start >= preTime && start <= time) {
          customData.push([start, 1]);
          continue;
        }
        if (end >= time && end <= nextTime) {
          customData.push([end, 1]);
        }
      }
      return customData;
    };

    watch(
      () => props.data,
      () => {
        setOptions();
      },
      { immediate: true }
    );

    watch(
      () => props.comparisonDate,
      val => {
        brushCoordRange.value = val;
        setOptions();
      },
      {
        immediate: true,
      }
    );

    function setOptions(hasSetChartBrush = true) {
      if (!props.data) return;
      options.value = {
        ...defaultOptions,
        yAxis: {
          type: 'value',
          axisTick: {
            show: false,
          },
          axisLabel: {
            formatter: (v: any) => {
              if (props.data.unit !== 'none') {
                const obj = getValueFormat(props.data.unit)(v, 0);
                return obj.text + (obj.suffix || '');
              }
              return v;
            },
          },
          splitNumber: 2,
          minInterval: 1,
          position: 'left',
        },
        brush: {
          xAxisIndex: 'all',
          brushLink: 'all',
          toolbox: ['lineX', 'clear'],
          brushStyle: {
            borderType: 'dashed',
            color: ['rgba(58, 132, 255, 0.1)', 'rgba(255, 86, 86, 0.1)'][props.colorIndex],
          },
          outOfBrush: {
            colorAlpha: 0.1,
          },
        },
        series: [
          {
            name: props.title,
            type: 'line',
            data: getSeriesData(false),
            lineStyle: {
              color: ['#3A84FF', '#EA3636'][props.colorIndex],
            },
            showSymbol: false,
            unitFormatter:
              props.data.unit !== 'none' ? getValueFormat(props.data.unit || '') : (v: any) => ({ text: v }),
            precision: 2,
          },
          {
            type: 'custom',
            renderItem: (param, api) => {
              if (Number.isNaN(api.value(1))) return;
              const isStart = brushCoordRange.value[0] >= api.value(0);
              const point = api.coord([api.value(0), api.value(1)]);
              return {
                type: 'path',
                shape: {
                  pathData: 'M 1,0A 1,1 0 0,1 3,0L 3,50A 1,1 0 0,1 1,50L 1,0',
                  x: isStart ? -1.5 : -1.5,
                  y: -35,
                  width: 4,
                  height: 24,
                },
                position: point,
                style: api.style({
                  stroke: ['#699DF4', '#FE8A8A'][props.colorIndex],
                  lineWidth: 3,
                }),
              };
            },
            tooltip: {
              show: false,
            },
            data: getSeriesData(true),
            z: 100000,
            silent: true,
          },
        ],
      };
      if (hasSetChartBrush) {
        nextTick(() => {
          setChartBrush();
        });
      }
    }

    /** 设置图表框选区域 */
    function setChartBrush() {
      baseEchart.value?.dispatchAction({
        type: 'brush',
        areas: brushCoordRange.value.length
          ? [
              {
                brushType: 'lineX',
                xAxisIndex: 0,
                coordRange: brushCoordRange.value,
              },
            ]
          : [],
      });
    }

    function handleBrushEnd(data) {
      const coordRange = data.areas?.[0]?.coordRange || [];
      if (coordRange.length) {
        brushCoordRange.value = data.areas?.[0]?.coordRange || [];
        emit('brushEnd', brushCoordRange.value);
      }
    }
    function handleBrush(data) {
      const coordRange = data.areas?.[0]?.coordRange || [];
      if (coordRange.length) {
        brushCoordRange.value = data.areas?.[0]?.coordRange || [];
      }
      setOptions(!coordRange.length);
    }

    return {
      t,
      baseEchart,
      chartContainer,
      height,
      width,
      options,
      setChartBrush,
      handleBrushEnd,
      handleBrush,
      handleResize,
    };
  },
  render() {
    return (
      <div
        ref='chartContainer'
        class='comparison-chart-card'
      >
        <div class='title'>
          {this.title}
          {this.loading && (
            <img
              class='chart-loading-icon'
              alt='loading'
              src={loadingIcon}
            />
          )}
        </div>
        <div class='chart-wrap'>
          {this.data ? (
            <BaseEchart
              ref='baseEchart'
              width={this.width}
              height={this.height}
              notMerge={false}
              options={this.options}
              toolbox={[Toolbox.Brush, Toolbox.DataZoom]}
              onBrush={this.handleBrush}
              onBrushEnd={this.handleBrushEnd}
              onLoaded={this.setChartBrush}
            />
          ) : (
            <div class='empty-chart'>{this.t('查无数据')}</div>
          )}
        </div>
      </div>
    );
  },
});
