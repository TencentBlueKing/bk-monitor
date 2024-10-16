<script setup>
  import { ref, computed, watch, onUnmounted } from 'vue';
  import useStore from '@/hooks/use-store';
  import useTrendChart from '@/hooks/use-trend-chart';
  import { useRoute } from 'vue-router/composables';
  import axios from 'axios';

  import http from '@/api';
  const store = useStore();
  const route = useRoute();

  const emit = defineEmits(['polling']);

  const CancelToken = axios.CancelToken;

  const isUnionSearch = computed(() => store.getters.isUnionSearch);
  const unionIndexList = computed(() => store.getters.unionIndexList);
  const retrieveParams = computed(() => store.getters.retrieveParams);
  const chartKey = computed(() => store.state.retrieve.chartKey);
  const interval = computed(() => retrieveParams.value.interval);

  const refDataTrendCanvas = ref(null);

  const { updateChart } = useTrendChart({
    target: refDataTrendCanvas,
  });

  const finishPolling = ref(false);
  const isStart = ref(false);
  const isLoading = ref(false);

  let isRequsting = false;
  let requestInterval = 0;
  let pollingEndTime = 0;
  let pollingStartTime = 0;
  let logChartCancel = null;
  let currentInterval = 0;
  let optionData = new Map();

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

  const handleIntervalSplit = (startTime, endTime) => {
    currentInterval = interval.value;
    let intervalTemp = interval.value;

    // 如果是手动变更汇聚周期导致的更新
    // 这里禁止进一步进行更新interval, 避免重置
    if (/^chart_interval_/.test(chartKey.value)) {
      return;
    }

    // 按照小时统计
    const duration = (endTime - startTime) / 3600;

    // 按照分钟统计
    const durationMin = (endTime - startTime) / 60;

    if (duration < 1) {
      // 小于1小时 1min
      intervalTemp = '1m';
      currentInterval = '1m';
      intervalTemp = 'auto';

      if (durationMin < 5) {
        currentInterval = '30s';
      }

      if (durationMin < 2) {
        currentInterval = '5s';
      }

      if (durationMin < 1) {
        currentInterval = '1s';
      }
    } else if (duration < 6) {
      // 小于6小时 5min
      intervalTemp = '5m';
      currentInterval = intervalTemp;
    } else if (duration < 72) {
      // 小于72小时 1hour
      intervalTemp = '1h';
      currentInterval = '1h';
    } else {
      // 大于72小时 1day
      intervalTemp = '1d';
      currentInterval = '1d';
    }

    store.commit('updateIndexItem', { interval: intervalTemp });
  };

  // 需要更新图表数据
  const getSeriesData = (startTimeStamp, endTimeStamp) => {
    // 轮循结束
    if (finishPolling.value) return;

    // 请求间隔时间
    requestInterval = isStart.value ? requestInterval : handleRequestSplit(startTimeStamp, endTimeStamp);

    if (!isStart.value) {
      isRequsting = true;
      optionData.clear();
      // 获取坐标分片间隔
      handleIntervalSplit(startTimeStamp, endTimeStamp);
      isLoading.value = true;
      emit('polling', !isLoading.value);

      pollingEndTime = endTimeStamp;
      pollingStartTime = requestInterval > 0 ? pollingEndTime - requestInterval : startTimeStamp;

      isStart.value = true;
    } else {
      pollingEndTime = pollingStartTime;
      pollingStartTime = pollingStartTime - requestInterval;
    }

    if (pollingStartTime < startTimeStamp) {
      pollingStartTime = startTimeStamp;
      // 轮询结束
      finishPolling.value = true;
      isRequsting = false;
      emit('polling', false);
    }

    if (pollingStartTime < retrieveParams.value.start_time) {
      pollingStartTime = retrieveParams.value.start_time;
    }

    if ((!isUnionSearch.value && !!route.params?.indexId) || (isUnionSearch.value && unionIndexList.value?.length)) {
      // 从检索切到其他页面时 表格初始化的时候路由中indexID可能拿不到 拿不到 则不请求图表
      const urlStr = isUnionSearch.value ? 'unionSearch/unionDateHistogram' : 'retrieve/getLogChartList';
      const queryData = {
        ...retrieveParams.value,
        time_range: 'customized',
        interval: currentInterval,
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

            originChartData.forEach(item => {
              optionData.set(item.key_as_string, [
                (optionData.get(item.key_as_string)?.[0] ?? 0) + item.doc_count,
                item.key,
              ]);
            });
          }

          if (!res?.result) {
            finishPolling.value = true;
            isRequsting = false;
            emit('polling', false);
            updateChart([]);
            return;
          }

          const keys = [...optionData.keys()];

          keys.sort((a, b) => a[0] - b[0]);
          const data = keys.map(key => [optionData.get(key)[1], optionData.get(key)[0], key]);
          updateChart(data, currentInterval);

          if (!finishPolling.value && requestInterval > 0) {
            getSeriesData(startTimeStamp, endTimeStamp);
            return;
          }

          isRequsting = false;
        })
        .catch(() => {
          finishPolling.value = true;
          isRequsting = false;
          updateChart([]);
        })

        .finally(() => {
          isLoading.value = false;
        });
    } else {
      finishPolling.value = true;
      isRequsting = false;
      emit('polling', false);
    }
  };

  watch(
    () => chartKey.value,
    () => {
      if (!isRequsting) {
        finishPolling.value = false;

        isStart.value = false;
        optionData.clear();
        logChartCancel?.();
        updateChart([]);
        getSeriesData(retrieveParams.value.start_time, retrieveParams.value.end_time);
      }
    },
    {
      immediate: true,
    },
  );

  onUnmounted(() => {
    logChartCancel?.();
  });
</script>
<script>
  export default {
    name: 'BkTrendChart',
  };
</script>
<template>
  <div
    v-bkloading="{ isLoading: isLoading }"
    class="monitor-echart-wrap"
  >
    <div
      ref="refDataTrendCanvas"
      style="height: 110px"
    ></div>
  </div>
</template>
<style lang="scss" scoped>
  .monitor-echart-wrap {
    position: relative;
    width: 100%;
    height: 100%;
    padding-top: 18px;
    color: #63656e;
    background-color: #fff;
    background-repeat: repeat;
    background-position: top;
    border-radius: 2px;
  }
</style>
