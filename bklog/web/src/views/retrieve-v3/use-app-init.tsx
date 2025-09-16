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

import { VIEW_BUSINESS } from '@/common/authority-map';
import useResizeObserve from '@/hooks/use-resize-observe';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import useStore from '@/hooks/use-store';
import { getDefaultRetrieveParams, update_URL_ARGS } from '@/store/default-values';
import { BK_LOG_STORAGE, RouteParams, SEARCH_MODE_DIC } from '@/store/store.type';
import RouteUrlResolver, { RetrieveUrlResolver } from '@/store/url-resolver';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';
import { useRoute, useRouter } from 'vue-router/composables';

import $http from '@/api';

export default () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();
  const searchBarHeight = ref(0);
  const isPreApiLoaded = ref(false);

  const favoriteWidth = ref(RetrieveHelper.favoriteWidth);
  const isFavoriteShown = ref(RetrieveHelper.isFavoriteShown);
  const trendGraphHeight = ref(0);

  const leftFieldSettingWidth = computed(() => {
    const { width, show } = store.state.storage[BK_LOG_STORAGE.FIELD_SETTING];
    return show ? width : 0;
  });

  /**
   * 解析地址栏参数
   * 在其他模块跳转过来时，这里需要解析路由参数
   * 更新相关参数到store
   */
  const reoverRouteParams = () => {
    update_URL_ARGS(route);
    const routeParams = getDefaultRetrieveParams({
      spaceUid: store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID],
      bkBizId: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
      search_mode: SEARCH_MODE_DIC[store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? 'ui',
    });
    let activeTab = 'single';
    Object.assign(routeParams, { ids: [] });

    if (/^-?\d+$/.test(routeParams.index_id)) {
      Object.assign(routeParams, {
        ids: [`${routeParams.index_id}`],
        isUnionIndex: false,
        selectIsUnionSearch: false,
      });
      activeTab = 'single';
    }

    if (routeParams.unionList?.length) {
      Object.assign(routeParams, {
        ids: [...routeParams.unionList],
        isUnionIndex: true,
        selectIsUnionSearch: true,
      });
      activeTab = 'union';
    }

    store.commit('updateIndexItem', routeParams);
    store.commit('updateSpace', routeParams.spaceUid);
    store.commit('updateState', { indexId: routeParams.index_id });
    store.commit('updateStorage', { [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: activeTab });
  };

  RetrieveHelper.setScrollSelector('.v3-bklog-content');

  const handleSearchBarHeightChange = height => {
    searchBarHeight.value = height;
  };

  const handleFavoriteWidthChange = width => {
    favoriteWidth.value = width;
  };

  const hanldeFavoriteShown = isShown => {
    isFavoriteShown.value = isShown;
  };

  const handleGraphHeightChange = height => {
    trendGraphHeight.value = height;
  };

  const { addEvent } = useRetrieveEvent();
  addEvent(RetrieveEvent.SEARCHBAR_HEIGHT_CHANGE, handleSearchBarHeightChange);
  addEvent(RetrieveEvent.FAVORITE_WIDTH_CHANGE, handleFavoriteWidthChange);
  addEvent(RetrieveEvent.FAVORITE_SHOWN_CHANGE, hanldeFavoriteShown);
  addEvent(RetrieveEvent.TREND_GRAPH_HEIGHT_CHANGE, handleGraphHeightChange);

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);

  const indexSetIdList = computed(() => store.state.indexItem.ids.filter(id => id?.length ?? false));
  const fromMonitor = computed(() => route.query.from === 'monitor');

  const stickyStyle = computed(() => {
    return {
      '--top-searchbar-height': `${searchBarHeight.value}px`,
      '--left-field-setting-width': `${leftFieldSettingWidth.value}px`,
      '--left-collection-width': `${isFavoriteShown.value ? favoriteWidth.value : 0}px`,
      '--trend-graph-height': `${trendGraphHeight.value}px`,
      '--header-height': fromMonitor.value ? '0px' : '52px',
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
        router.push({
          query: { ...route.query, search_mode: 'sql', addition: '[]' },
        });
        const resolver = new RouteUrlResolver({
          route,
          resolveFieldList: ['addition'],
        });
        const target = resolver.convertQueryToStore<RouteParams>();

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
                router.replace({
                  query: { ...route.query, keyword: newKeyword, addition: [] },
                });
                store.commit('updateIndexItemParams', { keyword: newKeyword });
              }
            })
            .catch(err => {
              console.error(err);
            });
        }

        return;
      }

      if (keyword?.length > 0) {
        router.push({ query: { ...route.query, search_mode: 'sql' } });
        return;
      }

      router.push({
        query: {
          ...route.query,
          search_mode: store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE] === 1 ? 'sql' : 'ui',
        },
      });
    }
  };

  setSearchMode();
  reoverRouteParams();

  /**
   * 拉取索引集列表
   */
  const getIndexSetList = () => {
    store.commit('updateIndexSetQueryResult', {
      origin_log_list: [],
      list: [],
      exception_msg: '',
      is_error: false,
    });

    return store
      .dispatch('retrieve/getIndexSetList', {
        spaceUid: spaceUid.value,
        bkBizId: bkBizId.value,
        is_group: true,
      })
      .then(resp => {
        isPreApiLoaded.value = true;

        // 在路由不带indexId的情况下 检查 unionList 和 tags 参数 是否存在联合查询索引集参数
        // tags 是 BCS索引集注入内置标签特殊检索
        if (!indexSetIdList.value.length && route.query.tags?.length) {
          const tagList = Array.isArray(route.query.tags) ? route.query.tags : route.query.tags.split(',');
          const indexSetMatch = resp[1]
            .filter(item => item.tags.some(tag => tagList.includes(tag.name)))
            .map(val => val.index_set_id);
          if (indexSetMatch.length) {
            store.commit('updateIndexItem', { ids: indexSetMatch, isUnionIndex: true, selectIsUnionSearch: true });
            store.commit('updateState', {
              unionIndexItemList: tagList,
            });
            store.commit('updateStorage', { [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: 'union' });
          }
        }

        // 如果当前地址参数没有indexSetId，则默认取缓存中的索引信息
        // 同时，更新索引信息到store中
        if (!indexSetIdList.value.length) {
          const lastIndexSetIds = store.state.storage[BK_LOG_STORAGE.LAST_INDEX_SET_ID]?.[spaceUid.value];
          if (lastIndexSetIds?.length) {
            const validateIndexSetIds = lastIndexSetIds.filter(id =>
              resp[1].some(item => `${item.index_set_id}` === `${id}`),
            );
            if (validateIndexSetIds.length) {
              store.commit('updateIndexItem', { ids: validateIndexSetIds });
              store.commit('updateStorage', {
                [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: validateIndexSetIds.length > 1 ? 'union' : 'single',
              });
            } else {
              store.commit('updateStorage', {
                [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: 'single',
              });
            }
          }
        }

        // 如果解析出来的索引集信息不为空
        // 需要检查索引集列表中是否包含解析出来的索引集信息
        // 避免索引信息不存在导致的频繁错误请求和异常提示
        const emptyIndexSetList = [];
        const indexSetItems = [];
        const indexSetIds = [];

        if (indexSetIdList.value.length) {
          indexSetIdList.value.forEach(id => {
            const item = resp[1].find(item => `${item.index_set_id}` === `${id}`);
            if (!item) {
              emptyIndexSetList.push(id);
            }

            if (item) {
              indexSetItems.push(item);
              indexSetIds.push(id);
            }
          });

          if (emptyIndexSetList.length) {
            store.commit('updateIndexItem', { ids: [], items: [] });
            store.commit('updateState', { indexId: '' });
            store.commit('updateIndexSetQueryResult', {
              is_error: true,
              exception_msg: `index-set-not-found:(${emptyIndexSetList.join(',')})`,
            });
          }

          if (indexSetItems.length) {
            store.commit('updateIndexItem', {
              ids: [...indexSetIds],
              items: [...indexSetItems],
            });
          }
        }

        // 如果经过上述逻辑，缓存中没有索引信息，则默认取第一个有数据的索引
        if (!indexSetIdList.value.length) {
          const respIndexSetList = resp[1];
          const defIndexItem =
            respIndexSetList.find(
              item => item.permission?.[VIEW_BUSINESS] && item.tags.every(tag => tag.tag_id !== 4),
            ) ?? respIndexSetList[0];
          const defaultId = [defIndexItem?.index_set_id].filter(Boolean);

          if (defaultId) {
            const strId = `${defaultId}`;
            store.commit('updateIndexItem', { ids: [strId], items: [defIndexItem].filter(Boolean) });
            store.commit('updateState', { indexId: strId });
          }
        }

        let indexId =
          store.state.storage[BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB] === 'single'
            ? store.state.indexItem.ids[0]
            : undefined;
        const unionList =
          store.state.storage[BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB] === 'union' ? store.state.indexItem.ids : undefined;

        if (emptyIndexSetList.length === 0) {
          RetrieveHelper.setSearchingValue(true);

          const type = (indexId ?? route.params.indexId) ? 'single' : 'union';
          if (indexId && type === 'single') {
            store.commit('updateState', { indexId: indexId });
            store.commit('updateUnionIndexList', { updateIndexItem: false, list: [] });
          }

          if (type === 'union') {
            store.commit('updateUnionIndexList', {
              updateIndexItem: false,
              list: [...(unionList ?? [])],
            });
          }

          store.commit('updateIndexItem', { isUnionIndex: type === 'union' });

          RetrieveHelper.setIndexsetId(store.state.indexItem.ids, type, false);

          store.dispatch('requestIndexSetFieldInfo').then(resp => {
            RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
            RetrieveHelper.fire(RetrieveEvent.LEFT_FIELD_INFO_UPDATE);

            if (
              route.query.tab === 'origin' ||
              route.query.tab === undefined ||
              route.query.tab === null ||
              route.query.tab === ''
            ) {
              if (resp?.data?.fields?.length) {
                store.dispatch('requestIndexSetQuery').then(() => {
                  RetrieveHelper.setSearchingValue(false);
                });
              }

              if (!resp?.data?.fields?.length) {
                store.commit('updateIndexSetQueryResult', {
                  is_error: true,
                  exception_msg: 'index-set-field-not-found',
                });
                RetrieveHelper.setSearchingValue(false);
              }

              return;
            }

            RetrieveHelper.setSearchingValue(false);
          });
        }

        if (!indexSetIdList.value.length) {
          const defaultId = [resp[1][0]?.index_set_id];

          if (defaultId) {
            const strId = `${defaultId}`;
            store.commit('updateIndexItem', { ids: [strId], items: [resp[1][0]] });
            store.commit('updateState', { indexId: strId });
          }
        }

        const queryTab = RetrieveHelper.routeQueryTabValueFix(
          store.state.indexItem.items?.[0],
          route.query.tab,
          store.getters.isUnionSearch,
        );

        router.replace({
          params: { ...route.params, indexId },
          query: {
            ...route.query,
            ...queryTab,
            unionList: unionList ? JSON.stringify(unionList) : undefined,
          },
        });
      });
  };

  // 解析默认URL为前端参数
  // 这里逻辑不要动，不做解析会导致后续前端查询相关参数的混乱
  const setDefaultRouteUrl = () => {
    const routeParams = store.getters.retrieveParams;
    const resolver = new RetrieveUrlResolver({
      ...routeParams,
      datePickerValue: store.state.indexItem.datePickerValue,
      spaceUid: store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID],
    });

    router.replace({
      query: { ...route.query, ...resolver.resolveParamsToUrl() },
    });
  };

  const beforeMounted = () => {
    setDefaultRouteUrl();
    getIndexSetList();
  };

  beforeMounted();

  const handleSpaceIdChange = () => {
    const { start_time, end_time, timezone, datePickerValue } = store.state.indexItem;
    store.commit('resetIndexsetItemParams', {
      start_time,
      end_time,
      timezone,
      datePickerValue,
    });
    store.commit('updateState', { indexId: '' });
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
          ...resolver.getDefUrlQuery(['start_time', 'end_time', 'format', 'interval', 'search_mode', 'timezone']),
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

  addEvent(RetrieveEvent.GLOBAL_SCROLL, event => {
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
    // 清理掉当前查询结果，避免下次进入空白展示
    store.commit('updateIndexSetQueryResult', {
      origin_log_list: [],
      list: [],
      is_error: false,
      exception_msg: '',
    });
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
