/*
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
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import useStore from '@/hooks/use-store';
import RouteUrlResolver, { RetrieveUrlResolver } from '@/store/url-resolver';
import { useRoute, useRouter } from 'vue-router/composables';

import useResizeObserve from '../../hooks/use-resize-observe';
import RetrieveHelper, { RetrieveEvent } from '../retrieve-helper';
import $http from '@/api';

export default () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();
  const searchBarHeight = ref(0);
  const leftFieldSettingWidth = ref(0);
  const leftFieldSettingShown = ref(true);
  const isPreApiLoaded = ref(false);

  const favoriteWidth = ref(RetrieveHelper.favoriteWidth);
  const isFavoriteShown = ref(RetrieveHelper.isFavoriteShown);
  const trendGraphHeight = ref(0);

  RetrieveHelper.setScrollSelector('.v3-bklog-content');

  RetrieveHelper.on(RetrieveEvent.LEFT_FIELD_SETTING_SHOWN_CHANGE, isShown => {
    leftFieldSettingShown.value = isShown;
  })
    .on(RetrieveEvent.SEARCHBAR_HEIGHT_CHANGE, height => {
      searchBarHeight.value = height;
    })
    .on(RetrieveEvent.LEFT_FIELD_SETTING_WIDTH_CHANGE, width => {
      leftFieldSettingWidth.value = width;
    })
    .on(RetrieveEvent.FAVORITE_WIDTH_CHANGE, width => {
      favoriteWidth.value = width;
    })
    .on(RetrieveEvent.FAVORITE_SHOWN_CHANGE, isShown => {
      isFavoriteShown.value = isShown;
    })
    .on(RetrieveEvent.TREND_GRAPH_HEIGHT_CHANGE, height => {
      trendGraphHeight.value = height;
    });

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);

  const indexSetIdList = computed(() => store.state.indexItem.ids.filter(id => id?.length ?? false));

  const stickyStyle = computed(() => {
    return {
      '--top-searchbar-height': `${searchBarHeight.value}px`,
      '--left-field-setting-width': `${leftFieldSettingShown.value ? leftFieldSettingWidth.value : 0}px`,
      '--left-collection-width': `${isFavoriteShown.value ? favoriteWidth.value : 0}px`,
      '--trend-graph-height': `${trendGraphHeight.value}px`,
    };
  });

  /**
   * 用于处理收藏夹宽度变化
   * 当收藏夹展开时，需要将内容宽度设置为减去收藏夹宽度
   */
  const contentStyle = computed(() => {
    if (isFavoriteShown.value) {
      return { width: `calc(100% - ${favoriteWidth.value}px)` };
    }

    return { width: '100%' };
  });

  const setSearchMode = () => {
    const { search_mode, addition, keyword } = route.query;

    // 此时说明来自旧版URL，同时带有 addition 和 keyword
    // 这种情况下需要将 addition 转换为 keyword 进行查询合并
    // 同时设置 search_mode 为 sql
    if (!search_mode) {
      if (addition?.length > 4 && keyword?.length > 0) {
        // 这里不好做同步请求，所以直接设置 search_mode 为 sql
        router.push({ query: { ...route.query, search_mode: 'sql', addition: '[]' } });
        const resolver = new RouteUrlResolver({ route, resolveFieldList: ['addition'] });
        const target = resolver.convertQueryToStore();

        if (target.addition?.length) {
          $http
            .request('retrieve/generateQueryString', {
              data: {
                addition: target.addition,
              },
            })
            .then(res => {
              if (res.result) {
                const newKeyword = `${keyword} AND ${res.data?.querystring}`;
                router.replace({ query: { ...route.query, keyword: newKeyword, addition: [] } });
                store.commit('updateIndexItemParams', { keyword: newKeyword });
              }
            })
            .catch(err => {
              console.log(err);
            });
        }

        return;
      }

      if (keyword?.length > 0) {
        router.push({ query: { ...route.query, search_mode: 'sql' } });
        return;
      }

      router.push({ query: { ...route.query, search_mode: 'ui' } });
    }
  };

  setSearchMode();

  /**
   * 拉取索引集列表
   */
  const getIndexSetList = () => {
    return store
      .dispatch('retrieve/getIndexSetList', { spaceUid: spaceUid.value, bkBizId: bkBizId.value })
      .then(resp => {
        isPreApiLoaded.value = true;

        // 如果当前地址参数没有indexSetId，则默认取第一个索引集
        // 同时，更新索引信息到store中
        if (!indexSetIdList.value.length) {
          const defaultId = `${resp[1][0].index_set_id}`;
          store.commit('updateIndexItem', { ids: [defaultId], items: [resp[1][0]] });
          store.commit('updateIndexId', defaultId);

          router.replace({
            params: { indexId: defaultId },
            query: { ...route.query, unionList: undefined },
          });
        }

        // 如果解析出来的索引集信息不为空
        // 需要检查索引集列表中是否包含解析出来的索引集信息
        // 避免索引信息不存在导致的频繁错误请求和异常提示
        const emptyIndexSetList = [];
        if (indexSetIdList.value.length) {
          indexSetIdList.value.forEach(id => {
            if (!resp[1].some(item => `${item.index_set_id}` === `${id}`)) {
              emptyIndexSetList.push(id);
            }
          });

          if (emptyIndexSetList.length) {
            store.commit('updateIndexItem', { ids: [], items: [] });
            store.commit('updateIndexId', '');
            store.commit('updateIndexSetQueryResult', {
              is_error: true,
              exception_msg: `index-set-not-found:(${emptyIndexSetList.join(',')})`,
            });
          }
        }

        if (emptyIndexSetList.length === 0) {
          RetrieveHelper.setSearchingValue(true);

          const type = route.params.indexId ? 'single' : 'union';
          RetrieveHelper.setIndexsetId(store.state.indexItem.ids, type);

          store.dispatch('requestIndexSetFieldInfo').then(() => {
            store.dispatch('requestIndexSetQuery').then(() => {
              RetrieveHelper.setSearchingValue(false);
            });
            RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
          });
        }
      });
  };

  // 解析默认URL为前端参数
  // 这里逻辑不要动，不做解析会导致后续前端查询相关参数的混乱
  const setDefaultRouteUrl = () => {
    const routeParams = store.getters.retrieveParams;
    const resolver = new RetrieveUrlResolver({
      ...routeParams,
      datePickerValue: store.state.indexItem.datePickerValue,
    });

    router.replace({ query: { ...route.query, ...resolver.resolveParamsToUrl() } });
  };

  const beforeMounted = () => {
    setDefaultRouteUrl();
    getIndexSetList();
  };

  beforeMounted();

  const handleSpaceIdChange = () => {
    store.commit('resetIndexsetItemParams');
    store.commit('updateIndexId', '');
    store.commit('updateUnionIndexList', []);
    RetrieveHelper.setIndexsetId([], null);

    getIndexSetList();
    store.dispatch('requestFavoriteList');
  };

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

  /** 开始处理滚动容器滚动时，收藏夹高度 */

  // 顶部二级导航高度，这个高度是固定的
  const subBarHeight = ref(64);

  // 计算滚动时二级导航和检索栏高度差
  // 这个高度差用来判定是够需要字段设置栏进行吸顶
  const paddingTop = ref(0);

  // 滚动容器高度
  const scrollContainerHeight = ref(0);

  // 滚动时，检索结果距离顶部高度
  const searchResultTop = ref(0);

  RetrieveHelper.on(RetrieveEvent.GLOBAL_SCROLL, event => {
    const scrollTop = (event.target as HTMLElement).scrollTop;
    paddingTop.value = scrollTop > subBarHeight.value ? subBarHeight.value : scrollTop;

    const diff = subBarHeight.value + trendGraphHeight.value;
    searchResultTop.value = scrollTop > diff ? diff : scrollTop;
  });

  useResizeObserve(
    RetrieveHelper.getScrollSelector(),
    entry => {
      scrollContainerHeight.value = (entry.target as HTMLElement).offsetHeight;
    },
    0,
  );

  /**
   * 计算检索内容的滚动位置，监听是否滚动到顶部
   */
  const isSearchContextStickyTop = computed(() => {
    return paddingTop.value === subBarHeight.value;
  });

  /**
   * 计算检索结果列表的滚动位置，监听是否滚动到顶部
   */
  const isSearchResultStickyTop = computed(() => {
    return searchResultTop.value === subBarHeight.value + trendGraphHeight.value;
  });

  /** * 结束计算 ***/
  onMounted(() => {
    RetrieveHelper.onMounted();
    store.dispatch('requestFavoriteList');
  });

  onUnmounted(() => {
    RetrieveHelper.destroy();
  });

  return {
    isSearchContextStickyTop,
    isSearchResultStickyTop,
    stickyStyle,
    contentStyle,
    isFavoriteShown,
    isPreApiLoaded,
  };
};
