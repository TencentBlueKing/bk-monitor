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
import RetrieveHelper, { RetrieveEvent } from '../views/retrieve-helper';

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

  // const datepickerValue = computed(() => store.state.indexItem.datePickerValue);
  const retrieveParams = computed(() => store.getters.retrieveParams);

  let runningInterval = '1m';
  // let cachedTimRange = [];
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

  // 时间向下取整
  const getIntegerTime = time => {
    if (runningInterval === '1d') {
      // 如果周期是 天 则特殊处理
      const step = dayjs.tz(time * 1000).format('YYYY-MM-DD');
      return Date.parse(`${step} 00:00:00`) / 1000;
    }

    const intervalTimestamp = getIntervalValue(runningInterval);
    return Math.floor(time / intervalTimestamp) * intervalTimestamp;
  };

  const getDefData = () => {
    const data = [];
    const { start_time, end_time } = retrieveParams.value;
    const startValue = getIntegerTime(start_time / 1000);
    let endValue = getIntegerTime(end_time / 1000);
    const intervalTimestamp = getIntervalValue(runningInterval);

    while (endValue > startValue) {
      data.push([endValue * 1000, 0, null]);
      endValue = endValue - intervalTimestamp;
    }

    if (endValue < startValue) {
      endValue = startValue;
      data.push([endValue * 1000, 0, null]);
    }

    return data;
  };

  const setGroupData = (group, isInit?) => {
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
      if (isInit) {
        series.push(getSeriesData({ name: item.key, data, color: colors[index % colors.length] }));
      } else {
        options.series[index].data.push(...data);
      }

      opt_data.clear();
      opt_data = null;
    });

    if (isInit) {
      if (!series.length) {
        series.push(getSeriesData({ name: '', data: getDefData(), color: '#A4B3CD' }));
      }
      options.series = series;
    }

    updateChart(isInit);
    return count;
  };

  const setDefaultData = (aggs, isInit?) => {
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

    if (isInit) {
      series.push(getSeriesData({ name: '', data: data.length ? data : getDefData(), color: '#A4B3CD' }));
      options.series = series;
    } else {
      options.series[0].data.push(...data);
    }

    updateChart(isInit);
    opt_data.clear();
    opt_data = null;
    return count;
  };

  const setChartData = (eggs, fieldName?, isInit?) => {
    if (fieldName && eggs[fieldName]) {
      return setGroupData(eggs[fieldName], isInit);
    }

    return setDefaultData(eggs, isInit);
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

  const updateChart = (notMerge = true) => {
    if (!chartInstance) {
      return;
    }

    options.series.forEach(s => {
      s.barMinHeight = 2;
      s.itemStyle.color = params => {
        return (params.value[1] ?? 0) > 0 ? params.color : '#fff';
      };
    });

    options.xAxis[0].axisLabel.formatter = v => formatTimeString(v, runningInterval);
    options.xAxis[0].minInterval = getIntervalValue(runningInterval);
    options.yAxis[0].axisLabel.formatter = v => abbreviateNumber(v);
    options.yAxis[0].splitNumber = dynamicHeight.value < 120 ? 2 : 4;

    chartInstance.setOption(options, { notMerge });
    nextTick(() => {
      dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: true,
      });
    });
  };

  let cachedBatch: any = null;

  const handleDataZoom = debounce(event => {
    const [batch] = event.batch;
    if (cachedBatch === null && !batch.dblclick) {
      cachedBatch = batch;
    }

    if (batch.startValue && batch.endValue) {
      const timeFrom = dayjs.tz(batch.startValue).format('YYYY-MM-DD HH:mm:ss');
      const timeTo = dayjs.tz(batch.endValue).format('YYYY-MM-DD HH:mm:ss');

      if (window.__IS_MONITOR_COMPONENT__) {
        handleChartDataZoom([timeFrom, timeTo]);
      } else {
        // 更新Store中的时间范围
        // 同时会自动更新chartKey，触发接口更新当前最新数据
        store.dispatch('handleTrendDataZoom', { start_time: timeFrom, end_time: timeTo, format: true }).then(() => {
          store.dispatch('requestIndexSetQuery');
        });
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
      chartInstance.on('dblclick', () => {
        chartInstance.dispatchAction({
          type: 'dataZoom',
          dblclick: true,
          batch: [
            {
              startValue: cachedBatch.startValue,
              endValue: cachedBatch.endValue,
              start: cachedBatch.startValue,
              end: cachedBatch.endValue,
            },
          ],
        });

        cachedBatch = null;
      });

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
