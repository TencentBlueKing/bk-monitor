<script setup>
  import { ref, computed, watch, onBeforeUnmount, inject } from 'vue';
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
  const isLoading = computed(() => store.state.indexFieldInfo.is_loading);

  const chartKey = computed(() => store.state.retrieve.chartKey);

  const refDataTrendCanvas = ref(null);
  const dynamicHeight = ref(130);
  const handleChartDataZoom = inject('handleChartDataZoom', () => {});
  const { initChartData, setChartData, clearChartData } = useTrendChart({
    target: refDataTrendCanvas,
    handleChartDataZoom,
    dynamicHeight,
  });

  const finishPolling = ref(false);
  const isStart = ref(false);
  let requestInterval = 0;
  let pollingEndTime = 0;
  let pollingStartTime = 0;
  let logChartCancel = null;

  const handleRequestSplit = (startTime, endTime) => {
    const duration = (endTime - startTime) / 3600000;
    if (duration <= 6) {
      // 小于6小时 一次性请求
      return 0;
    }
    if (duration < 48) {
      // 小于24小时 6小时间隔
      return 21600 * 1000;
    }

    // 大于1天 按0.5天请求
    return (86400 * 1000) / 2;
  };

  let runningInterval = 'auto';

  // 需要更新图表数据
  const getSeriesData = (startTimeStamp, endTimeStamp) => {
    // 轮循结束
    if (finishPolling.value) return;

    // 请求间隔时间
    requestInterval = isStart.value ? requestInterval : handleRequestSplit(startTimeStamp, endTimeStamp);

    if (!isStart.value) {
      pollingEndTime = endTimeStamp;
      pollingStartTime = requestInterval > 0 ? pollingEndTime - requestInterval : startTimeStamp;

      isStart.value = true;
      store.commit('retrieve/updateTrendDataLoading', true);
      store.commit('retrieve/updateTrendDataCount', 0);
      const { interval } = initChartData(startTimeStamp, endTimeStamp);
      runningInterval = interval;
    } else {
      pollingEndTime = pollingStartTime;
      pollingStartTime = pollingStartTime - requestInterval;
    }

    if (pollingStartTime < startTimeStamp) {
      pollingStartTime = startTimeStamp;
      // 轮询结束
      finishPolling.value = true;
      store.commit('retrieve/updateTrendDataLoading', false);
    }

    if (pollingStartTime < retrieveParams.value.start_time) {
      pollingStartTime = retrieveParams.value.start_time;
    }

    if (pollingStartTime > pollingEndTime) {
      // 轮询结束
      finishPolling.value = true;
      isStart.value = false;
      store.commit('retrieve/updateTrendDataLoading', false);
      return;
    }

    const indexId = window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId;
    if ((!isUnionSearch.value && !!indexId) || (isUnionSearch.value && unionIndexList.value?.length)) {
      // 从检索切到其他页面时 表格初始化的时候路由中indexID可能拿不到 拿不到 则不请求图表
      const urlStr = isUnionSearch.value ? 'unionSearch/unionDateHistogram' : 'retrieve/getLogChartList';
      const queryData = {
        ...retrieveParams.value,
        addition: [...retrieveParams.value.addition, ...store.getters.common_filter_addition],
        time_range: 'customized',
        interval: runningInterval,
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
            params: { index_set_id: indexId },
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
            const data = originChartData.map(item => [item.key, item.doc_count, item.key_as_string]);
            const sumCount = setChartData(data);
            store.commit('retrieve/updateTrendDataCount', sumCount);
          }

          if (!res?.result || requestInterval === 0) {
            isStart.value = false;
            finishPolling.value = true;
            store.commit('retrieve/updateTrendDataLoading', false);
            return;
          }

          if (!finishPolling.value && requestInterval > 0) {
            getSeriesData(startTimeStamp, endTimeStamp);
            return;
          }
        })
        .catch(() => {
          isStart.value = false;
          finishPolling.value = true;
          store.commit('retrieve/updateTrendDataLoading', false);
        });
    } else {
      isStart.value = false;
      finishPolling.value = true;
      store.commit('retrieve/updateTrendDataLoading', false);
    }
  };

  let runningTimer = null;

  watch(
    () => chartKey.value,
    () => {
      logChartCancel?.();

      runningTimer && clearTimeout(runningTimer);
      runningTimer = setTimeout(() => {
        clearChartData();

        finishPolling.value = false;
        isStart.value = false;
        getSeriesData(retrieveParams.value.start_time, retrieveParams.value.end_time);
      });
    },
    {
      immediate: true,
    },
  );

  const isRenderLoading = ref(false);
  watch(
    () => isLoading.value,
    () => {
      if (isLoading.value) {
        isRenderLoading.value = true;
        return;
      }

      setTimeout(() => {
        isRenderLoading.value = false;
      }, 300);
    },
  );

  onBeforeUnmount(() => {
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
    v-bkloading="{ isLoading: isRenderLoading }"
    class="monitor-echart-wrap"
  >
    <div
      ref="refDataTrendCanvas"
      :style="{ height: dynamicHeight + 'px' }"
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
