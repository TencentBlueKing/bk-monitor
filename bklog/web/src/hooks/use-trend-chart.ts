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
import { computed, nextTick, onMounted, Ref } from 'vue';

// @ts-ignore
import useStore from '@/hooks/use-store';
import dayjs from 'dayjs';
import * as Echarts from 'echarts';
import { debounce } from 'lodash';

import chartOption from './trend-chart-options';

export type TrandChartOption = {
  target: Ref<HTMLDivElement | null>;
};

export type EchartData = {
  datapoints: Array<number[]>;
  target: string;
  isFinish: boolean;
};
export default ({ target }: TrandChartOption) => {
  let chartInstance: Echarts.ECharts = null;
  const options: any = Object.assign({}, chartOption);
  const store = useStore();

  const datepickerValue = computed(() => store.state.indexItem.datePickerValue);
  let cachedTimRange = [];
  const delegateMethod = (name: string, ...args) => {
    return chartInstance?.[name](...args);
  };

  const dispatchAction = payload => {
    delegateMethod('dispatchAction', payload);
  };

  const formatTimeString = (data, interval) => {
    if (/\d+s$/.test(interval)) {
      return dayjs.tz(data).format('HH:mm:ss');
    }

    if (/\d+(m|h)$/.test(interval)) {
      return dayjs.tz(data).format('HH:mm:ss').replace(/:00$/, '');
    }

    if (/\d+d$/.test(interval)) {
      return dayjs
        .tz(data)
        .format('MM-DD HH:mm:ss')
        .replace(/00:00:00$/, '');
    }
  };

  const getIntervalValue = (interval: string) => {
    const timeunit = {
      s: 1000,
      m: 60 * 1000,
      h: 60 * 60 * 1000,
      d: 24 * 60 * 60 * 1000,
    };

    const matchs = (interval ?? '1h').match(/(\d+)(s|m|h|d)/);
    const num = matchs[1];
    const unit = matchs[2];

    return timeunit[unit] * Number(num);
  };

  const getMinValue = (data, interval) => {
    const minValue = data[0]?.[0];
    if (!minValue || data?.length > 5) {
      return 'dataMin';
    }
    return minValue - getIntervalValue(interval);
  };

  const getMaxValue = (data, interval) => {
    const maxValue = data.slice(-1)?.[0]?.[0];

    if (!maxValue || data?.length > 5) {
      return 'dataMax';
    }
    return maxValue + getIntervalValue(interval);
  };

  const updateChart = (data: EchartData[], interval: string) => {
    if (!chartInstance) {
      return;
    }

    options.series[0].data = data;
    options.xAxis[0].axisLabel.formatter = v => formatTimeString(v, interval);
    options.xAxis[0].minInterval = getIntervalValue(interval);
    options.xAxis[0].min = getMinValue(data, interval);
    options.xAxis[0].max = getMaxValue(data, interval);

    chartInstance.setOption(options);
    nextTick(() => {
      dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: true,
      });
    });
  };

  const handleDataZoom = debounce(event => {
    const [batch] = event.batch;

    if (batch.startValue && batch.endValue) {
      const timeFrom = dayjs.tz(batch.startValue).format('YYYY-MM-DD HH:mm:ss');
      const timeTo = dayjs.tz(batch.endValue).format('YYYY-MM-DD HH:mm:ss');

      if (!cachedTimRange.length) {
        cachedTimRange = [datepickerValue.value[0], datepickerValue.value[1]];
      }

      dispatchAction({
        type: 'restore',
      });

      // 更新Store中的时间范围
      // 同时会自动更新chartKey，触发接口更新当前最新数据
      store.dispatch('handleTrendDataZoom', { start_time: timeFrom, end_time: timeTo, format: true });
    }
  });

  onMounted(() => {
    if (target.value) {
      chartInstance = Echarts.init(target.value);

      chartInstance.on('dataZoom', handleDataZoom);
      target.value.ondblclick = () => {
        dispatchAction({
          type: 'restore',
        });

        nextTick(() => {
          if (cachedTimRange.length) {
            store.dispatch('handleTrendDataZoom', {
              start_time: cachedTimRange[0],
              end_time: cachedTimRange[1],
              format: true,
            });
            cachedTimRange = [];
          }
        });
      };
    }
  });

  return { updateChart };
};
