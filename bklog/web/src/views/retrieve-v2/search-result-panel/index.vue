<script setup>
  import { computed, ref } from 'vue';

  import useStore from '@/hooks/use-store';

  import NoIndexSet from '../result-comp/no-index-set';
  import SearchResultChart from '../search-result-chart/index.vue';
  import FieldFilter from './field-filter';
  import LogClustering from './log-clustering/index';
  import LogResult from './log-result/index';
  import useResizeObserve from '../../../hooks/use-resize-observe';
  import { SECTION_SEARCH_INPUT, GLOBAL_SCROLL_SELECTOR } from './log-result/log-row-attributes';
  import useScroll from '../../../hooks/use-scroll';

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
    heightNum.value = height + 4;
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

  const rightContentStyle = computed(() => {
    return {
      width: `calc(100% - ${isShowFieldStatistics.value ? fieldFilterWidth.value : 0}px)`,
    };
  });

  /**** 根据滚动条滚动位置动态计算左侧字段列表高度 *****/
  // 搜索框高度，搜索框高度会改变
  const searchInputHeight = ref(0);
  // 滚动容器高度
  const scrollContainerHeight = ref(0);
  // 自定操作时顶部填充高度，根据滚动位置动态计算
  const paddingTop = ref(0);
  // 顶部二级导航高度，这个高度是固定的
  const subBarHeight = ref(64);
  // 原始日志，日志聚类这一层级的Tab高度，高度固定
  const tabHeight = ref(50);

  useResizeObserve(SECTION_SEARCH_INPUT, entry => {
    searchInputHeight.value = entry.target.offsetHeight;
  });

  useResizeObserve(GLOBAL_SCROLL_SELECTOR, entry => {
    scrollContainerHeight.value = entry.target.offsetHeight;
  });

  const getPaddingTop = scrollTop => {
    // 如果滚动位置小于二级导航高度，直接返回滚动位置
    if (scrollTop <= subBarHeight.value) {
      return scrollTop;
    }

    // 如果滚动位置大于二级导航高度，小于搜索框高度，直接返回二级导航高度
    // 搜索框吸顶，不占高度
    if (scrollTop > subBarHeight.value && scrollTop <= subBarHeight.value + searchInputHeight.value) {
      return subBarHeight.value;
    }

    // 如果滚动位置大于搜索框 + 二级导航高度，直接计算当前滚动位置 - 搜索框高度
    // 搜索框吸顶，不占高度，这里只需要计算二级导航高度 + Tab框高度
    const top = scrollTop - searchInputHeight.value;

    // 如果滚动位置大于搜索框 + 二级导航高度 + Tab框高度，直接返回Tab框高度 + 二级导航高度
    if (top > tabHeight.value + subBarHeight.value) {
      return tabHeight.value + subBarHeight.value;
    }

    return top;
  };

  useScroll(GLOBAL_SCROLL_SELECTOR, event => {
    const scrollTop = event.target.scrollTop;
    paddingTop.value = getPaddingTop(scrollTop);
  });

  const fieldListStyle = computed(() => {
    // 高度计算：滚动容器高度 - 搜索框高度 - 二级导航高度 - Tab框高度 + 有效滚动填充
    const height =
      scrollContainerHeight.value - searchInputHeight.value - subBarHeight.value - tabHeight.value + paddingTop.value;

    return {
      height: isShowFieldStatistics.value ? `${height}px` : 'auto',
    };
  });

  /***** 计算结束 ******/
</script>

<template>
  <div class="search-result-panel flex">
    <!-- 无索引集 申请索引集页面 -->
    <NoIndexSet v-if="!pageLoading && isNoIndexSet" />
    <template v-else>
      <div
        :class="['field-list-sticky', { 'is-show': isShowFieldStatistics }]"
        :style="fieldListStyle"
      >
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
      </div>
      <div
        :class="['search-result-content', { 'field-list-show': isShowFieldStatistics }]"
        :style="rightContentStyle"
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
          <LogResult
            v-if="isOriginShow"
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
