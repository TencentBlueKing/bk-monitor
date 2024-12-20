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
  import RouteUrlResolver, { RetrieveUrlResolver } from '@/store/url-resolver';
  import { debounce } from 'lodash';
  import { useRoute, useRouter } from 'vue-router/composables';

  import CollectFavorites from './collect/collect-index';
  import SearchBar from './search-bar/index.vue';
  import SearchResultPanel from './search-result-panel/index.vue';
  import SearchResultTab from './search-result-tab/index.vue';
  import GraphAnalysis from './search-result-panel/graph-analysis';

  import SubBar from './sub-bar/index.vue';
  const store = useStore();
  const router = useRouter();
  const route = useRoute();

  const showFavorites = ref(false);
  const favoriteRef = ref(null);
  const favoriteWidth = ref(240);

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);

  // 解析默认URL为前端参数
  // 这里逻辑不要动，不做解析会导致后续前端查询相关参数的混乱
  store.dispatch('updateIndexItemByRoute', { route, list: [] });

  const setDefaultIndexsetId = () => {
    if (!route.params.indexId) {
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
          params: { indexId: store.state.indexId },
          query: {
            ...route.query,
            ...resolver.resolveParamsToUrl(),
          },
        });
      }
    }
  };

  /**
   * 拉取索引集列表
   */
  const getIndexSetList = () => {
    store.dispatch('retrieve/getIndexSetList', { spaceUid: spaceUid.value, bkBizId: bkBizId.value }).then(resp => {
      // 拉取完毕根据当前路由参数回填默认选中索引集
      store.dispatch('updateIndexItemByRoute', { route, list: resp[1] }).then(() => {
        setDefaultIndexsetId();
        store.dispatch('requestIndexSetFieldInfo').then(() => {
          store.dispatch('requestIndexSetQuery');
        });
      });
    });
  };

  const handleSpaceIdChange = () => {
    store.commit('resetIndexsetItemParams');
    store.commit('updateIndexId', '');
    store.commit('updateUnionIndexList', []);
    getIndexSetList();
    store.dispatch('requestFavoriteList');
  };

  handleSpaceIdChange();

  watch(spaceUid, () => {
    handleSpaceIdChange();
    const routeQuery = route.query ?? {};

    if (routeQuery.spaceUid !== spaceUid.value) {
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

  const debounceUpdateTabValue = debounce(() => {
    const isClustering = activeTab.value === 'clustering';
    router.replace({
      params: { ...(route.params ?? {}) },
      query: {
        ...(route.query ?? {}),
        tab: activeTab.value,
        ...(isClustering ? {} : { clusterParams: undefined }),
      },
    });
  }, 60);

  watch(
    () => activeTab.value,
    () => {
      debounceUpdateTabValue();
    },
    { immediate: true },
  );

  const showAnalysisTab = computed(() => activeTab.value === 'graphAnalysis');
  const activeFavorite = ref();
  const updateActiveFavorite = value => {
    activeFavorite.value = value;
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
      <SubBar
        :style="{ width: `calc(100% - ${showFavorites ? favoriteWidth : 92}px` }"
        show-favorites
      />
    </div>
    <div class="retrieve-body">
      <CollectFavorites
        ref="favoriteRef"
        class="collect-favorites"
        :is-refresh.sync="isRefreshList"
        :is-show.sync="showFavorites"
        :width.sync="favoriteWidth"
        @update-active-favorite="updateActiveFavorite"
      ></CollectFavorites>
      <div
        :style="{ paddingLeft: `${showFavorites ? favoriteWidth : 0}px` }"
        class="retrieve-context"
      >
        <SearchBar
          :active-favorite="activeFavorite"
          @height-change="handleHeightChange"
          @refresh="handleRefresh"
        ></SearchBar>
        <div
          ref="resultRow"
          :style="{ height: `calc(100vh - ${searchBarHeight + 130}px)` }"
          class="result-row"
        >
          <SearchResultTab v-model="activeTab"></SearchResultTab>
          <template v-if="showAnalysisTab">
            <GraphAnalysis></GraphAnalysis>
          </template>
          <template v-else>
            <SearchResultPanel :active-tab.sync="activeTab"></SearchResultPanel>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
<style lang="scss">
  @import './index.scss';
</style>
<style lang="scss">
  @import './segment-pop.scss';
</style>
