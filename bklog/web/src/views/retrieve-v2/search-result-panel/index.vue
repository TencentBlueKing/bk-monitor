<script setup>
  import { computed, ref, watch } from 'vue';
  import useStore from '@/hooks/use-store';

  import FieldFilter from './field-filter';
  import SearchResultChart from '../search-result-chart/index.vue';
  import NoIndexSet from '../result-comp/no-index-set';

  import LogClustering from './log-clustering/index';
  import OriginalLog from './original-log/index';

  const props = defineProps({
    activeTab: { type: String, default: '' },
  });

  const store = useStore();
  const isFilterLoading = computed(() => store.state.indexFieldInfo.is_loading);
  const retrieveParams = computed(() => store.getters.retrieveParams);
  const isNoIndexSet = computed(() => !store.state.retrieve.indexSetList.length);
  const isOriginShow = computed(() => props.activeTab === 'origin');
  const pageLoading = computed(() => store.getters.pageLoading);

  const totalCount = ref(0);
  const queueStatus = ref(false);
  const isTrendChartShow = ref(true);
  const isShowFieldStatistics = ref(true);
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
</script>

<template>
  <div class="search-result-panel">
    <!-- 无索引集 申请索引集页面 -->
    <NoIndexSet v-if="!pageLoading && isNoIndexSet" />
    <template v-else>
      <FieldFilter
        v-show="isOriginShow"
        v-bkloading="{ isLoading: isFilterLoading }"
        :is-show-field-statistics.sync="isShowFieldStatistics"
      ></FieldFilter>
      <div
        :class="[
          'search-result-content',
          {
            'is-trend-chart-show': isTrendChartShow,
            'is-show-field-statistics': isShowFieldStatistics && isOriginShow,
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
            :height="heightNum"
            :retrieve-params="retrieveParams"
          />
        </keep-alive>
      </div>
    </template>
  </div>
</template>

<style scoped>
  @import './index.scss';
</style>
