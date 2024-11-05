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
window.__IS_MONITOR_APM__ = true;
import { computed, ref, watch, defineProps, onMounted } from 'vue';

import useStore from '@/hooks/use-store';
import { ConditionOperator } from '@/store/condition-operator';
import RouteUrlResolver, { RetrieveUrlResolver } from '@/store/url-resolver';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { isEqual } from 'lodash';
import { useRoute, useRouter } from 'vue-router/composables';
import { updateTimezone } from '@/language/dayjs';
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
    default: null,
  },
  timezone: {
    type: String,
    default: '',
  },
  refleshImmediate: {
    type: String,
    default: ''
  }
});

const store = useStore();
const router = useRouter();
const route = useRoute();

const spaceUid = computed(() => store.state.spaceUid);
const bkBizId = computed(() => store.state.bkBizId);
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

/**
 * 拉取索引集列表
 */
const getIndexSetList = () => {
  store.dispatch('retrieve/getIndexSetList', { spaceUid: spaceUid.value, bkBizId: bkBizId.value }).then(resp => {
    // 拉取完毕根据当前路由参数回填默认选中索引集
    store.dispatch('updateIndexItemByRoute', { route, list: resp[1] }).then(() => {
      store.dispatch('requestIndexSetFieldInfo').then(() => {
        store.dispatch('requestIndexSetQuery');
      });
    });
  });
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
    datePickerValue: store.state.indexItem.datePickerValue,
  });

  Object.assign(query, resolver.resolveParamsToUrl());
  console.log(query)
  if (!isEqual(query, route.query)) {
    router.replace({
      query,
    });
  }
};

const handleSpaceIdChange = () => {
  store.commit('resetIndexsetItemParams');
  store.commit('updateIndexId', '');
  store.commit('updateUnionIndexList', []);
  getIndexSetList();
  store.dispatch('requestFavoriteList');
};


watch(
  routeQueryParams,
  () => {
    setRouteParams();
  },
  { deep: true },
);

watch(spaceUid, () => {
  handleSpaceIdChange();
  const routeQuery = route.query ?? {};
  if (routeQuery.spaceUid !== spaceUid.value) {
    const resolver = new RouteUrlResolver({ route });

    router.replace({
      query: {
        ...resolver.getDefUrlQuery(),
        spaceUid: spaceUid.value,
        bizId: bkBizId.value,
        indexId: undefined
      },
    });
  }
});

watch(
  () => props.timeRange,
  async val => {
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
  const result = handleTransformToTimestamp(props.timeRange);
  store.commit('updateIndexItemParams', { start_time: result[0], end_time: result[1], datePickerValue: props.timeRange, timezone: props.timezone });
  handleSpaceIdChange();
})
</script>
<template>
  <div class="retrieve-v2-index">
    <div class="sub-head">
      <SelectIndexSet
        :popover-options="{ offset: '-6,10' }"
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
<style scoped>
@import './monitor.scss';
</style>
