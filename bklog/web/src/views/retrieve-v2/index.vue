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
  const router = useRouter();
  const route = useRoute();

  const showFavorites = ref(false);
  const favoriteList = ref([]);
  const indexSetItem = ref({});

  const activeFavoriteID = ref(-1);

  const retrieveParams = ref({
    bk_biz_id: store.state.bkBizId,
    ...getDefaultRetrieveParams(),
  });

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);
  const indexItem = computed(() => store.state.indexItem);

  const setRouteParams = (name = 'retrieve', params, query) => {
    router.replace({
      name,
      params,
      query,
    });
  };

  watch(indexItem, () => {
    const { ids } = indexItem.value;
    const indexId = ids?.[0];
    if (indexId) {
      router.push({
        params: {
          ...route.params,
          indexId
        },
        query: route.query
      })
    }
  }, { immediate: true, deep: true });

  watch(
    spaceUid,
    () => {
      const name = route.name;
      const spaceId = route.query.spaceUid;
      const bizId = route.query.bizId;

      if (name !== 'retrieve' || spaceId !== spaceUid.value || bizId !== bkBizId.value) {
        setRouteParams(
          'retrieve',
          {},
          {
            spaceUid: spaceUid.value,
            bizId: bkBizId.value,
          },
        );
      }
    },
    { immediate: true },
  );

  const handleFavoritesClick = () => {
    showFavorites.value = !showFavorites.value;
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
      <SubBar :indexSetItem="indexSetItem" />
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
