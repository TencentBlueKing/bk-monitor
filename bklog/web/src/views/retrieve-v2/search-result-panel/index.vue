<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import useStore from '@/hooks/use-store';
import { getCommonFilterAdditionWithValues } from '@/store/helper';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { throttle } from 'lodash-es';

import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import NoIndexSet from '../result-comp/no-index-set';
import LogResult from './log-result/index';

// #if MONITOR_APP !== 'trace'
const SearchResultChart = defineAsyncComponent(() =>
  import(/* webpackChunkName: 'retrieve-search-result-chart' */ '../search-result-chart/index.tsx'),
);
// #else
// #code const SearchResultChart = () => null;
// #endif

// #if MONITOR_APP !== 'trace'
const FieldFilter = defineAsyncComponent(() =>
  import(/* webpackChunkName: 'retrieve-field-filter' */ './field-filter'),
);
// #else
// #code const FieldFilter = () => null;
// #endif

// #if MONITOR_APP !== 'trace' && MONITOR_APP !== 'apm'
const LogClustering = defineAsyncComponent(() =>
  import(/* webpackChunkName: 'retrieve-v2-log-clustering' */ './log-clustering/index'),
);
// #else
// #code const LogClustering = () => null;
// #endif

const DEFAULT_FIELDS_WIDTH = 200;

const props = defineProps({
  activeTab: { type: String, default: '' },
});
const emit = defineEmits(['update:active-tab']);

const store = useStore();
const isFilterLoading = computed(() => store.state.indexFieldInfo.is_loading);
const isSearchRersultLoading = computed(() => store.state.indexSetQueryResult.is_loading);

const retrieveParams = computed(() => store.getters.retrieveParams);
const requestAddition = computed(() => store.getters.requestAddition);
const isNoIndexSet = computed(() => !store.state.retrieve.flatIndexSetList.length);
const isOriginShow = computed(() => props.activeTab === 'origin');
const trendContextKey = computed(() => [
  store.state.spaceUid,
  store.state.indexId,
  ...(store.state.indexItem.ids ?? []),
].join('|'));
const pageLoading = computed(
  () => isFilterLoading.value || isSearchRersultLoading.value || store.state.retrieve.isIndexSetLoading,
);

const totalCount = ref(0);
const queueStatus = ref(false);
const isTrendChartShow = ref(!store.state.storage[BK_LOG_STORAGE.TREND_CHART_IS_FOLD]);
const DEFAULT_TREND_CHART_EXPANDED_HEIGHT = 170;
const DEFAULT_TREND_CHART_FOLDED_HEIGHT = 40;
const heightNum = ref(isTrendChartShow.value ? DEFAULT_TREND_CHART_EXPANDED_HEIGHT : DEFAULT_TREND_CHART_FOLDED_HEIGHT);
const shouldRenderTrendChart = ref(false);
const isTrendChartPending = ref(!shouldRenderTrendChart.value);
const TREND_CHART_MIN_DELAY = 5000;
let renderTrendChartDelayTimer = null;
let renderTrendChartIdleTimer = null;

const setTrendChartPending = () => {
  if (!isOriginShow.value) {
    return;
  }

  isTrendChartPending.value = true;
  store.commit('retrieve/updateTrendDataLoading', true);
  heightNum.value = isTrendChartShow.value ? Math.max(heightNum.value, DEFAULT_TREND_CHART_EXPANDED_HEIGHT) : DEFAULT_TREND_CHART_FOLDED_HEIGHT;
  RetrieveHelper.setTrendGraphHeight(heightNum.value);
};

const clearRenderTrendChartTimer = () => {
  if (renderTrendChartDelayTimer) {
    window.clearTimeout(renderTrendChartDelayTimer);
    renderTrendChartDelayTimer = null;
  }

  if (renderTrendChartIdleTimer) {
    if (window.cancelIdleCallback) {
      window.cancelIdleCallback(renderTrendChartIdleTimer);
    } else {
      window.clearTimeout(renderTrendChartIdleTimer);
    }
    renderTrendChartIdleTimer = null;
  }
};

const scheduleRenderTrendChart = () => {
  if (shouldRenderTrendChart.value || renderTrendChartDelayTimer || renderTrendChartIdleTimer) {
    return;
  }

  const render = () => {
    renderTrendChartIdleTimer = null;
    shouldRenderTrendChart.value = true;
  };

  renderTrendChartDelayTimer = window.setTimeout(() => {
    renderTrendChartDelayTimer = null;

    if (!isOriginShow.value) {
      return;
    }

    if (window.requestIdleCallback) {
      renderTrendChartIdleTimer = window.requestIdleCallback(render, { timeout: 3000 });
      return;
    }

    renderTrendChartIdleTimer = window.setTimeout(render, 1200);
  }, TREND_CHART_MIN_DELAY);
};

watch(isOriginShow, (value) => {
  if (value) {
    scheduleRenderTrendChart();
  }
});

watch(trendContextKey, (value, oldValue) => {
  if (oldValue !== undefined && value !== oldValue) {
    setTrendChartPending();
  }
});

RetrieveHelper.on(RetrieveEvent.TREND_GRAPH_PENDING, setTrendChartPending);

onMounted(() => {
  RetrieveHelper.setTrendGraphHeight(heightNum.value);
  scheduleRenderTrendChart();
});

onBeforeUnmount(() => {
  clearRenderTrendChartTimer();
  RetrieveHelper.off(RetrieveEvent.TREND_GRAPH_PENDING, setTrendChartPending);
});

