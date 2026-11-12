<script setup>
import { useApplicationStore } from '@/app/state/domains/application-store';
import { useRetrieveStore } from '@/app/state/domains/retrieve-store';
import { ServicesInstance } from '@/platform/services';

  import { ref, computed, onBeforeUnmount, inject } from 'vue';

  import useTrendChart from '@/shared/composables/use-trend-chart';
  import useRetrieveEvent from '@/shared/composables/use-retrieve-event';
  import BklogLoading from '@/shared/ui/loading';
  import { useRoute } from "vue-router";
  import { getCommonFilterAdditionWithValues } from '../../app/state/helper';
  import { RetrieveEvent } from '../retrieval/retrieve-helper';
  import axios from 'axios';


  const store = useApplicationStore();
  const route = useRoute();

  defineEmits(['polling']);

  const CancelToken = axios.CancelToken;
  const isUnionSearch = computed(() => store.isUnionSearch);
  const unionIndexList = computed(() => store.unionIndexList);
  const retrieveParams = computed(() => store.retrieveParams);
  const requestAddition = computed(() => store.requestAddition);
  const isLoading = computed(() => store.indexFieldInfo.is_loading);
  const gradeOptions = computed(() => store.indexFieldInfo.custom_config?.grade_options);

  const refDataTrendCanvas = ref(null);
  const dynamicHeight = ref(130);
  const handleChartDataZoom = inject('handleChartDataZoom', () => {});
  const { initChartData, setChartData } = useTrendChart({
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
  let isInit = true;
  let sumCount = 0;

  // 需要更新图表数据
  const getSeriesData = (startTimeStamp, endTimeStamp) => {
    // 轮循结束
    if (finishPolling.value) return;

    // 请求间隔时间
    requestInterval = isStart.value ? requestInterval : handleRequestSplit(startTimeStamp, endTimeStamp);

    if (!isStart.value) {
      isInit = true;
      sumCount = 0;
      pollingEndTime = endTimeStamp;
      pollingStartTime = requestInterval > 0 ? pollingEndTime - requestInterval : startTimeStamp;

      isStart.value = true;
      useRetrieveStore().updateTrendDataLoading(true);
      useRetrieveStore().updateTrendDataCount(0);
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
      useRetrieveStore().updateTrendDataLoading(false);
    }

    if (pollingStartTime < retrieveParams.value.start_time) {
      pollingStartTime = retrieveParams.value.start_time;
    }

    if (pollingStartTime > pollingEndTime) {
      // 轮询结束
      finishPolling.value = true;
      isStart.value = false;
      useRetrieveStore().updateTrendDataLoading(false);
      return;
    }

    const indexId = window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId;
    if ((!isUnionSearch.value && !!indexId) || (isUnionSearch.value && unionIndexList.value?.length)) {
      // 从检索切到其他页面时 表格初始化的时候路由中indexID可能拿不到 拿不到 则不请求图表
      const urlStr = (isUnionSearch.value ? ServicesInstance.unionSearch.unionDateHistogram : ServicesInstance.retrieve.getLogChartList);
      const queryData = {
        ...retrieveParams.value,
        addition: [...requestAddition.value, ...getCommonFilterAdditionWithValues(store)],
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

      if (
        gradeOptions.value &&
        !gradeOptions.value.disabled &&
        gradeOptions.value.type === 'custom' &&
        gradeOptions.value.field
      ) {
        Object.assign(queryData, {
          group_field: gradeOptions.value.field,
        });
      }

      urlStr(
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
            sumCount += setChartData(res?.data?.aggs, queryData.group_field, isInit);
            isInit = false;

            useRetrieveStore().updateTrendDataCount(sumCount);
          }

          if (!res?.result || requestInterval === 0) {
            isStart.value = false;
            finishPolling.value = true;
            useRetrieveStore().updateTrendDataLoading(false);
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
          useRetrieveStore().updateTrendDataLoading(false);
        });
    } else {
      isStart.value = false;
      finishPolling.value = true;
      useRetrieveStore().updateTrendDataLoading(false);
    }
  };

  let runningTimer = null;
  const loadTrendData = () => {
    logChartCancel?.();
    setChartData(null, null, true);

    runningTimer && clearTimeout(runningTimer);
    runningTimer = setTimeout(() => {
      finishPolling.value = false;
      isStart.value = false;
      getSeriesData(retrieveParams.value.start_time, retrieveParams.value.end_time);
    });
  };

  const { addEvent } = useRetrieveEvent();
  addEvent(
    [
      RetrieveEvent.SEARCH_VALUE_CHANGE,
      RetrieveEvent.SEARCH_TIME_CHANGE,
      RetrieveEvent.TREND_GRAPH_SEARCH,
      RetrieveEvent.FAVORITE_ACTIVE_CHANGE,
      RetrieveEvent.INDEX_SET_ID_CHANGE,
    ],
    loadTrendData,
  );

  onBeforeUnmount(() => {
    finishPolling.value = true;
    runningTimer && clearTimeout(runningTimer);
    logChartCancel?.();
  });
</script>
<script>
  export default {
    name: 'BkTrendChart',
  };
</script>
<template>
  <bklog-loading
    class="monitor-echart-wrap"
    data-testid="trend-chart-loading"
    :loading="isLoading"
    size="mini"
    :z-index="10"
  >
    <div
      ref="refDataTrendCanvas"
      :style="{ height: dynamicHeight + 'px' }"
    ></div>
  </bklog-loading>
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
