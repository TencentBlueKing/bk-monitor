<script setup>
  import { computed, ref } from 'vue';

  import useStore from '@/hooks/use-store';
  import { throttle } from 'lodash';
  import { getCommonFilterAdditionWithValues } from '@/store/helper'

  import RetrieveHelper from '../../retrieve-helper';
  import NoIndexSet from '../result-comp/no-index-set';
  // #if MONITOR_APP !== 'trace'
  import SearchResultChart from '../search-result-chart/index.vue';
  // #else
  // #code const SearchResultChart = () => null;
  // #endif

  // #if MONITOR_APP !== 'trace'
  import FieldFilter from './field-filter';
  // #else
  // #code const FieldFilter = () => null;
  // #endif

  // #if MONITOR_APP !== 'trace' && MONITOR_APP !== 'apm'
  import LogClustering from './log-clustering/index';
  // #else
  // #code const LogClustering = () => null;
  // #endif

  import { BK_LOG_STORAGE } from '@/store/store.type';

  import LogResult from './log-result/index';

  const DEFAULT_FIELDS_WIDTH = 200;

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
  const heightNum = ref();

  const fieldFilterWidth = computed(() => store.state.storage[BK_LOG_STORAGE.FIELD_SETTING].width);
  const isShowFieldStatistics = computed(() => {
    if(window.__IS_MONITOR_TRACE__) {
      return false;
    }
    return store.state.storage[BK_LOG_STORAGE.FIELD_SETTING].show
  });

  const retrieveParamsWithCommonAddition = computed(() => {
    return {
      ...retrieveParams.value,
      addition: [...retrieveParams.value.addition, ...getCommonFilterAdditionWithValues(store.state)]
    }
  })

  RetrieveHelper.setLeftFieldSettingWidth(fieldFilterWidth.value);

  const changeTotalCount = count => {
    totalCount.value = count;
  };
  const changeQueueRes = status => {
    queueStatus.value = status;
  };

  const handleToggleChange = (isShow, height) => {
    isTrendChartShow.value = isShow;
    heightNum.value = height + 4;
    RetrieveHelper.setTrendGraphHeight(heightNum.value);
  };

  const handleFieldsShowChange = status => {
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

  const handleFilterWidthChange = throttle(width => {
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

  const handleUpdateActiveTab = active => {
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
      <div :class="['field-list-sticky', { 'is-show': isShowFieldStatistics }]">
        <FieldFilter
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
          v-show="isOriginShow"
          :class="{ 'filet-hidden': !isShowFieldStatistics }"
          :value="isShowFieldStatistics"
          :width="fieldFilterWidth"
          @field-status-change="handleFieldsShowChange"
        ></FieldFilter>
      </div>
      <div
        :style="__IS_MONITOR_TRACE__ ? undefined : rightContentStyle"
        :class="['search-result-content', { 'field-list-show': isShowFieldStatistics }]"
      >
        <SearchResultChart
          v-show="isOriginShow"
          :class="RetrieveHelper.randomTrendGraphClassName"
          @change-queue-res="changeQueueRes"
          @change-total-count="changeTotalCount"
          @toggle-change="handleToggleChange"
        ></SearchResultChart>
        <div
          class="split-line"
          v-show="isOriginShow"
        ></div>

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
