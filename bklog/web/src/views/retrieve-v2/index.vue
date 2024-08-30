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
  import { computed, onMounted, ref, watch, set } from 'vue';
  import { isEqual } from 'lodash';

  import dayjs from 'dayjs';
  import { updateTimezone } from '../../language/dayjs';
  // import * as authorityMap from '@/common/authority-map';
  import useStore from '@/hooks/use-store';
  import { useRoute, useRouter } from 'vue-router/composables';

  import CollectFavorites from './collect/collect-index';
  import TabPanel from './tab-panel/index.vue';
  // import { getDefaultRetrieveParams } from './const';
  import SearchBar from './search-bar/index.vue';
  import SubBar from './sub-bar/index.vue';

  const store = useStore();
  const router = useRouter();
  const route = useRoute();

  const showFavorites = ref(false);
  const favoriteRef = ref(null);
  const favoriteWidth = ref(240);

  const datePickerValue = ref(['now-15m', 'now']);
  const timeZone = ref(dayjs.tz.guess());
  // const retrieveParams = ref({
  //   bk_biz_id: store.state.bkBizId,
  //   ...getDefaultRetrieveParams(),
  // });

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);
  const indexItem = computed(() => store.state.indexItem ?? {});

  const getIndexSetList = () => {
    store.dispatch('retrieve/getIndexSetList', { spaceUid: spaceUid.value, bkBizId: bkBizId.value }).then(resp => {
      store.dispatch('updateIndexItemByRoute', { route, list: resp[1] });
    });
  };

  const setRouteParams = () => {
    const { ids, isUnionIndex } = indexItem.value;
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
    indexItem.value,
    () => {
      setRouteParams();
      const { ids = [] } = indexItem.value ?? {};
      if (ids.length) {
        store.dispatch('requestIndexSetFieldInfo');
      }
    },
    { immediate: true, deep: true },
  );

  watch(
    spaceUid,
    () => {
      const routeQuery = route.query ?? {};
      if (routeQuery.spaceUid !== spaceUid || routeQuery.bizId !== bkBizId.value) {
        router.replace({
          query: {
            ...routeQuery,
            spaceUid: spaceUid.value,
            bizId: bkBizId.value,
          },
        });
      }
      getIndexSetList();
    },
    { immediate: true },
  );

  const initFavoriteState = () => {
    // const isOpen = localStorage.getItem('isAutoShowCollect') === 'true';
    // if (!isOpen) {
    //   showFavorites.value = true;
    //   favoriteWidth.value = 240;
    // }
  };

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
  const handleClickFavorite = v => {};

  onMounted(() => {
    initFavoriteState();
  });
  /** 修改时区 */
  const handleTimezoneChange = timezone => {
    timezone.value = timezone;
    updateTimezone(timezone);
  };
  /** 触发重新查询 */
  const shouldRetrieve = () => {
    console.log('======= shouldRetrieve')
  }
  const activeTab = ref('origin');
</script>
<template>
  <div :class="['retrieve-v2-index', { 'show-favorites': showFavorites }]">
    <div class="sub-head">
      <div
        class="box-favorites"
        :style="{ width: `${showFavorites ? favoriteWidth : 110}px` }"
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
        class="collect-favorites"
        ref="favoriteRef"
        :is-show.sync="showFavorites"
        :width.sync="favoriteWidth"
        @handle-click-favorite="handleClickFavorite"
      ></CollectFavorites>
      <div :style="{ paddingLeft: `${showFavorites ? favoriteWidth : 0}px` }">
        <SearchBar
          :timeZone="timeZone"
          :datePickerValue="datePickerValue"
          @update:date-picker-value="value => (datePickerValue = value)"
          @timezone-change="handleTimezoneChange"
          @should-retrieve="shouldRetrieve"
        ></SearchBar>
        <div class="result-row">
          <TabPanel v-model="activeTab"></TabPanel>
        </div>
        <div class="result-row"></div>
      </div>
    </div>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
import dayjs from 'dayjs';
