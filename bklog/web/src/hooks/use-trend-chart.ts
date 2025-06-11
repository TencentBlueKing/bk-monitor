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

import chartOption, { COLOR_LIST, getSeriesData } from './trend-chart-options';
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

  const retrieveParams = computed(() => store.getters.retrieveParams);
  const gradeOptionsGroups = computed(() =>
    (store.state.indexFieldInfo.custom_config?.grade_options?.settings ?? []).filter(setting => setting.enable),
  );

  /**
   * 匹配规则是否为值匹配
   * 可选值：value、regex
   */
  const isGradeMatchValue = computed(() => {
    return store.state.indexFieldInfo.custom_config?.grade_options?.valueType === 'value';
  });

  let runningInterval = '1m';
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

    runningInterval = `1${intervals[intervals.length - 1]?.[0] ?? 's'}`;
    return runningInterval;
  };

  const initChartData = () => {
    setRunnningInterval();
    return { interval: runningInterval };
  };

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

  const getDefData = (buckets?) => {
    if (buckets?.length) {
      return buckets.map(bucket => [bucket.key, 0, bucket.key_as_string]);
    }

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

  const dataset = new Map<string, any>();
  let sortKeys = ['level_1', 'level_2', 'level_3', 'level_4', 'level_5', 'level_6', 'others'];

  const isMatchedGroup = (group, fieldValue) => {
    return RetrieveHelper.isMatchedGroup(group, fieldValue, isGradeMatchValue.value);
  };

  const setGroupData = (group, fieldName, isInit?) => {
    const buckets = group?.buckets || [];

    let count = 0;

    if (isInit) {
      dataset.clear();
      options.series = [];
      sortKeys = gradeOptionsGroups.value.map(g => g.id);
      const colors = [];

      gradeOptionsGroups.value.forEach(group => {
        if (!dataset.has(group.id)) {
          const dst = getSeriesData({ name: group.name, data: [], color: group.color });
          options.series.push(dst);
          colors.push(group.color);
          const index = options.series.length - 1;
          dataset.set(group.id, { group, dst: options.series[index], dataMap: new Map<string, number>() });
        }
      });

      options.color = colors;
    }

    // 遍历外层
    buckets.forEach(bucket => {
      const { key, key_as_string, doc_count } = bucket;
      const groupData = bucket[fieldName]?.buckets ?? [];

      count += doc_count;
      // 如果返回数据没有符合条件的分组数据
      // 这里初始化默认数据
      if (groupData.length === 0) {
        sortKeys.forEach(dstKey => {
          const { dataMap } = dataset.get(dstKey);
          dataMap.set(key, [key, 0, key_as_string]);
        });
      }

      groupData?.forEach(d => {
        const fieldValue = d.key;
        // 用于判定是否已经命中
        let isMatched = false;

        sortKeys.forEach(dstKey => {
          const { group, dataMap } = dataset.get(dstKey);

          let count = dataMap.get(key)?.[1] ?? 0;

          if (!isMatched) {
            if (dstKey === 'others' || isMatchedGroup(group, fieldValue)) {
              isMatched = true;
              count += d.doc_count ?? 0;
            }
          }

          dataMap.set(key, [key, count, key_as_string]);
        });
      });
    });

    sortKeys.forEach(key => {
      const { dst, dataMap } = dataset.get(key);
      dst.data = Array.from(dataMap.values());
    });

    updateChart(isInit);
    return count;
  };

  const setDefaultData = (aggs?, isInit?) => {
    let opt_data = new Map<Number, Number[]>();
    const buckets = aggs?.group_by_histogram?.buckets || [];
    const series = [];
    let count = 0;

    if (!isInit) {
      (options.series[0]?.data ?? []).forEach(item => {
        opt_data.set(item[0], [item[1], item[2]]);
      });
    }

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
      options.series[0].data = data;
    }
    options.color = ['#A4B3CD'];
    updateChart(isInit);
    opt_data.clear();
    opt_data = null;
    return count;
  };

  const setChartData = (eggs, fieldName?, isInit?) => {
    if (fieldName) {
      return setGroupData(eggs?.group_by_histogram ?? {}, fieldName, isInit);
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
      const { start_time, end_time } = store.state.indexItem;
      cachedBatch = { startValue: start_time, endValue: end_time };
    }

    if (batch.startValue && batch.endValue) {
      const timeFrom = dayjs.tz(batch.startValue).format('YYYY-MM-DD HH:mm:ss');
      const timeTo = dayjs.tz(batch.endValue).format('YYYY-MM-DD HH:mm:ss');

      if (window.__IS_MONITOR_COMPONENT__) {
        handleChartDataZoom([timeFrom, timeTo]);
      } else {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
        // 更新Store中的时间范围
        store.dispatch('handleTrendDataZoom', { start_time: timeFrom, end_time: timeTo, format: true }).then(() => {
          store.dispatch('requestIndexSetQuery');
        });
      }
    }
  });

  const handleCanvasResize = debounce(() => {
    chartInstance?.resize();
  });

  const handleDblClick = () => {
    if (cachedBatch !== null) {
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
    }
  };
  onMounted(() => {
    if (target.value) {
      chartInstance = Echarts.init(target.value);

      chartInstance.on('dataZoom', handleDataZoom);
      target.value?.addEventListener('dblclick', handleDblClick);

      addListener(target.value, handleCanvasResize);
    }
  });

  onBeforeUnmount(() => {
    if (target.value) {
      removeListener(target.value, handleCanvasResize);
      target.value.removeEventListener('dblclick', handleDblClick);
    }
  });

  return { initChartData, setChartData, clearChartData };
};
