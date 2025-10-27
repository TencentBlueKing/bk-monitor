<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
-->

<script setup>
  import { computed, ref, watch, defineProps, provide } from 'vue';

  import * as authorityMap from '@/common/authority-map';
  import { handleTransformToTimestamp } from '@/components/time-range/utils';
  import useStore from '@/hooks/use-store';
  import { updateTimezone } from '@/language/dayjs';
  import { ConditionOperator } from '@/store/condition-operator';
  import RouteUrlResolver, { RetrieveUrlResolver } from '@/store/url-resolver';
  import { isEqual } from 'lodash-es';
  import { useRoute, useRouter } from 'vue-router/composables';

  import useResizeObserve from '../../../hooks/use-resize-observe';
  import useScroll from '../../../hooks/use-scroll';
  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import { getInputQueryIpSelectItem } from '../search-bar/const.common';
  import SearchBar from '../search-bar/index.vue';
  import QueryHistory from '../sub-bar/query-history.vue';
  import SearchResultPanel from '../search-result-panel/index.vue';
  import RetrieveHelper from '../../retrieve-helper.tsx';

  const GLOBAL_SCROLL_SELECTOR = RetrieveHelper.getScrollSelector();

  const props = defineProps({
    indexSetApi: {
      type: Function,
      default: null,
    },
    timeRange: {
      type: Array,
      default: () => ['now-15m', 'now'],
    },
    timezone: {
      type: String,
      default: '',
    },
    refleshImmediate: {
      type: String,
      default: '',
    },
    handleChartDataZoom: {
      type: Function,
      default: null,
    },
  });

  provide('handleChartDataZoom', props.handleChartDataZoom);

  const store = useStore();
  const router = useRouter();
  const route = useRoute();
  const indexSetParams = computed(() => store.state.indexItem);
  const initLoading = ref(true);

  // 解析默认URL为前端参数
  // 这里逻辑不要动，不做解析会导致后续前端查询相关参数的混乱
  // store.dispatch('updateIndexItemByRoute', { route, list: [] });

  const setDefaultIndexsetId = () => {
    if (!route.query.indexId) {
      const routeParams = store.getters.retrieveParams;
      const resolver = new RetrieveUrlResolver({
        ...routeParams,
        datePickerValue: store.state.indexItem.datePickerValue,
      });
      if (store.getters.isUnionSearch) {
        router.replace({ query: { ...route.query, ...resolver.resolveParamsToUrl() } });
        return;
      }
      if (store.state.indexId) {
        router.replace({
          query: {
            ...route.query,
            indexId: store.state.indexId,
            ...resolver.resolveParamsToUrl(),
          },
        });
      }
    }
  };

  const getApmIndexSetList = async () => {
    store.commit('retrieve/updateIndexSetLoading', true);
    store.commit('retrieve/updateIndexSetList', []);
    return props
      .indexSetApi()
      .then(res => {
        let indexSetList = [];
        if (res.length) {
          // 有索引集
          // 根据权限排序
          const s1 = [];
          const s2 = [];
          for (const item of res) {
            if (item.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
              s1.push(item);
            } else {
              s2.push(item);
            }
          }
          indexSetList = s1.concat(s2);
          // 索引集数据加工
          indexSetList.forEach(item => {
            item.index_set_id = `${item.index_set_id}`;
            item.indexName = item.index_set_name;
            item.lightenName = ` (${item.indices.map(item => item.result_table_id).join(';')})`;
          });
          store.commit('retrieve/updateIndexSetList', indexSetList);
          return indexSetList;
        }
      })
      .finally(() => {
        initLoading.value = false;
        store.commit('retrieve/updateIndexSetLoading', false);
      });
  };

  /**
   * 拉取索引集列表
   */
  const getIndexSetList = () => {
    if (!props.indexSetApi) return;
    getApmIndexSetList().then(res => {
      if (!res?.length) return;
      // 拉取完毕根据当前路由参数回填默认选中索引集
      // store.dispatch('updateIndexItemByRoute', { route, list: res }).then(() => {
      //   setDefaultIndexsetId();
      //   store.dispatch('requestIndexSetFieldInfo').then(() => {
      //     store.dispatch('requestIndexSetQuery');
      //   });
      // });
    });
  };

  const setRouteQuery = query => {
    if (query) {
      router.replace({
        query,
      });
      return;
    }
    const routeQuery = { ...route.query };
    const { keyword, addition, ip_chooser, search_mode, begin, size } = store.getters.retrieveParams;
    const resolver = new RetrieveUrlResolver({
      keyword,
      addition,
      ip_chooser,
      search_mode,
      begin,
      size,
    });
    Object.assign(routeQuery, resolver.resolveParamsToUrl());
    router.replace({
      query: routeQuery,
    });
  };

  const handleIndexSetSelected = payload => {
    if (!isEqual(indexSetParams.value.ids, payload.ids) || indexSetParams.value.isUnionIndex !== payload.isUnionIndex) {
      if (payload.isUnionIndex) {
        setRouteQuery({
          ...route.query,
          indexId: undefined,
          unionList: JSON.stringify(ids),
          clusterParams: undefined,
        });
        return;
      }
      setRouteQuery({ ...route.query, indexId: payload.ids[0], unionList: undefined, clusterParams: undefined });
      store.commit('updateUnionIndexList', payload.isUnionIndex ? payload.ids ?? [] : []);
      store.dispatch('requestIndexSetItemChanged', payload ?? {}).then(() => {
        store.commit('retrieve/updateChartKey');
        store.dispatch('requestIndexSetQuery');
      });
    }
  };

  const updateSearchParam = payload => {
    const { keyword, addition, ip_chooser, search_mode } = payload;
    const foramtAddition = (addition ?? []).map(item => {
      const instance = new ConditionOperator(item);
      return instance.formatApiOperatorToFront();
    });

    if (Object.keys(ip_chooser).length) {
      foramtAddition.unshift(getInputQueryIpSelectItem(ip_chooser));
    }

    setRouteQuery();

    store.commit('updateIndexItemParams', {
      keyword,
      addition: foramtAddition,
      ip_chooser,
      begin: 0,
      search_mode,
    });

    setTimeout(() => {
      store.dispatch('requestIndexSetQuery');
    });
  };

  const init = () => {
    const result = handleTransformToTimestamp(props.timeRange, store.getters.retrieveParams.format);
    const resolver = new RouteUrlResolver({ route });
    store.commit('updateIndexItem', {
      ...resolver.convertQueryToStore(),
      start_time: result[0],
      end_time: result[1],
      datePickerValue: props.timeRange,
    });
    getIndexSetList();
  };
  init();

  watch(
    () => props.timeRange,
    async val => {
      if (!val) return;
      getIndexSetList();
      store.commit('updateIsSetDefaultTableColumn', false);
      const result = handleTransformToTimestamp(val, store.getters.retrieveParams.format);
      store.commit('updateIndexItemParams', { start_time: result[0], end_time: result[1], datePickerValue: val });
      await store.dispatch('requestIndexSetFieldInfo');
      store.dispatch('requestIndexSetQuery');
    },
  );

  watch(
    () => props.timezone,
    val => {
      if (!val) return;
      store.commit('updateIndexItemParams', { timezone });
      updateTimezone(timezone);
      store.dispatch('requestIndexSetQuery');
    },
  );

  watch(
    () => props.refleshImmediate,
    () => {
      store.dispatch('requestIndexSetQuery');
    },
  );

  const activeTab = ref('origin');
  const searchBarHeight = ref(0);
  const resultRow = ref();
  const handleHeightChange = height => {
    searchBarHeight.value = height;
  };

  const initIsShowClusterWatch = watch(
    () => store.state.clusterParams,
    () => {
      if (!!store.state.clusterParams) {
        activeTab.value = 'clustering';
        initIsShowClusterWatch();
      }
    },
    { deep: true },
  );

  watch(
    () => store.state.indexItem.isUnionIndex,
    () => {
      if (store.state.indexItem.isUnionIndex && activeTab.value === 'clustering') {
        activeTab.value = 'origin';
      }
    },
  );

  const stickyStyle = computed(() => {
    return {
      '--offset-search-bar': `${searchBarHeight.value + 8}px`,
    };
  });

  const contentStyle = computed(() => {
    return {
      '--left-width': `0px`,
    };
  });

  /** 开始处理滚动容器滚动时，收藏夹高度 */

  // 顶部二级导航高度，这个高度是固定的
  const subBarHeight = ref(64);
  const paddingTop = ref(0);
  // 滚动容器高度
  const scrollContainerHeight = ref(0);

  useScroll(GLOBAL_SCROLL_SELECTOR, event => {
    if (event.target) {
      const scrollTop = event.target.scrollTop;
      paddingTop.value = scrollTop > subBarHeight.value ? subBarHeight.value : scrollTop;
    }
  });

  useResizeObserve(
    GLOBAL_SCROLL_SELECTOR,
    entry => {
      scrollContainerHeight.value = entry.target.offsetHeight;
    },
    0,
  );

  const isStickyTop = computed(() => {
    if (window.__IS_MONITOR_TRACE__) {
      return false;
    }
    return paddingTop.value === subBarHeight.value;
  });

  // const isScrollY = computed(() => {
  //   return !window.__IS_MONITOR_TRACE__
  // })

  /** * 结束计算 ***/
</script>
<template>
  <div
    :style="stickyStyle"
    :class="['retrieve-v2-index', { 'scroll-y': true, 'is-sticky-top': isStickyTop }]"
    v-bkloading="{ isLoading: initLoading }"
  >
    <div
      class="sub-head"
      v-show="!initLoading"
    >
      <SelectIndexSet
        :popover-options="{ offset: '-6,10' }"
        @collection="getIndexSetList"
        @selected="handleIndexSetSelected"
      ></SelectIndexSet>
      <QueryHistory @change="updateSearchParam"></QueryHistory>
    </div>
    <div
      :style="contentStyle"
      :class="['retrieve-v2-body']"
      v-show="!initLoading"
    >
      <div class="retrieve-v2-content">
        <SearchBar @height-change="handleHeightChange"></SearchBar>
        <div
          ref="resultRow"
          :style="{
            height: `calc(100% - ${searchBarHeight + 14}px)`,
          }"
          class="result-row"
        >
          <SearchResultPanel :active-tab.sync="activeTab"></SearchResultPanel>
        </div>
      </div>
    </div>
  </div>
</template>
<style lang="scss">
  @import './monitor.scss';
  @import '../segment-pop.scss';
</style>
