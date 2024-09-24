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
  import { computed, ref, watch } from 'vue';

  import useStore from '@/hooks/use-store';
  import RouteUrlResolver from '@/store/url-resolver';
  import { isEqual } from 'lodash';
  import { useRoute, useRouter } from 'vue-router/composables';

  import CollectFavorites from './collect/collect-index';
  import SearchBar from './search-bar/index.vue';
  import SearchResultPanel from './search-result-panel/index.vue';
  import SearchResultTab from './search-result-tab/index.vue';

  import SubBar from './sub-bar/index.vue';

  const store = useStore();
  const router = useRouter();
  const route = useRoute();

  const showFavorites = ref(false);
  const favoriteRef = ref(null);
  const favoriteWidth = ref(240);

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);

  const routeQueryParams = computed(() => {
    const { ids, isUnionIndex, search_mode } = store.state.indexItem;
    const unionList = store.state.unionIndexList;
    return {
      ...(store.getters.retrieveParams ?? {}),
      search_mode,
      ids,
      isUnionIndex,
      unionList,
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

  const getEncodeString = val => encodeURIComponent(JSON.stringify(val));

  /**
   * 路由参数格式化字典函数
   * 不同的字段需要不同的格式化函数
   */
  const routeQueryMap = {
    host_scopes: val => {
      const isEmpty = !Object.keys(val ?? {}).some(k => {
        if (typeof val[k] === 'object') {
          return Array.isArray(val[k]) ? val[k].length : Object.keys(val[k] ?? {}).length;
        }

        return val[k]?.length;
      });

      return isEmpty ? undefined : getEncodeString(val);
    },
    start_time: () => store.state.indexItem.datePickerValue[0],
    end_time: () => store.state.indexItem.datePickerValue[1],
    keyword: val => (/^\s*\*\s*$/.test(val) ? undefined : val),
    unionList: val => {
      if (routeQueryParams.value.isUnionIndex && val?.length) {
        return getEncodeString(val);
      }

      return undefined;
    },
    default: val => {
      if (typeof val === 'object' && val !== null) {
        if (Array.isArray(val) && val.length) {
          return getEncodeString(val);
        }

        if (Object.keys(val).length) {
          return getEncodeString(val);
        }

        return undefined;
      }

      return val?.length ? val : undefined;
    },
  };

  const getRouteQueryValue = () => {
    return Object.keys(routeQueryParams.value)
      .filter(key => {
        return !['ids', 'isUnionIndex'].includes(key);
      })
      .reduce((result, key) => {
        const val = routeQueryParams.value[key];
        const valueFn = typeof routeQueryMap[key] === 'function' ? routeQueryMap[key] : routeQueryMap.default;
        const value = valueFn(val);
        return Object.assign(result, { [key]: value });
      }, {});
  };

  const setRouteParams = () => {
    const { ids, isUnionIndex } = routeQueryParams.value;
    const params = isUnionIndex
      ? { ...route.params, indexId: undefined }
      : { ...route.params, indexId: ids?.[0] ?? route.params?.indexId };

    const query = { ...route.query };

    Object.assign(query, getRouteQueryValue());
    if (!isEqual(params, route.params) || !isEqual(query, route.query)) {
      router.replace({
        params,
        query,
      });
    }
  };

  const handleSpaceIdChange = (resetParams = true) => {
    if (resetParams) {
      store.commit('resetIndexsetItemParams');
      store.commit('updateIndexId', '');
      store.commit('updateUnionIndexList', []);
    }

    getIndexSetList();
    store.dispatch('requestFavoriteList');
  };

  handleSpaceIdChange();
  store.dispatch('updateIndexItemByRoute', { route, list: [] });

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

    if (routeQuery.spaceUid !== spaceUid.value || routeQuery.bizId !== bkBizId.value) {
      const resolver = new RouteUrlResolver({ route });

      router.replace({
        params: {
          indexId: undefined,
        },
        query: {
          ...resolver.getDefUrlQuery(),
          spaceUid: spaceUid.value,
          bizId: bkBizId.value,
        },
      });
    }
  });

  const handleFavoritesClick = () => {
    if (showFavorites.value) return;
    showFavorites.value = true;
  };

  const handleFavoritesClose = e => {
    e.stopPropagation();
    showFavorites.value = false;
  };

  const handleEditFavoriteGroup = e => {
    e.stopPropagation();
    favoriteRef.value.isShowManageDialog = true;
  };

  const activeTab = ref('origin');
  const isRefreshList = ref(false);
  const searchBarHeight = ref(0);
  const resultRow = ref();
  /** 刷新收藏夹列表 */
  const handleRefresh = v => {
    isRefreshList.value = v;
  };
  const handleHeightChange = height => {
    searchBarHeight.value = height;
  };
</script>
<template>
  <div :class="['retrieve-v2-index', { 'show-favorites': showFavorites }]">
    <div class="sub-head">
      <div
        :style="{ width: `${showFavorites ? favoriteWidth : 94}px` }"
        class="box-favorites"
        @click="handleFavoritesClick"
      >
        <div
          v-if="showFavorites"
          class="collet-label"
        >
          <div class="left-info">
            <span class="collect-title">{{ $t('收藏夹') }}</span>
            <span class="collect-count">{{ favoriteRef?.allFavoriteNumber }}</span>
            <span
              class="collect-edit bklog-icon bklog-wholesale-editor"
              @click="handleEditFavoriteGroup"
            ></span>
          </div>
          <span
            class="bklog-icon bklog-collapse-small"
            @click="handleFavoritesClose"
          ></span>
        </div>
        <template v-else>
          <span :class="['bklog-icon bklog-collapse-small', { active: showFavorites }]"></span>{{ $t('收藏夹') }}
        </template>
      </div>
      <SubBar :style="{ width: `calc(100% - ${showFavorites ? favoriteWidth : 92}px` }" />
    </div>
    <div class="retrieve-body">
      <CollectFavorites
        ref="favoriteRef"
        class="collect-favorites"
        :is-refresh.sync="isRefreshList"
        :is-show.sync="showFavorites"
        :width.sync="favoriteWidth"
      ></CollectFavorites>
      <div
        :style="{ paddingLeft: `${showFavorites ? favoriteWidth : 0}px` }"
        class="retrieve-context"
      >
        <SearchBar
          @height-change="handleHeightChange"
          @refresh="handleRefresh"
        ></SearchBar>
        <div
          ref="resultRow"
          :style="{ height: `calc(100vh - ${searchBarHeight + 160}px)` }"
          class="result-row"
        >
          <SearchResultTab v-model="activeTab"></SearchResultTab>
          <SearchResultPanel :active-tab="activeTab"></SearchResultPanel>
        </div>
      </div>
    </div>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
