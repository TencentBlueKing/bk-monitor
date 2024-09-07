<script setup>
  import { computed, ref } from 'vue';
  import useStore from '@/hooks/use-store';

  import FieldFilter from './field-filter';
  import SearchResultChart from '../search-result-chart/index.vue';

  import LogClustering from './log-clustering/index';
  import OriginalLog from './original-log/index';

  const props = defineProps({
    activeTab: { type: String, default: '' },
  });

  const store = useStore();
  const isFilterLoading = computed(() => store.state.indexFieldInfo.is_loading);
  const retrieveParams = computed(() => store.getters.retrieveParams);

  const totalCount = ref(0);
  const queueStatus = ref(false);
  const isTrendChartShow = ref(true);
  const isShowFieldStatistics = ref(true);

  const changeTotalCount = count => {
    totalCount.value = count;
  };
  const changeQueueRes = status => {
    queueStatus.value = status;
  };

  const handleToggleChange = isShow => {
    isTrendChartShow.value = isShow;
  };
</script>

<template>
  <div class="search-result-panel">
    <FieldFilter
      v-bkloading="{ isLoading: isFilterLoading }"
      :is-show-field-statistics.sync="isShowFieldStatistics"
    ></FieldFilter>
    <div
      :class="[
        'search-result-content',
        { 'is-trend-chart-show': isTrendChartShow, 'is-show-field-statistics': isShowFieldStatistics },
      ]"
    >
      <SearchResultChart
        @change-queue-res="changeQueueRes"
        @change-total-count="changeTotalCount"
        @toggle-change="handleToggleChange"
      ></SearchResultChart>
      <div class="split-line"></div>
      <keep-alive>
        <OriginalLog
          v-if="activeTab === 'origin'"
          :retrieveParams="retrieveParams"
          :totalCount="totalCount"
          :queueStatus="queueStatus"
        />
        <LogClustering
          v-if="activeTab === 'clustering'"
          :retrieveParams="retrieveParams"
        />
      </keep-alive>
    </div>
  </div>
</template>

<style scoped>
  @import './index.scss';
</style>
