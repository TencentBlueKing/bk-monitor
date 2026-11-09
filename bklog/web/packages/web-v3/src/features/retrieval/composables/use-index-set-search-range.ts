/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { reactive, toRefs, toValue, type MaybeRefOrGetter } from 'vue';
import dayjs from 'dayjs';
import { handleTransformToTimestamp } from '@/shared/ui/time-range/utils';
import type { TimeRangeType } from '@/shared/ui/time-range/time-range';
import { asDictionary } from '@/shared/utils/typed-record';

/** Retained V2 time-slicing contract, independent of any component instance. */
export function useIndexSetSearchRange(datePickerValue: MaybeRefOrGetter<TimeRangeType>) {
  const state = reactive({
    finishPolling: false,
    pollingStartTime: 0,
    pollingEndTime: 0,
    requestInterval: 0, // 请求间隔时间
    interval: 'auto',
    chartInterval: 'auto',
    intervalMap: {
      '5s': 5,
      '1m': 60,
      '5m': 300,
      '15m': 900,
      '30m': 1800,
      '1h': 3600,
      '4h': 14400,
      '12h': 43200,
      '1d': 86400,
    },
  });

  function handleIntervalSplit(startTime: number, endTime: number) {
    if (state.chartInterval !== 'auto') {
      state.interval = state.chartInterval;
      return;
    }
    const duration = (endTime - startTime) / 3600000;
    if (duration < 1) {
      // 小于1小时 1min
      state.interval = '1m';
    } else if (duration < 6) {
      // 小于6小时 5min
      state.interval = '5m';
    } else if (duration < 72) {
      // 小于72小时 1hour
      state.interval = '1h';
    } else {
      // 大于72小时 1day
      state.interval = '1d';
    }
  }

  function handleRequestSplit(startTime: number, endTime: number) {
    const duration = (endTime - startTime) / 3600000;
    if (duration < 6) {
      // 小于6小时 一次性请求
      return 0;
    }
    if (duration < 48) {
      // 小于24小时 6小时间隔
      return 21600 * 1000;
    } // 大于1天 按0.5天请求
    return (86400 * 1000) / 2;
  }

  function getRealTimeRange() {
    // if (!state.pickerTimeRange.length) {
    //   return {
    //     startTimeStamp: new Date(state.retrieveParams.start_time.replace(/-/g, '/')).getTime(),
    //     endTimeStamp: new Date(state.retrieveParams.end_time.replace(/-/g, '/')).getTime(),
    //   };
    // };

    const tempList = handleTransformToTimestamp(toValue(datePickerValue));
    return {
      startTimeStamp: tempList[0],
      endTimeStamp: tempList[1],
    };
  }

  function getInterval() {
    if (state.chartInterval !== 'auto') {
      // 若选择了汇聚周期则使用retrieveParams
      state.interval = state.chartInterval;
      return;
    }

    state.interval = '1h';
  }

  function getTimeRange(startTime: number, endTime: number) {
    // 根据时间范围获取和横坐标分片
    const rangeArr: [number, number][] = [];
    const range = asDictionary(state.intervalMap)[state.interval]! * 1000;
    for (let index = endTime; index >= startTime; index = index - range) {
      rangeArr.push([0, index]);
    }

    return rangeArr;
  }

  function getIntegerTime(time: number) {
    if (state.interval === '1d') {
      // 如果周期是 天 则特殊处理
      const step = dayjs.tz(time).format('YYYY-MM-DD');
      return Date.parse(`${step} 00:00:00`);
    }

    const step = asDictionary(state.intervalMap)[state.interval]! * 1000;
    return Math.floor(time / step) * step;
  }

  return {
    ...toRefs(state),
    handleIntervalSplit,
    handleRequestSplit,
    getRealTimeRange,
    getInterval,
    getTimeRange,
    getIntegerTime,
  };
}
