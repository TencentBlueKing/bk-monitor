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

  import * as authorityMap from '@/common/authority-map';
  import useStore from '@/hooks/use-store';
  import { useRoute, useRouter } from 'vue-router/composables';

  import CollectFavorites from './collect/collect-index';
  import { getDefaultRetrieveParams } from './const';
  import SearchBar from './search-bar/index.vue';
  import SubBar from './sub-bar/index.vue';
  import http from '@/api';

  const store = useStore();
  const route = useRoute();
  const router = useRouter();

  const showFavorites = ref(false);
  const favoriteList = ref([]);
  const indexSetList = ref([]);
  const totalFields = ref([]);

  const activeFavoriteID = ref(-1);
  const activeFavorite = ref({});
  const retrieveSearchNumber = ref(0);

  const indexId = ref(route.params.indexId?.toString());
  const retrieveParams = ref({
    bk_biz_id: store.state.bkBizId,
    ...getDefaultRetrieveParams(),
  });

  const authPageInfo = ref(null);
  const hasAuth = ref(false);

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);
  const isExternal = computed(() => store.state.isExternal);
  const externalMenu = computed(() => store.state.externalMenu);
  const authMainPageInfo = computed(() => store.getters['globals/authContainerInfo']);

  watch(
    () => spaceUid,
    () => {
      indexId.value = '';
      indexSetList.value.length = 0;
      indexSetList.value = [];

      totalFields.value.length = 0;
      totalFields.value = [];

      retrieveParams.value.bk_biz_id = bkBizId.value;
      // 外部版 无检索权限跳转后不更新页面数据
      if (!isExternal.value || (isExternal.value && externalMenu.value.includes('retrieve'))) {
        fetchPageData();
      }
      resetFavoriteValue();
      store.commit('updateUnionIndexList', []);
    },
    { immediate: true },
  );

  const handleFavoritesClick = () => {
    showFavorites.value = !showFavorites.value;
  };

  const fetchPageData = async () => {
    // 有spaceUid且有业务权限时 才去请求索引集列表
    if (!authMainPageInfo.value && spaceUid.value) {
      // 收藏侧边栏打开且 则先获取到收藏列表再获取索引集列表
      showFavorites.value && (await getFavoriteList());
      requestIndexSetList();
    }
  };

  // 初始化索引集
  const requestIndexSetList = () => {
    http
      .request('retrieve/getIndexSetList', {
        query: {
          space_uid: spaceUid.value,
        },
      })
      .then(res => {
        if (res.data.length) {
          // 有索引集
          // 根据权限排序
          const s1 = [];
          const s2 = [];
          for (const item of res.data) {
            if (item.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
              s1.push(item);
            } else {
              s2.push(item);
            }
          }
          indexSetList.value = s1.concat(s2);

          // 索引集数据加工
          indexSetList.value.forEach(item => {
            item.index_set_id = `${item.index_set_id}`;
            item.indexName = item.index_set_name;
            item.lightenName = ` (${item.indices.map(item => item.result_table_id).join(';')})`;
          });

          indexId.value = route.params.indexId?.toString();
          const routeIndexSet = indexSetList.value.find(item => item.index_set_id === indexId.value);
          const isRouteIndex = !!routeIndexSet && !routeIndexSet?.permission?.[authorityMap.SEARCH_LOG_AUTH];

          // 如果都没有权限或者路由带过来的索引集无权限则显示索引集无权限
          if (!indexSetList.value[0]?.permission?.[authorityMap.SEARCH_LOG_AUTH] || isRouteIndex) {
            const authIndexID = indexId.value || indexSetList.value[0].index_set_id;
            store
              .dispatch('getApplyData', {
                action_ids: [authorityMap.SEARCH_LOG_AUTH],
                resources: [
                  {
                    type: 'indices',
                    id: authIndexID,
                  },
                ],
              })
              .then(res => {
                authPageInfo.value = res.data;
                setRouteParams(
                  'retrieve',
                  {
                    indexId: null,
                  },
                  {
                    spaceUid: spaceUid.value,
                    bizId: bkBizId.value,
                  },
                );
              })
              .catch(err => {
                console.warn(err);
              });
            return;
          }
          hasAuth.value = true;
        }
      });
  };

  const setRouteParams = (name = 'retrieve', params, query) => {
    router.replace({
      name,
      params,
      query,
    });
  };

  /** 获取收藏列表 */
  const getFavoriteList = async () => {
    // 第一次显示收藏列表时因路由更变原因 在本页面第一次请求
    try {
      const { data } = await http.request('favorite/getFavoriteByGroupList', {
        query: {
          space_uid: spaceUid.value,
          order_type: localStorage.getItem('favoriteSortType') || 'NAME_ASC',
        },
      });
      const provideFavorite = data[0];
      const publicFavorite = data[data.length - 1];
      const sortFavoriteList = data.slice(1, data.length - 1).sort((a, b) => a.group_name.localeCompare(b.group_name));
      const sortAfterList = [provideFavorite, ...sortFavoriteList, publicFavorite];
      favoriteList.value = sortAfterList;
    } catch (err) {
      favoriteList.value = [];
    } finally {
      // 获取收藏列表后 若当前不是新检索 则判断当前收藏是否已删除 若删除则变为新检索
      if (activeFavoriteID.value !== -1) {
        for (const gItem of favoriteList.value) {
          const findFavorites = gItem.favorites.find(item => item.id === activeFavoriteID.value);
          if (!!findFavorites) {
            isFindCheckValue = true; // 找到 中断循环
            break;
          }
        }
      }
    }
  };

  const resetFavoriteValue = () => {
    activeFavorite.value = {};
    activeFavoriteID.value = -1;
    retrieveSearchNumber.value = 0; // 切换业务 检索次数设置为0;
  };
</script>
<template>
  <div :class="['retrieve-v2-index', { 'show-favorites': showFavorites }]">
    <div class="sub-head">
      <div
        class="box-favorites"
        @click="handleFavoritesClick"
      >
        <div
          v-if="showFavorites"
          class="collet-label"
        >
          <div class="left-info">
            <span class="collect-title">{{ $t('收藏夹') }}</span>
            <span class="collect-count">50</span>
            <span class="collect-edit log-icon icon-wholesale-editor"></span>
          </div>
          <span class="log-icon icon-collapse-small"></span>
        </div>
        <template v-else>
          <span :class="['log-icon icon-collapse-small', { active: showFavorites }]"></span>{{ $t('收藏夹') }}
        </template>
      </div>
      <SubBar />
    </div>
    <div class="retrieve-body">
      <CollectFavorites
        v-if="showFavorites"
        class="collect-favorites"
        :active-favorite-i-d="activeFavoriteID"
        :favorite-list="favoriteList"
        :is-show="showFavorites"
        :width="240"
      ></CollectFavorites>
      <SearchBar></SearchBar>
      <div class="result-row"></div>
      <div class="result-row"></div>
    </div>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
