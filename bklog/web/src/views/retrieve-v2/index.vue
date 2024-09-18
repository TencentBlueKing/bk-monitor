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
  const indexSetParams = computed(() => store.getters.retrieveParams);

  store.dispatch('updateIndexItemByRoute', { route, list: [] });

  /**
   * 拉取索引集列表
   */
  const getIndexSetList = () => {
    store.dispatch('retrieve/getIndexSetList', { spaceUid: spaceUid.value, bkBizId: bkBizId.value }).then(resp => {
      // 拉取完毕根据当前路由参数回填默认选中索引集
      store.dispatch('updateIndexItemByRoute', { route, list: resp[1] }).then(() => {
        store.dispatch('requestIndexSetFieldInfo').then(() =>{
          store.dispatch('requestIndexSetQuery');
        });
      });
    });
  };

  const setRouteParams = () => {
    const { ids, isUnionIndex } = indexSetParams.value;
    const params = isUnionIndex ? route.params : { ...route.params, indexId: ids?.[0] };
    const query = isUnionIndex
      ? { ...route.query, unionList: encodeURIComponent(JSON.stringify(ids.map(item => String(item)))) }
      : route.query;

    if (!isEqual(params, route.params) || !isEqual(query, route.query)) {
      router.replace({
        params,
        query,
      });
    }
  };


  watch(
    indexSetParams,
    () => {
      setRouteParams();
    },
    { deep: true },
  );

  watch(
    spaceUid,
    () => {
      const routeQuery = route.query ?? {};
      if (routeQuery.spaceUid !== spaceUid.value || routeQuery.bizId !== bkBizId.value) {
        router.push({
          params: {
            indexId: undefined,
          },
          query: {
            ...routeQuery,
            spaceUid: spaceUid.value,
            bizId: bkBizId.value,
            unionList: undefined,
          },
        });
      }

      store.commit('resetIndexsetItemParams');
      store.commit('updateIndexId');

      getIndexSetList();
      store.dispatch('requestFavoriteList');
    },
    { immediate: true },
  );

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

  const handleClickFavorite = v => {
    if (!v) {
      return;
    }
    store.commit('resetIndexsetItemParams');
    store.commit('updateIndexId', v.index_set_id);
    const isUnionIndex = v.index_set_ids.length > 0;

    store.commit('updateIndexItem', {
      ...v.params,
      index_set_id: v.index_set_id,
      ids: isUnionIndex ? v.index_set_ids : [v.index_set_id],
      isUnionIndex,
    });

    store.dispatch('requestIndexSetFieldInfo');
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
        :style="{ width: `${showFavorites ? favoriteWidth : 110}px` }"
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
      <SubBar :style="{ width: `calc(100% - ${showFavorites ? favoriteWidth : 110}px` }" />
    </div>
    <div class="retrieve-body">
      <CollectFavorites
        ref="favoriteRef"
        class="collect-favorites"
        :is-refresh.sync="isRefreshList"
        :is-show.sync="showFavorites"
        :width.sync="favoriteWidth"
        @handle-click-favorite="handleClickFavorite"
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
          :style="{ height: `calc(100vh - ${searchBarHeight + 190}px)` }"
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