const fieldFilterWidth = computed(() => store.state.storage[BK_LOG_STORAGE.FIELD_SETTING].width);
const isShowFieldStatistics = computed(() => {
  if (window.__IS_MONITOR_TRACE__) {
    return false;
  }
  return store.state.storage[BK_LOG_STORAGE.FIELD_SETTING].show;
});

const retrieveParamsWithCommonAddition = computed(() => {
  return {
    ...retrieveParams.value,
    addition: [...requestAddition.value, ...getCommonFilterAdditionWithValues(store.state)],
  };
});

RetrieveHelper.setLeftFieldSettingWidth(fieldFilterWidth.value);

const changeTotalCount = (count) => {
  totalCount.value = count;
};
const changeQueueRes = (status) => {
  queueStatus.value = status;
};
const handleTrendReady = () => {
  isTrendChartPending.value = false;
};

const handleToggleChange = (isShow, height) => {
  isTrendChartShow.value = isShow;
  heightNum.value = height + 4;
  RetrieveHelper.setTrendGraphHeight(heightNum.value);
};

const handleFieldsShowChange = (status) => {
  if (status) {
    RetrieveHelper.setLeftFieldSettingWidth(DEFAULT_FIELDS_WIDTH);
  }
  RetrieveHelper.setLeftFieldIsShown(!!status);
  store.commit('updateStorage', {
    [BK_LOG_STORAGE.FIELD_SETTING]: {
      show: !!status,
      width: DEFAULT_FIELDS_WIDTH,
    },
  });
};

const handleFilterWidthChange = throttle((width) => {
  if (width !== fieldFilterWidth.value) {
    RetrieveHelper.setLeftFieldSettingWidth(width);
    store.commit('updateStorage', {
      [BK_LOG_STORAGE.FIELD_SETTING]: {
        show: true,
        width,
      },
    });
  }
});

const handleUpdateActiveTab = (active) => {
  emit('update:active-tab', active);
};

const __IS_MONITOR_TRACE__ = computed(() => {
  return !!window.__IS_MONITOR_TRACE__;
});

const rightContentStyle = computed(() => {
  if (isOriginShow.value) {
    return {
      width: `calc(100% - ${isShowFieldStatistics.value ? fieldFilterWidth.value : 0}px)`,
    };
  }

  return {
    width: '100%',
    padding: '8px 16px',
  };
});
</script>

<template>
  <div :class="['search-result-panel', { flex: !__IS_MONITOR_TRACE__ }]">
    <!-- 无索引集 申请索引集页面 -->
    <NoIndexSet v-if="!pageLoading && isNoIndexSet" />
    <template v-else>
      <div :class="['field-list-sticky', { 'is-show': isShowFieldStatistics, 'is-close': !isShowFieldStatistics }]">
        <FieldFilter
          v-show="isOriginShow"
          v-bkloading="{ isLoading: isFilterLoading && isShowFieldStatistics }"
          v-log-drag="{
            minWidth: 160,
            maxWidth: 500,
            defaultWidth: fieldFilterWidth,
            autoHidden: false,
            theme: 'dotted',
            placement: 'left',
            isShow: isShowFieldStatistics,
            onHidden: () => (isShowFieldStatistics = false),
            onWidthChange: handleFilterWidthChange,
          }"
          :class="{ 'filet-hidden': !isShowFieldStatistics }"
          :value="isShowFieldStatistics"
          :width="fieldFilterWidth"
          @field-status-change="handleFieldsShowChange"
        />
      </div>
      <div
        :style="__IS_MONITOR_TRACE__ ? undefined : rightContentStyle"
        :class="['search-result-content', { 'field-list-show': isShowFieldStatistics }]"
      >
        <div
          v-show="isOriginShow"
          :class="[
            'trend-chart-reserved',
            RetrieveHelper.randomTrendGraphClassName,
            { 'is-fold': !isTrendChartShow, 'is-loading': isTrendChartPending || !shouldRenderTrendChart },
          ]"
          :style="{ height: `${heightNum}px` }"
        >
          <SearchResultChart
            v-if="shouldRenderTrendChart"
            @change-queue-res="changeQueueRes"
            @change-total-count="changeTotalCount"
            @toggle-change="handleToggleChange"
            @trend-ready="handleTrendReady"
          />
          <div
            v-if="isTrendChartPending || !shouldRenderTrendChart"
            class="trend-chart-skeleton"
            aria-hidden="true"
          >
            <div class="trend-chart-skeleton-title">
              <span class="trend-chart-skeleton-caret" />
              <span class="trend-chart-skeleton-title-line" />
              <span class="trend-chart-skeleton-meta-line" />
            </div>
            <div
              v-if="isTrendChartShow"
              class="trend-chart-skeleton-body"
            >
              <span
                v-for="index in 36"
                :key="index"
                class="trend-chart-skeleton-bar"
                :style="{ height: `${24 + ((index * 17) % 78)}px` }"
              />
            </div>
          </div>
        </div>
        <div
          v-show="isOriginShow"
          class="split-line"
        />

        <keep-alive>
          <LogResult
            v-if="isOriginShow"
            :queue-status="queueStatus"
            :retrieve-params="retrieveParamsWithCommonAddition"
            :total-count="totalCount"
          />
          <LogClustering
            v-if="activeTab === 'clustering'"
            :active-tab="activeTab"
            :height="heightNum"
            :retrieve-params="retrieveParamsWithCommonAddition"
            @show-change="handleUpdateActiveTab"
          />
        </keep-alive>
      </div>
    </template>
  </div>
</template>

<style lang="scss">
  @import './index.scss';
</style>
