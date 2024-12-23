<script setup>
  import { computed, ref, defineComponent, h } from 'vue';

  import useStore from '@/hooks/use-store';

  import NoIndexSet from '../result-comp/no-index-set';
  // #if MONITOR_APP !== 'trace'
  import SearchResultChart from '../search-result-chart/index.vue';
  import FieldFilter from './field-filter';
  import LogClustering from './log-clustering/index';
  // #else
  // #code const SearchResultChart = defineComponent(() => h('div'));
  // #code const FieldFilter = defineComponent(() => h('div'));
  // #code const LogClustering = defineComponent(() => h('div'));
  // #endif
  
  import OriginalLog from './original-log/index';

  const DEFAULT_FIELDS_WIDTH = 220;

  const props = defineProps({
    activeTab: { type: String, default: '' },
  });
  const emit = defineEmits(['update:active-tab']);

  const store = useStore();
  const isFilterLoading = computed(() => store.state.indexFieldInfo.is_loading);
  const isSearchRersultLoading = computed(() => store.state.indexSetQueryResult.is_loading);

  const retrieveParams = computed(() => store.getters.retrieveParams);
  const isNoIndexSet = computed(() => !store.state.retrieve.indexSetList.length);
  const isOriginShow = computed(() => props.activeTab === 'origin');
  const pageLoading = computed(
    () => isFilterLoading.value || isSearchRersultLoading.value || store.state.retrieve.isIndexSetLoading,
  );

  const totalCount = ref(0);
  const queueStatus = ref(false);
  const isTrendChartShow = ref(true);
  const isShowFieldStatistics = ref(true);
  const fieldFilterWidth = ref(DEFAULT_FIELDS_WIDTH);
  const heightNum = ref();

  const changeTotalCount = count => {
    totalCount.value = count;
  };
  const changeQueueRes = status => {
    queueStatus.value = status;
  };

  const handleToggleChange = (isShow, height) => {
    isTrendChartShow.value = isShow;
    heightNum.value = height;
  };
  const handleFieldsShowChange = status => {
    if (status) fieldFilterWidth.value = DEFAULT_FIELDS_WIDTH;
    isShowFieldStatistics.value = status;
  };
  const handleFilterWidthChange = width => {
    fieldFilterWidth.value = width;
  };
  const handleUpdateActiveTab = active => {
    emit('update:active-tab', active);
  };
</script>

<template>
  <div class="search-result-panel">
    <!-- 无索引集 申请索引集页面 -->
    <NoIndexSet v-if="!pageLoading && isNoIndexSet" />
    <template v-else>
      <FieldFilter
        v-model="isShowFieldStatistics"
        v-bkloading="{ isLoading: isFilterLoading && isShowFieldStatistics }"
        v-log-drag="{
          minWidth: 160,
          maxWidth: 500,
          defaultWidth: DEFAULT_FIELDS_WIDTH,
          autoHidden: false,
          theme: 'dotted',
          placement: 'left',
          isShow: isShowFieldStatistics,
          onHidden: () => (isShowFieldStatistics = false),
          onWidthChange: handleFilterWidthChange,
        }"
        v-show="isOriginShow"
        :class="{ 'filet-hidden': !isShowFieldStatistics }"
        @field-status-change="handleFieldsShowChange"
      ></FieldFilter>
      <div
        :style="{ flex: 1, width: `calc(100% - ${fieldFilterWidth}px)` }"
        :class="[
          'search-result-content',
          {
            'is-trend-chart-show': isTrendChartShow,
            'is-show-field-statistics': isShowFieldStatistics && isOriginShow,
            'is-not-show-field-statistics': !isShowFieldStatistics,
          },
        ]"
      >
        <SearchResultChart
          v-show="isOriginShow"
          @change-queue-res="changeQueueRes"
          @change-total-count="changeTotalCount"
          @toggle-change="handleToggleChange"
        ></SearchResultChart>
        <div
          class="split-line"
          v-show="isOriginShow"
        ></div>

        <keep-alive>
          <OriginalLog
            v-if="isOriginShow"
            :height="heightNum"
            :queue-status="queueStatus"
            :retrieve-params="retrieveParams"
            :total-count="totalCount"
          />
          <LogClustering
            v-if="activeTab === 'clustering'"
            :active-tab="activeTab"
            :height="heightNum"
            :retrieve-params="retrieveParams"
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
