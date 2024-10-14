<script setup>
  import { ref, computed, watch } from 'vue';
  import useStore from '@/hooks/use-store';
  import useTrendChart from '@/hooks/use-trend-chart';
  import { useRoute } from 'vue-router/composables';
  import axios from 'axios';

  import dayjs from 'dayjs';
  import http from '@/api';
  const store = useStore();
  const route = useRoute();

  const CancelToken = axios.CancelToken;


  const isUnionSearch = computed(() => store.getters.isUnionSearch);
  const unionIndexList = computed(() => store.getters.unionIndexList);
  const retrieveParams = computed(() => store.getters.retrieveParams);
  const chartKey = computed(() => store.state.retrieve.chartKey);

  const refDataTrendCanvas = ref(null);
  const interval = ref('auto');

  const { updateChart } = useTrendChart({
    target: refDataTrendCanvas,
  });

  const intervalMap = {
    '5s': 5,
    '1m': 60,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1h': 3600,
    '4h': 14400,
    '12h': 43200,
    '1d': 86400,
  };

  let timeRange = [];
  let finishPolling = false;
  let isStart = false;
  let requestInterval = 0;
  let pollingEndTime = 0;
  let pollingStartTime = 0;
  let logChartCancel = null;

  const optionData = ref([]);

  const handleRequestSplit = (startTime, endTime) => {
    const duration = (endTime - startTime) / 3600;
    if (duration < 6) {
      // 小于6小时 一次性请求
      return 0;
    }
    if (duration < 48) {
      // 小于24小时 6小时间隔
      return 21600;
    } // 大于1天 按0.5天请求
    return 86400 / 2;
  };

  const getIntegerTime = time => {
    if (interval.value === '1d') {
      // 如果周期是 天 则特殊处理
      const step = dayjs.tz(time * 1000).format('YYYY-MM-DD');
      return Date.parse(`${step} 00:00:00`) / 1000;
    }

    const step = intervalMap[interval.value];
    return Math.floor(time / step) * step;
  };

  const handleIntervalSplit = (startTime, endTime) => {
    const duration = (endTime - startTime) / 3600;
    if (duration < 1) {
      // 小于1小时 1min
      interval.value = '1m';
    } else if (duration < 6) {
      // 小于6小时 5min
      interval.value = '5m';
    } else if (duration < 72) {
      // 小于72小时 1hour
      interval.value = '1h';
    } else {
      // 大于72小时 1day
      interval.value = '1d';
    }
  };

  // 获取时间分片数组
  const getTimeRange = (startTime, endTime) => {
    // 根据时间范围获取和横坐标分片
    const rangeArr = [];
    const range = intervalMap[interval.value] * 1000;
    for (let index = endTime * 1000; index >= startTime * 1000; index = index - range) {
      rangeArr.push([index, 0]);
    }

    return rangeArr;
  };

  // 需要更新图表数据
  const getSeriesData = (startTimeStamp, endTimeStamp) => {
    if (startTimeStamp && endTimeStamp) {
      timeRange = [startTimeStamp, endTimeStamp];
      finishPolling = false;
      isStart = false;
      // todo: 更新全局时间 && 拉取全量数据统计条数
    }

    // 轮循结束
    if (finishPolling) return;

    // 请求间隔时间
    requestInterval = isStart ? requestInterval : handleRequestSplit(startTimeStamp, endTimeStamp);
    if (!isStart) {
      // 获取坐标分片间隔
      handleIntervalSplit(startTimeStamp, endTimeStamp);

      // 获取分片起止时间
      const curStartTimestamp = getIntegerTime(startTimeStamp);
      const curEndTimestamp = getIntegerTime(endTimeStamp);

      // 获取分片结果数组
      optionData.value = getTimeRange(curStartTimestamp, curEndTimestamp);

      pollingEndTime = endTimeStamp;
      pollingStartTime = pollingEndTime - requestInterval;

      if (pollingStartTime < startTimeStamp || requestInterval === 0) {
        pollingStartTime = startTimeStamp;
        // 轮询结束
        finishPolling = true;
      }
      isStart = true;
    } else {
      pollingEndTime = pollingStartTime;
      pollingStartTime = pollingStartTime - requestInterval;

      if (pollingStartTime < retrieveParams.value.start_time) {
        pollingStartTime = retrieveParams.value.start_time;
      }
    }

    if ((!isUnionSearch.value && !!route.params?.indexId) || (isUnionSearch.value && unionIndexList.value?.length)) {
      // 从检索切到其他页面时 表格初始化的时候路由中indexID可能拿不到 拿不到 则不请求图表
      const urlStr = isUnionSearch.value ? 'unionSearch/unionDateHistogram' : 'retrieve/getLogChartList';
      const queryData = {
        ...retrieveParams.value,
        time_range: 'customized',
        interval: interval.value,
        // 每次轮循的起始时间
        start_time: pollingStartTime,
        end_time: pollingEndTime,
      };
      if (isUnionSearch.value) {
        Object.assign(queryData, {
          index_set_ids: unionIndexList.value,
        });
      }
      http
        .request(
          urlStr,
          {
            params: { index_set_id: route.params.indexId },
            data: queryData,
          },
          {
            cancelToken: new CancelToken(c => {
              logChartCancel = c;
            }),
          },
        )
        .then(res => {
          if (res?.data) {
            const originChartData = res?.data?.aggs?.group_by_histogram?.buckets || [];
            const targetArr = originChartData.map(item => {
              return [item.key, item.doc_count];
            });

            if (pollingStartTime <= retrieveParams.value.start_time) {
              // 轮询结束
              finishPolling = true;
            }

            for (let i = 0; i < targetArr.length; i++) {
              for (let j = 0; j < optionData.value.length; j++) {
                if (optionData.value[j][0] === targetArr[i][0] && targetArr[i][1] > 0) {
                  // 根据请求结果匹配对应时间下数量叠加
                  optionData.value[j][1] = optionData.value[j][1] + targetArr[i][1];
                }
              }
            }
          } else {
            finishPolling = true;
          }

          updateChart(optionData.value);

          if (!finishPolling) {
            getSeriesData();
          }
        })
        .catch(() => false);
    } else {
      finishPolling = true;
    }
  };

  watch(
    () => chartKey,
    () => {
      finishPolling = false;
      isStart = false;
      getSeriesData(retrieveParams.value.start_time, retrieveParams.value.end_time);
    },
    {
      immediate: true
    }
  );
</script>
<script>
  export default {
    name: 'BkTrendChart',
  };
</script>
<template>
  <div ref="refDataTrendCanvas" style="height: 110px;"></div>
</template>
