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

import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils';
import { MONITOR_BAR_OPTIONS, MONITOR_LINE_OPTIONS } from 'monitor-ui/chart-plugins/constants';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from 'monitor-ui/chart-plugins/utils/axis';
import { useI18n } from 'vue-i18n';

import BaseEchart from '../../../plugins/base-echart';
import PageLegend from '../../../plugins/components/page-legend';
import { useChartResize } from '../../../plugins/hooks';
import { formatDurationWithUnit } from '@/components/trace-view/utils/date';

import type { ILegendItem, LegendActionType } from '../../../plugins/typings';
import type { IStatisticsGraph } from '../typing';
import type { MonitorEchartOptions } from 'monitor-ui/chart-plugins/typings';

import './dimension-echarts.scss';

export default defineComponent({
  name: 'DimensionEcharts',
  props: {
    seriesType: {
      type: String as PropType<'histogram' | 'line'>,
      default: 'line',
    },
    isDuration: {
      type: Boolean,
      default: false,
    },
    data: {
      type: Array as PropType<IStatisticsGraph[]>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();
    const chartContainer = shallowRef();
    const width = shallowRef(370);
    const height = shallowRef(136);
    const baseEchartRef = shallowRef();
    const legendList = shallowRef<ILegendItem[]>([]);
    const options = shallowRef<MonitorEchartOptions>({});

    const LegendShowMap = computed(() => {
      return legendList.value.reduce((acc, cur) => {
        acc[cur.name] = cur.show;
        return acc;
      }, {});
    });

    useChartResize(chartContainer, chartContainer, width, height);

    function handleSetFormatterFunc(seriesData: any, onlyBeginEnd = false) {
      let formatterFunc = null;
      const [firstItem] = seriesData;
      const lastItem = seriesData[seriesData.length - 1];
      const val = new Date('2010-01-01').getTime();
      const getXVal = (timeVal: any) => {
        if (!timeVal) return timeVal;
        return timeVal[0] > val ? timeVal[0] : timeVal[1];
      };
      const minX = Array.isArray(firstItem) ? getXVal(firstItem) : getXVal(firstItem?.value);
      const maxX = Array.isArray(lastItem) ? getXVal(lastItem) : getXVal(lastItem?.value);

      minX &&
        maxX &&
        // biome-ignore lint/suspicious/noAssignInExpressions: <explanation>
        (formatterFunc = (v: any) => {
          const duration = Math.abs(dayjs.tz(maxX).diff(dayjs.tz(minX), 'second'));
          if (onlyBeginEnd && v > minX && v < maxX) {
            return '';
          }
          if (duration < 1 * 60) {
            return dayjs.tz(v).format('mm:ss');
          }
          if (duration < 60 * 60 * 24 * 1) {
            return dayjs.tz(v).format('HH:mm');
          }
          if (duration < 60 * 60 * 24 * 6) {
            return dayjs.tz(v).format('MM-DD HH:mm');
          }
          if (duration <= 60 * 60 * 24 * 30 * 12) {
            return dayjs.tz(v).format('MM-DD');
          }
          return dayjs.tz(v).format('YYYY-MM-DD');
        });
      return formatterFunc;
    }

    function customTooltips(params) {
      let name = params[0].axisValue;
      let value = params[0].value[1];
      if (props.isDuration) {
        const nameVal = params[0].name.split('-');
        const [start, end] = nameVal;
        const startLabel = formatDurationWithUnit(Number(start || 0));
        const endLabel = formatDurationWithUnit(Number(end || 0));
        name = `${startLabel} - ${endLabel}`;
        value = params[0].value[1];
      }

      return `<div class="monitor-chart-tooltips">
              <ul class="tooltips-content">
                 <li class="tooltips-content-item" style="--series-color: ${params[0].color}">
                    <span class="item-name" style="color: #fff;font-weight: bold;">${name}:</span>
                    <span class="item-value" style="color: #fff;font-weight: bold;">${value}</span>
                 </li>
              </ul>
              </div>`;
    }

    watch(
      () => props.data,
      value => {
        legendList.value = value.map(item => ({ name: item.name, color: item.color, show: true }));
        setOptions();
      },
      { immediate: true }
    );

    function setOptions() {
      if (props.isDuration) {
        height.value = 81;
        const series: MonitorEchartOptions['series'] = props.data.map(item => ({
          type: 'bar',
          name: '',
          data: item.datapoints.map(point => [point[1], point[0] || null]),
          barMinHeight: 6,
          barCategoryGap: -1,
          color: item.color,
          itemStyle: {
            color: item.color,
          },
        }));

        options.value = deepmerge(
          deepClone(MONITOR_BAR_OPTIONS),
          {
            grid: {
              top: 0,
              left: 0,
              right: 0,
              containLabel: false,
            },
            toolbox: [],
            yAxis: {
              type: 'value',
              show: false,
            },
            xAxis: {
              type: 'category',
              boundaryGap: true,
              show: false,
            },
            tooltip: {
              show: true,
            },
            series,
          },
          { arrayMerge: (_, newArr) => newArr }
        );
      } else if (props.seriesType === 'histogram') {
        const series: MonitorEchartOptions['series'] = props.data.map(item => ({
          type: 'bar',
          name: '',
          data: item.datapoints.map(point => [point[1], point[0]]),
          symbol: 'none',
          z: 6,
          color: item.color,
          itemStyle: {
            color: item.color,
          },
        }));
        options.value = deepmerge(
          deepClone(MONITOR_BAR_OPTIONS),
          {
            xAxis: {
              type: 'category',
              boundaryGap: true,
              axisLabel: {
                showMaxLabel: true,
                showMinLabel: true,
                hideOverlap: true,
              },
            },
            series,
            toolbox: [],
            yAxis: {
              splitLine: {
                lineStyle: {
                  color: '#F0F1F5',
                  type: 'solid',
                },
              },
              splitNumber: 5,
            },
          },
          { arrayMerge: (_, newArr) => newArr }
        );
      } else {
        const { maxSeriesCount, maxXInterval } = getSeriesMaxInterval(props.data);
        const series: MonitorEchartOptions['series'] = props.data
          .map(item => ({
            type: 'line' as const,
            name: item.name,
            data: item.datapoints.map(point => [point[1], point[0]]),
            symbol: 'none',
            z: 6,
            color: item.color,
            lineStyle: {
              color: item.color,
            },
          }))
          .filter(item => LegendShowMap.value[item.name]);
        const xInterval = getTimeSeriesXInterval(maxXInterval, width.value, maxSeriesCount);
        const formatterFunc = handleSetFormatterFunc(series[0]?.data || []);
        options.value = deepmerge(
          deepClone(MONITOR_LINE_OPTIONS),
          {
            xAxis: {
              type: 'time',
              splitNumber: 4,
              axisLabel: {
                formatter: formatterFunc || '{value}',
                hideOverlap: true,
              },
              ...xInterval,
            },
            series,
            toolbox: [],
            yAxis: {
              splitLine: {
                lineStyle: {
                  color: '#F0F1F5',
                  type: 'solid',
                },
              },
              splitNumber: 5,
            },
          },
          { arrayMerge: (_, newArr) => newArr }
        );
      }
    }

    function handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
      let list: ILegendItem[] = deepClone(legendList.value);
      if (actionType === 'click') {
        const hasHidden = list.some(legendItem => !legendItem.show);
        list = list.map(legendItem => {
          if (legendItem.name === item.name) {
            legendItem.show = true;
          } else {
            legendItem.show = hasHidden && item.show;
          }
          return legendItem;
        });
      } else if (actionType === 'shift-click') {
        const result = list.find(legendItem => legendItem.name === item.name);
        result.show = !result.show;
      }
      legendList.value = list;
      setOptions();
    }

    return {
      t,
      chartContainer,
      width,
      height,
      baseEchartRef,
      options,
      LegendShowMap,
      legendList,
      customTooltips,
      handleSelectLegend,
    };
  },
  render() {
    return (
      <div
        ref='chartContainer'
        class={['trace-explore-dimension-echarts-e', { 'has-legend': this.seriesType === 'line' }]}
      >
        <div
          style={{ height: `${this.height}px` }}
          class='event-explore-dimension-echarts-content'
        >
          {this.data.length ? (
            <BaseEchart
              ref='baseEchartRef'
              width={this.width}
              height={this.height}
              customTooltips={this.seriesType === 'histogram' ? this.customTooltips : null}
              options={this.options}
            />
          ) : (
            <div class='empty-chart'>{this.t('查无数据')}</div>
          )}
        </div>

        {this.seriesType === 'line' && (
          <PageLegend
            legendData={this.legendList}
            wrapHeight={40}
            onSelectLegend={this.handleSelectLegend}
          />
        )}
      </div>
    );
  },
});
