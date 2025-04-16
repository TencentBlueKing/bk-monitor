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
import { computed, nextTick, onMounted, onBeforeUnmount, type Ref } from 'vue';

// @ts-ignore
import useStore from '@/hooks/use-store';
import dayjs from 'dayjs';
import * as Echarts from 'echarts';
import { debounce } from 'lodash';
import { addListener, removeListener } from 'resize-detector';

import chartOption, { getSeriesData } from './trend-chart-options';

export type TrandChartOption = {
  target: Ref<HTMLDivElement | null>;
  handleChartDataZoom?: (val) => void;
  dynamicHeight?: Ref<number>;
};

export type EchartData = {
  datapoints: Array<number[]>;
  target: string;
  isFinish: boolean;
};
export default ({ target, handleChartDataZoom, dynamicHeight }: TrandChartOption) => {
  let chartInstance: Echarts.ECharts = null;
  const options: any = Object.assign({}, chartOption);
  const store = useStore();

  const datepickerValue = computed(() => store.state.indexItem.datePickerValue);
  const retrieveParams = computed(() => store.getters.retrieveParams);

  let runningInterval = '1m';
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
      const { start_time, end_time } = retrieveParams.value;
      const durationHour = (end_time / 1000 - start_time / 1000) / 3600;
      // 当筛选时间间隔6小时以上 显示日期
      const format = durationHour < 6 ? 'HH:mm:ss' : 'MM-DD HH:mm:ss';
      return dayjs.tz(data).format(format).replace(/:00$/, '');
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
      s: 1,
      m: 60,
      h: 60 * 60,
      d: 24 * 60 * 60,
    };

    const matchs = (interval ?? '1h').match(/(\d+)(s|m|h|d)/);
    const num = matchs[1];
    const unit = matchs[2];

    return timeunit[unit] * Number(num);
  };

  // 默认需要展示的柱子数量
  const barCount = 60;
  const intervals: [string, number][] = [
    ['d', 86400],
    ['h', 3600],
    ['m', 60],
    ['s', 1],
  ];

  const setRunnningInterval = () => {
    if (retrieveParams.value.interval !== 'auto') {
      runningInterval = retrieveParams.value.interval;
      return;
    }

    const { start_time, end_time } = retrieveParams.value;

    // 按照小时统计
    // 按照指定的柱子数量分割
    const duration = (end_time - start_time) / 1000;
    const segments = Math.floor(duration / barCount);
    for (const [name, seconds] of intervals) {
      if (segments >= seconds) {
        const interval = Math.floor(segments / seconds);
        runningInterval = `${interval >= 1 ? interval : 1}${name}`;
        return name;
      }
    }

    runningInterval = intervals[intervals.length - 1]?.[0] ?? '1s';
    return runningInterval;
  };

  const initChartData = () => {
    setRunnningInterval();
    return { interval: runningInterval };
  };

  const colors = ['#D46D5D', '#F59789', '#F5C78E', '#6FC5BF', '#92D4F1', '#A3B1CC', '#DCDEE5'];

  const setGroupData = group => {
    const buckets = group?.buckets || [];
    const series = [];
    let count = 0;

    buckets.forEach((item, index) => {
      let opt_data = new Map<Number, Number[]>();
      (item.group_by_histogram?.buckets || []).forEach(({ key, doc_count, key_as_string }) => {
        opt_data.set(key, [doc_count + (opt_data.get(key)?.[0] ?? 0), key_as_string]);
        count += doc_count;
      });

      const keys = [...opt_data.keys()];
      keys.sort((a, b) => a[0] - b[0]);
      const data = keys.map(key => [key, opt_data.get(key)[0], opt_data.get(key)[1]]);
      series.push(getSeriesData({ name: item.key, data, color: colors[index % colors.length] }));

      opt_data.clear();
      opt_data = null;
    });

    options.series = series;
    updateChart();
    return count;
  };

  const setDefaultData = aggs => {
    let opt_data = new Map<Number, Number[]>();
    const buckets = aggs?.group_by_histogram?.buckets || [];
    const series = [];
    let count = 0;

    buckets.forEach(({ key, doc_count, key_as_string }) => {
      opt_data.set(key, [doc_count + (opt_data.get(key)?.[0] ?? 0), key_as_string]);
      count += doc_count;
    });

    const keys = [...opt_data.keys()];
    keys.sort((a, b) => a[0] - b[0]);
    const data = keys.map(key => [key, opt_data.get(key)[0], opt_data.get(key)[1]]);
    series.push(getSeriesData({ name: '', data, color: '#A4B3CD' }));
    options.series = series;
    updateChart();
    opt_data.clear();
    opt_data = null;
    return count;
  };

  const setChartData = (eggs, fieldName?) => {
    if (fieldName && eggs[fieldName]) {
      return setGroupData(eggs[fieldName]);
    }

    return setDefaultData(eggs);
  };

  const clearChartData = () => {
    updateChart();
  };

  /** 缩写数字 */
  const abbreviateNumber = (value: number) => {
    let newValue = value;
    let suffix = '';

    if (value >= 1000 && value < 1000000) {
      newValue = value / 1000;
      suffix = 'K';
    } else if (value >= 1000000 && value < 1000000000) {
      newValue = value / 1000000;
      suffix = ' Mil';
    } else if (value >= 1000000000) {
      newValue = value / 1000000000;
      suffix = 'Bil';
    }

    // 使用 Intl.NumberFormat 来格式化数字，避免不必要的小数部分
    const formatter = new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 3, // 最多保留一位小数
      minimumFractionDigits: 0, // 最少保留零位小数
    });

    return `${formatter.format(newValue)}${suffix}`;
  };

  const updateChart = () => {
    if (!chartInstance) {
      return;
    }

    options.series.forEach(s => {
      s.barMinHeight = 2;
      s.itemStyle.color = params => {
        return (params.value[1] ?? 0) > 0 ? params.color : '#fff';
      };
    });

    // options.series[0].stack = 'total';
    options.xAxis[0].axisLabel.formatter = v => formatTimeString(v, runningInterval);
    options.xAxis[0].minInterval = getIntervalValue(runningInterval);
    options.yAxis[0].axisLabel.formatter = v => abbreviateNumber(v);
    options.yAxis[0].splitNumber = dynamicHeight.value < 120 ? 2 : 4;

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

      if (window.__IS_MONITOR_COMPONENT__) {
        handleChartDataZoom([timeFrom, timeTo]);
      } else {
        // 更新Store中的时间范围
        // 同时会自动更新chartKey，触发接口更新当前最新数据
        store.dispatch('handleTrendDataZoom', { start_time: timeFrom, end_time: timeTo, format: true });
      }
    }
  });

  const handleCanvasResize = debounce(() => {
    chartInstance?.resize();
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

      addListener(target.value, handleCanvasResize);
    }
  });

  onBeforeUnmount(() => {
    if (target.value) {
      removeListener(target.value, handleCanvasResize);
    }
  });

  return { initChartData, setChartData, clearChartData };
};
