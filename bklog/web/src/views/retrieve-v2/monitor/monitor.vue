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
import { computed, ref, watch, defineProps, onMounted, provide } from 'vue';

import * as authorityMap from '@/common/authority-map';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import useStore from '@/hooks/use-store';
import { updateTimezone } from '@/language/dayjs';
import { ConditionOperator } from '@/store/condition-operator';
import RouteUrlResolver, { RetrieveUrlResolver } from '@/store/url-resolver';
import { isEqual } from 'lodash';
import { useRoute, useRouter } from 'vue-router/composables';

import SelectIndexSet from '../condition-comp/select-index-set.tsx';
import { getInputQueryIpSelectItem } from '../search-bar/const.common';
import SearchBar from '../search-bar/index.vue';
import QueryHistory from '../search-bar/query-history.vue';
import SearchResultPanel from '../search-result-panel/index.vue';
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
    default: ''
  },
  handleChartDataZoom: {
    type: Function,
    default: null
  }
});

provide('handleChartDataZoom', props.handleChartDataZoom)

const store = useStore();
const router = useRouter();
const route = useRoute();

const indexSetParams = computed(() => store.state.indexItem);
const routeQueryParams = computed(() => {
  const { ids, isUnionIndex, search_mode } = store.state.indexItem;
  const {start_time, end_time, ...retrieveParams} = store.getters.retrieveParams ?? {};
  const unionList = store.state.unionIndexList;
  const clusterParams = store.state.clusterParams;
  return {
    ...retrieveParams,
    search_mode,
    ids,
    isUnionIndex,
    unionList,
    clusterParams,
  };
});

const getApmIndexSetList = async () => {
  store.commit('retrieve/updateIndexSetLoading', true);
  store.commit('retrieve/updateIndexSetList', []);
  return props.indexSetApi().then(res => {
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
  }).finally(() => {
    store.commit('retrieve/updateIndexSetLoading', false);
  });
}

/**
 * 拉取索引集列表
 */
const getIndexSetList = () => {
  if(!props.indexSetApi) return
  getApmIndexSetList().then(res => {
    if(!res?.length) return
    // 拉取完毕根据当前路由参数回填默认选中索引集
    store.dispatch('updateIndexItemByRoute', { route, list: res }).then(() => {
      store.dispatch('requestIndexSetFieldInfo').then(() => {
        store.dispatch('requestIndexSetQuery');
      });
    });
  })
};

const handleIndexSetSelected = payload => {
  if (!isEqual(indexSetParams.value.ids, payload.ids) || indexSetParams.value.isUnionIndex !== payload.isUnionIndex) {
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

const setRouteParams = () => {
  const { ids, isUnionIndex } = routeQueryParams.value;
  const params = isUnionIndex
  ? { indexId: undefined }
  : { indexId: ids?.[0] ?? route.query?.indexId };
  const query = { ...route.query, ...params };
  const resolver = new RetrieveUrlResolver({
    ...routeQueryParams.value,
    indexId: params.indexId,
    bizId: String(window.bk_biz_id),
    datePickerValue: store.state.indexItem.datePickerValue,
  });
  Object.assign(query, resolver.resolveParamsToUrl());

  if (!isEqual(query, route.query)) {
    router.replace({
      query,
    });
  }
};

const init = () => {
  const result = handleTransformToTimestamp(props.timeRange);
  const resolver = new RouteUrlResolver({ route });
  store.commit('updateIndexItem', { ...resolver.convertQueryToStore(), start_time: result[0], end_time: result[1], datePickerValue: props.timeRange, });
  store.commit('updateIndexId', '');
  store.commit('updateUnionIndexList', []);
  getIndexSetList();
};


watch(
  routeQueryParams,
  () => {
    setRouteParams();
  },
  { deep: true },
);


watch(
  () => props.timeRange,
  async val => {
    console.log('props.timeRange', props.timeRange);
    if (!val) return;
    store.commit('updateIsSetDefaultTableColumn', false);
    const result = handleTransformToTimestamp(val);
    store.commit('updateIndexItemParams', { start_time: result[0], end_time: result[1], datePickerValue: val });
    await store.dispatch('requestIndexSetFieldInfo');
    store.dispatch('requestIndexSetQuery');
  }
);

watch(
  () => props.timezone,
  val => {
    if (!val) return;
    store.commit('updateIndexItemParams', { timezone });
    updateTimezone(timezone);
    store.dispatch('requestIndexSetQuery');
  }
);

watch(() => props.refleshImmediate, () => {
  store.dispatch('requestIndexSetQuery');
})

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

onMounted(() => {
  init();
})
</script>
<template>
  <div class="retrieve-v2-index">
    <div class="sub-head">
      <SelectIndexSet
        :popover-options="{ offset: '-6,10' }"
        @collection="getIndexSetList"
        @selected="handleIndexSetSelected"
      ></SelectIndexSet>
      <QueryHistory @change="updateSearchParam"></QueryHistory>
    </div>
    <div class="retrieve-body">
      <div
        class="retrieve-context"
      >
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
