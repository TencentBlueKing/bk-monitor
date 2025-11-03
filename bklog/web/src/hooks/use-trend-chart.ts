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
import { computed, nextTick, onMounted, onBeforeUnmount, type Ref, watch } from 'vue';

import { formatNumberWithRegex } from '@/common/util';
// @ts-expect-error
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type.ts';
import dayjs from 'dayjs';
import * as Echarts from 'echarts';
import { debounce } from 'lodash-es';
import { addListener, removeListener } from 'resize-detector';
import { useRoute, useRouter } from 'vue-router/composables';

import RetrieveHelper, { RetrieveEvent } from '../views/retrieve-helper';
import chartOption, { getSeriesData } from './trend-chart-options';

export type TrandChartOption = {
  target: Ref<HTMLDivElement | null>;
  handleChartDataZoom?: (val) => void;
  dynamicHeight?: Ref<number>;
};

export type EchartData = {
  datapoints: number[][];
  target: string;
  isFinish: boolean;
};
export default ({ target, handleChartDataZoom, dynamicHeight }: TrandChartOption) => {
  let chartInstance: Echarts.ECharts = null;
  const options: any = { ...chartOption };
  const store = useStore();
  const router = useRouter();
  const route = useRoute();

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

  const barCount = 60; // auto时展示的柱子数量

  const intervals: [string, number][] = [
    ['d', 86_400],
    ['h', 3600],
    ['m', 60],
    ['s', 1],
  ];

  const xLabelMap = new Map<number, string>(); // 用于存储横坐标标签

  const setRunnningInterval = () => {
    // 1. 若汇聚周期不为auto，则直接使用用户选择的汇聚周期
    if (retrieveParams.value.interval !== 'auto') {
      runningInterval = retrieveParams.value.interval;
      return;
    }

    // 2. 若汇聚周期为auto，则根据时间范围动态计算
    const { start_time, end_time } = retrieveParams.value;
    const duration = (end_time - start_time) / 1000;
    const segments = Math.floor(duration / barCount); // 按照指定的柱子数量分割
    for (const [name, seconds] of intervals) {
      if (segments >= seconds) {
        const interval = Math.floor(segments / seconds);
        runningInterval = `${interval >= 1 ? interval : 1}${name}`;
        return name;
      }
    }

    runningInterval = `1${intervals.at(-1)?.[0] ?? 's'}`;
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

    const data: any[] = [];
    const { start_time, end_time } = retrieveParams.value;
    const startValue = getIntegerTime(start_time / 1000);
    let endValue = getIntegerTime(end_time / 1000);
    const intervalTimestamp = getIntervalValue(runningInterval);

    while (endValue > startValue) {
      data.push([endValue * 1000, 0, null]);
      endValue -= intervalTimestamp;
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

  // 计算x轴坐标点的时间显示格式
  const getXAxisFormat = (startTime: number, endTime: number, interval: string) => {
    const totalSpan = endTime - startTime; // 查询的总时间范围
    const intervalMs = getIntervalValue(interval) * 1000; // 查询的时间间隔

    // 若时间范围小于1天（<24h）
    if (totalSpan < 24 * 60 * 60 * 1000) {
      if (intervalMs <= 1000) {
        return 'HH:mm:ss.SSS';
      } // <=1s
      if (intervalMs <= 60 * 1000) {
        return 'HH:mm:ss';
      } // 1s~1min
      if (intervalMs <= 60 * 60 * 1000) {
        return 'HH:mm';
      } // 1min~1h
      return 'MM-DD HH:mm'; // >1h
    }
    // 时间范围大于等于1天（>=24h）

    if (intervalMs <= 1000) {
      return 'MM-DD HH:mm:ss.SSS';
    } // <=1s
    if (intervalMs <= 60 * 1000) {
      return 'MM-DD HH:mm:ss';
    } // 1s~1min
    if (intervalMs <= 60 * 60 * 1000) {
      return 'MM-DD HH:mm';
    } // 1min~1h
    if (intervalMs <= 24 * 60 * 60 * 1000) {
      return 'MM-DD HH:mm';
    } // 1h~1d
    return 'YYYY-MM-DD HH:mm'; // >1d
  };

  // 补齐图表数据到指定长度
  const padDataToLength = (data: [number, number, null | string][], targetLength: number, intervalMs: number) => {
    if (data.length >= targetLength) {
      return data;
    }

    // 按时间升序排序
    data.sort((a, b) => a[0] - b[0]);
    const result = [...data];
    const missing = targetLength - data.length;

    // 计算需要补前面和后面的数量
    const padBefore = Math.floor(missing / 2);
    const padAfter = missing - padBefore;

    // 前补
    const firstTime = data.length ? data[0][0] : Date.now();
    for (let i = 1; i <= padBefore; i++) {
      result.unshift([firstTime - i * intervalMs, 0, null]);
    }
    // 后补
    const lastTime = data.length ? data.at(-1)[0] : Date.now();
    for (let i = 1; i <= padAfter; i++) {
      result.push([lastTime + i * intervalMs, 0, null]);
    }

    return result;
  };

  // 监听loading, 在接口请求结束时再补充数据
  const loading = computed(() => store.state.retrieve.isTrendDataLoading);
  watch(loading, val => {
    if (val === false) {
      const intervalMs = getIntervalValue(runningInterval) * 1000;
      if (options.series && Array.isArray(options.series)) {
        for (const series of options.series) {
          if (series.data && Array.isArray(series.data)) {
            series.data = padDataToLength(series.data, 15, intervalMs);
          }
        }
        updateChart();
      }
    }
  });

  const setGroupData = (group, fieldName, isInit?) => {
    const buckets = group?.buckets || [];
    let count = 0;

    const { start_time, end_time } = retrieveParams.value;
    const formatStr = getXAxisFormat(start_time, end_time, runningInterval);

    if (isInit) {
      dataset.clear();
      options.series = [];
      sortKeys = gradeOptionsGroups.value.map(g => g.id);
      const colors: any[] = [];

      for (const newGroup of gradeOptionsGroups.value) {
        if (!dataset.has(newGroup.id)) {
          const dst = getSeriesData({ name: newGroup.name, data: [], color: newGroup.color });
          options.series.push(dst);
          colors.push(newGroup.color);
          const index = options.series.length - 1;
          dataset.set(newGroup.id, {
            group: newGroup,
            dst: options.series[index],
            dataMap: new Map<string, [number, number, null | string]>(),
          });
        }
      }

      options.color = colors;
    }

    // 遍历外层
    for (const bucket of buckets) {
      const { key, key_as_string, doc_count } = bucket;
      const groupData = bucket[fieldName]?.buckets ?? [];

      count += doc_count;
      if (groupData.length === 0) {
        // 如果返回数据没有符合条件的分组数据
        // 这里初始化默认数据
        for (const dstKey of sortKeys) {
          const { dataMap } = dataset.get(dstKey);
          dataMap.set(key, [key, 0, key_as_string]);
          xLabelMap.set(key, dayjs(key).format(formatStr));
        }
      }

      for (const d of groupData) {
        const fieldValue = d.key;
        // 用于判定是否已经命中
        let isMatched = false;

        for (const dstKey of sortKeys) {
          const { group: newGroup, dataMap } = dataset.get(dstKey);

          let newCount = dataMap.get(key)?.[1] ?? 0;

          if (!isMatched && (dstKey === 'others' || isMatchedGroup(newGroup, fieldValue))) {
            isMatched = true;
            newCount += d.doc_count ?? 0;
          }

          dataMap.set(key, [key, newCount, key_as_string]);
          xLabelMap.set(key, dayjs(key).format(formatStr));
        }
      }
    }

    for (const key of sortKeys) {
      const { dst, dataMap } = dataset.get(key);
      dst.data = Array.from(dataMap.values());
    }

    updateChart(isInit);
    return count;
  };

  const setDefaultData = (aggs?, isInit?) => {
    let opt_data = new Map<number, [number, null | string]>();
    const buckets = aggs?.group_by_histogram?.buckets || [];
    const series: Record<string, any>[] = [];
    let count = 0;

    const { start_time, end_time } = retrieveParams.value;
    const formatStr = getXAxisFormat(start_time, end_time, runningInterval);

    if (!isInit) {
      for (const item of options.series[0]?.data ?? []) {
        opt_data.set(item[0], [item[1], item[2]]);
      }
    }

    for (const { key, doc_count, key_as_string } of buckets) {
      xLabelMap.set(key, dayjs(key).format(formatStr));
      opt_data.set(key, [doc_count + (opt_data.get(key)?.[0] ?? 0), key_as_string]);
      count += doc_count;
    }

    const keys = [...opt_data.keys()];
    keys.sort((a, b) => a[0] - b[0]);
    const data = keys.map(key => {
      const val = opt_data.get(key);
      return [key, val ? val[0] : 0, val ? val[1] : null] as [number, number, null | string];
    });

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
    if (isInit) {
      xLabelMap.clear();
    }
    if (fieldName) {
      return setGroupData(eggs?.group_by_histogram ?? {}, fieldName, isInit);
    }

    return setDefaultData(eggs, isInit);
  };

  const clearChartData = () => {
    updateChart();
  };

  // 格式化数字（带单位）
  const abbreviateNumber = (value: number) => {
    let newValue = value;
    let suffix = '';

    if (value >= 1000 && value < 1_000_000) {
      newValue = value / 1000;
      suffix = 'K';
    } else if (value >= 1_000_000 && value < 1_000_000_000) {
      newValue = value / 1_000_000;
      suffix = ' Mil';
    } else if (value >= 1_000_000_000) {
      newValue = value / 1_000_000_000;
      suffix = 'Bil';
    }

    // 使用 Intl.NumberFormat 来格式化数字，避免不必要的小数部分
    const formatter = new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 3, // 最多保留一位小数
      minimumFractionDigits: 0, // 最少保留零位小数
    });

    return `${formatter.format(newValue)}${suffix}`;
  };

  // 格式化数字（三位分隔）
  const getShowTotalNum = (num: number) => formatNumberWithRegex(num);

  const updateChart = (notMerge = true) => {
    if (!chartInstance) {
      return;
    }

    const { start_time, end_time } = retrieveParams.value;
    const formatStr = getXAxisFormat(start_time, end_time, runningInterval);

    options.xAxis[0].axisLabel.formatter = v => xLabelMap.get(v) || dayjs(v).format(formatStr);
    options.xAxis[0].minInterval = getIntervalValue(runningInterval);
    options.yAxis[0].axisLabel.formatter = v => abbreviateNumber(v);
    options.yAxis[0].splitNumber = dynamicHeight.value < 120 ? 2 : 4;

    // 格式化tooltip
    options.tooltip.formatter = params => {
      // 获取开始时间
      const timeStart = dayjs(params[0].value[0]).format('MM-DD HH:mm:ss');

      // 计算结束时间：起始时间 + runningInterval
      const startTimestamp = params[0].value[0]; // 时间戳
      const intervalSeconds = getIntervalValue(runningInterval);
      const endTimestamp = startTimestamp + intervalSeconds * 1000; // 转换为毫秒
      const timeEnd = dayjs(endTimestamp).format('MM-DD HH:mm:ss');

      // 多 series 展示
      const seriesHtml = params
        .map(item => {
          const value = item.value[1] || 0;
          const seriesName = item.seriesName;
          const color = item.color;
          return `
          <div style="display: flex; align-items: center; margin-top: 4px;">
            <span style="
              display: inline-block; 
              width: 10px; 
              height: 10px; 
              background-color: ${color}; 
              border-radius: 50%; 
            "></span>
            <span style="flex: 1; margin-left: 6px;">${seriesName}</span>
            <span style="font-weight: bold;">${getShowTotalNum(value)}</span>
          </div>
        `;
        })
        .join('');

      return `
        <div style="min-width: 120px;">
          <div>${timeStart} <span style="font-weight:bold;margin:0 4px;">to</span> ${timeEnd}</div>
          ${seriesHtml}
        </div>
      `;
    };

    chartInstance.setOption(options, { notMerge });
    nextTick(() => {
      dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: true,
      });
    });
  };

  const cachedBatch = computed(() => store.state.storage[BK_LOG_STORAGE.CACHED_BATCH_LIST] || []);
  const canGoBack = computed(() => cachedBatch.value.length > 1);

  const handleDataZoom = debounce(event => {
    const [batch] = event.batch;

    // 初始化时，存入初始时间范围
    if (cachedBatch.value.length === 0 && !batch.dblclick && !batch.isBack) {
      const { start_time, end_time } = store.state.indexItem;
      cachedBatch.value.push({
        startValue: start_time,
        endValue: end_time,
        start: start_time,
        end: end_time,
      });
      store.commit('updateStorage', { [BK_LOG_STORAGE.CACHED_BATCH_LIST]: cachedBatch.value });
    }

    // 每次有效选择都 push
    if (batch.startValue && batch.endValue && !batch.dblclick && !batch.isBack) {
      cachedBatch.value.push({
        startValue: batch.startValue,
        endValue: batch.endValue,
        start: batch.startValue,
        end: batch.endValue,
      });
      store.commit('updateStorage', { [BK_LOG_STORAGE.CACHED_BATCH_LIST]: cachedBatch.value });
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
          // 更新URL
          router.replace({
            query: {
              ...route.query,
              start_time: timeFrom,
              end_time: timeTo,
            },
          });
        });
      }
    }
  });

  // 趋势图回退到上一个时间范围
  const backToPreChart = () => {
    if (cachedBatch.value.length > 1) {
      const prev = cachedBatch.value.at(-2); // 倒数第二个
      chartInstance.dispatchAction({
        type: 'dataZoom',
        batch: [prev],
        dblclick: false,
        isBack: true, // 标记本次是回退,避免点击回退时触发handleDataZoom的push操作
      });
      cachedBatch.value.pop();
      store.commit('updateStorage', { [BK_LOG_STORAGE.CACHED_BATCH_LIST]: cachedBatch.value });
    }
  };

  const handleCanvasResize = debounce(() => {
    chartInstance?.resize();
  });

  // 回到初始趋势图（第一个历史范围）
  const handleDblClick = () => {
    if (cachedBatch.value.length > 0) {
      const first = cachedBatch.value[0];
      chartInstance.dispatchAction({
        type: 'dataZoom',
        dblclick: true, // 标记本次是双击
        isBack: true,
        batch: [first],
      });
      cachedBatch.value.splice(0, cachedBatch.value.length); // 清空缓存时间组
      store.commit('updateStorage', { [BK_LOG_STORAGE.CACHED_BATCH_LIST]: cachedBatch.value });
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

  return { initChartData, setChartData, clearChartData, backToPreChart, canGoBack };
};
