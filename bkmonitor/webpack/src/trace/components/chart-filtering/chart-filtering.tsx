/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { computed, defineComponent, ref, watch } from 'vue';

import { Slider } from 'bkui-vue';
import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils';

import { useTraceStore } from '../../store/modules/trace';
import { formatDuration } from '../trace-view/utils/date';
import BarChart from './bar-chart';
import { BASE_BAR_OPTIONS, DURATION_AVERAGE_COUNT, DurationDataModal } from './utils';

import type { MonitorEchartOptions } from 'monitor-ui/chart-plugins/typings';

import './chart-filtering.scss';

export interface ISliderItem {
  overallText?: string;
  curValText?: string;
  curValue: number[];
  scaleRange: number[];
  min: number;
  max: number;
  step: number;
  disable?: boolean;
}

export default defineComponent({
  name: 'ChartFiltering',
  setup() {
    const store = useTraceStore();

    /** 耗时图表 */
    const barChartref = ref<HTMLDivElement>();
    /** 耗时图表配置 */
    const chartOptions = ref<MonitorEchartOptions | null>(null);
    /** 耗时 modal */
    const durationModal = ref<DurationDataModal | null>(null);
    /** 耗时范围选择信息 */
    const durationSlider = ref<ISliderItem>({
      overallText: '', // 全范围文案
      curValText: '', // 当前选择范围文案
      curValue: [0, 0], // 当前选择范围
      scaleRange: [0, DURATION_AVERAGE_COUNT], // 刻度范围
      min: 0, // 最小值
      max: 0, // 最大值
      step: 0, // 步长 / 刻度
    });

    /** trace列表数据 */
    const listData = computed(() => (store.listType === 'trace' ? store.traceList : store.spanList));

    /** 设置滑动选择器状态 */
    const handleSetDurationSlider = (min: number, max: number, step: number) => {
      const defaultText = `${formatDuration(min)} - ${formatDuration(max)}`;
      const sliderOptions: ISliderItem = {
        overallText: defaultText,
        curValText: defaultText,
        curValue: [min, max],
        scaleRange: [0, DURATION_AVERAGE_COUNT],
        min,
        max,
        step,
      };

      if (store.filterTraceList.length) {
        // 说明此前已通过滑动选择器过滤且当前范围不在两端
        // 刻度列是固定的 刻度值会根据大小变化 当数据发生变化 保留当前刻度比例范围 重置选中值即可
        const [scaleStart, scaleEnd] = durationSlider.value.scaleRange;
        const curStart = Math.floor(scaleStart ? scaleStart * step : min);
        const curEnd = Math.floor(scaleEnd * step);
        sliderOptions.scaleRange = [scaleStart, scaleEnd];
        sliderOptions.curValue = [curStart, curEnd];
        sliderOptions.curValText = `${formatDuration(curStart)} - ${formatDuration(curEnd)}`;
        handleFilterTraceList();
      }

      durationSlider.value = sliderOptions;
    };
    /** 初始化图表数据 */
    const initData = () => {
      if (listData.value.length) {
        durationModal.value = new DurationDataModal(listData.value);
        const { minDuration, maxDuration, durationStep, xAxisData, seriesData } = durationModal.value;

        const echartOptions = deepmerge(deepClone(BASE_BAR_OPTIONS), {});
        chartOptions.value = Object.freeze(
          deepmerge(echartOptions, {
            xAxis: { data: xAxisData },
            tooltip: {
              show: true,
              formatter: (params: any) => {
                const nameVal = params.name.split('-');
                const [start, end] = nameVal;
                const startLabel = formatDuration(Number(start || 0));
                const endLabel = formatDuration(Number(end || 0));
                return `${startLabel} - ${endLabel} : ${params.value}`;
              },
            },
            series: {
              data: seriesData,
              type: 'bar',
              barMinHeight: 6,
              barCategoryGap: -1,
              itemStyle: {
                normal: {
                  color: (params: any) => formatterDurationFunc(params, xAxisData),
                },
              },
            },
          })
        ) as MonitorEchartOptions;
        handleSetDurationSlider(minDuration, maxDuration, durationStep);
      } else {
        durationModal.value = null;
        chartOptions.value = null;
      }
    };

    watch(() => listData.value, initData, { immediate: true });

    /** 耗时滑动选择器选择 */
    const handleDurationChange = (val: number[]) => {
      const [start, end] = val;
      const { step } = durationSlider.value;
      durationSlider.value.curValue = val;
      durationSlider.value.curValText = `${formatDuration(start)} - ${formatDuration(end)}`;
      durationSlider.value.scaleRange = [Math.floor(start / step), Math.floor(end / step)];
      handleFilterTraceList();
    };
    /** 根据当前选择范围过滤 trace 列表 */
    const handleFilterTraceList = () => {
      const [start, end] = durationSlider.value.curValue;
      const list = durationModal.value?.handleFilter(start, end);
      const newList = list?.length ? list : [];
      if (store.listType === 'trace') {
        store.setFilterTraceList(newList);
      } else {
        store.setFilterSpanList(newList);
      }
    };
    /** 格式化图表series数据显示 */
    const formatterDurationFunc = (params: any, xAxisData: string[]) => {
      const nameVal = params.name.split('-');
      const [start, end] = nameVal;
      const curStart = Number(start || 0);
      const curEnd = Number(end || 0);
      const selectStart = durationSlider.value.curValue?.[0] || 0;
      const selectEnd = durationSlider.value.curValue?.[1] || 0;
      const lastXAxisItem = xAxisData[xAxisData.length - 1]; // 最大刻度范围
      const lastXAxisItemFirst = Number(lastXAxisItem.split('-')?.[0] ?? 0); // 最大刻度范围起始值
      // 由于刻度均分原因 最大值不一定与最大刻度值相等
      if (curStart === lastXAxisItemFirst) {
        return curStart < selectEnd ? '#A3C5FD' : '#DCDEE5';
      }

      return curStart >= selectStart && curEnd <= selectEnd ? '#A3C5FD' : '#DCDEE5';
    };

    return {
      barChartref,
      chartOptions,
      durationSlider,
      handleDurationChange,
    };
  },
  render() {
    return (
      <div class='chart-filtering-wrap'>
        {this.chartOptions && (
          <div class='chart-item'>
            <div class='header'>
              <span>{this.$t('耗时区间')}</span>
              <span class='range'>
                <span class='active'>{this.durationSlider.curValText}</span>
                <span>{` / ${this.durationSlider.overallText}`}</span>
              </span>
            </div>
            <BarChart
              ref='barChartref'
              options={this.chartOptions}
              selectedRange={this.durationSlider.curValue}
            />
            <Slider
              class='slider-range'
              v-model={this.durationSlider.curValue}
              maxValue={this.durationSlider.max}
              minValue={this.durationSlider.min}
              step={this.durationSlider.step}
              range
              onChange={this.handleDurationChange}
            />
          </div>
        )}
      </div>
    );
  },
});
