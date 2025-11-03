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
import { computed, nextTick, onUnmounted, ref, watch } from 'vue';

import * as authorityMap from '@/common/authority-map';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import useStore from '@/hooks/use-store';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { useRoute, useRouter } from 'vue-router/composables';

import useResizeObserve from '../../../hooks/use-resize-observe';
import { getDefaultRetrieveParams, update_URL_ARGS } from '../../../store/default-values';
import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '../../../store/store.type';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';

export default indexSetApi => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();
  const searchBarHeight = ref(0);
  const leftFieldSettingWidth = ref(0);
  const leftFieldSettingShown = ref(true);
  const isPreApiLoaded = ref(false);

  const trendGraphHeight = ref(0);

  RetrieveHelper.setScrollSelector('.v3-bklog-content');

  const { addEvent } = useRetrieveEvent();
  addEvent(RetrieveEvent.LEFT_FIELD_SETTING_SHOWN_CHANGE, (isShown: boolean) => {
    leftFieldSettingShown.value = isShown;
  });
  addEvent(RetrieveEvent.SEARCHBAR_HEIGHT_CHANGE, (height: number) => {
    searchBarHeight.value = height;
  });
  addEvent(RetrieveEvent.LEFT_FIELD_SETTING_WIDTH_CHANGE, (width: number) => {
    leftFieldSettingWidth.value = width;
  });
  addEvent(RetrieveEvent.TREND_GRAPH_HEIGHT_CHANGE, (height: number) => {
    trendGraphHeight.value = height;
  });

  const indexSetIdList = computed(() => store.state.indexItem.ids.filter(id => id?.length ?? false));
  const fromMonitor = computed(() => route.query.from === 'monitor');

  const stickyStyle = computed(() => {
    return {
      '--top-searchbar-height': `${searchBarHeight.value}px`,
      '--left-field-setting-width': `${leftFieldSettingShown.value ? leftFieldSettingWidth.value : 0}px`,
      '--left-collection-width': '0px',
      '--trend-graph-height': `${trendGraphHeight.value}px`,
      '--header-height': fromMonitor.value ? '0px' : '52px',
    };
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
      Object.assign(routeParams, { ids: [`${routeParams.index_id}`], isUnionIndex: false, selectIsUnionSearch: false });
      activeTab = 'single';
    }

    if (routeParams.unionList?.length) {
      Object.assign(routeParams, { ids: [...routeParams.unionList], isUnionIndex: true, selectIsUnionSearch: true });
      activeTab = 'union';
    }

    store.commit('updateIndexItem', routeParams);
    store.commit('updateStorage', { [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: activeTab });
  };

  const getApmIndexSetList = () => {
    store.commit('retrieve/updateIndexSetLoading', true);
    store.commit('retrieve/updateIndexSetList', []);
    return indexSetApi()
      .then(res => {
        let indexSetList: Record<string, any>[] = [];
        if (res.length) {
          // 有索引集
          // 根据权限排序
          const s1: Record<string, any>[] = [];
          const s2: Record<string, any>[] = [];
          for (const item of res) {
            if (item.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
              s1.push(item);
            } else {
              s2.push(item);
            }
          }
          indexSetList = s1.concat(s2);
          // 索引集数据加工
          for (const item of indexSetList) {
            item.index_set_id = `${item.index_set_id}`;
            item.indexName = item.index_set_name;
            item.lightenName = ` (${item.indices.map(newItem => newItem.result_table_id).join(';')})`;
          }
          store.commit('retrieve/updateIndexSetList', indexSetList);
          return indexSetList;
        }
      })
      .finally(() => {
        store.commit('retrieve/updateIndexSetLoading', false);
      });
  };

  /**
   * 拉取索引集列表
   */
  const getIndexSetList = () => {
    if (!indexSetApi) {
      return;
    }
    return getApmIndexSetList().then(resp => {
      isPreApiLoaded.value = true;

      if (!resp?.length) {
        return;
      }

      // 如果当前地址参数没有indexSetId，则默认取第一个索引集
      // 同时，更新索引信息到store中
      if (!indexSetIdList.value.length) {
        const defaultId = `${resp[0].index_set_id}`;
        store.commit('updateIndexItem', { ids: [defaultId], items: [resp[0]] });
        store.commit('updateState', {'indexId': defaultId});
        router.replace({
          query: { ...route.query, indexId: defaultId, unionList: undefined },
        });
      }
      // 如果解析出来的索引集信息不为空
      // 需要检查索引集列表中是否包含解析出来的索引集信息
      // 避免索引信息不存在导致的频繁错误请求和异常提示
      const emptyIndexSetList: string[] = [];
      const indexSetItems: Record<string, any>[] = [];
      const indexSetIds: string[] = [];

      if (indexSetIdList.value.length) {
        for (const id of indexSetIdList.value) {
          const item = resp.find(indexItem => `${indexItem.index_set_id}` === `${id}`);
          if (!item) {
            emptyIndexSetList.push(id);
          }

          if (item) {
            indexSetItems.push(item);
            indexSetIds.push(id);
          }
        }

        if (emptyIndexSetList.length) {
          store.commit('updateIndexItem', { ids: [], items: [] });
          store.commit('updateState', { 'indexId': ''});
          store.commit('updateIndexSetQueryResult', {
            is_error: true,
            exception_msg: `index-set-not-found:(${emptyIndexSetList.join(',')})`,
          });
        }

        if (indexSetItems.length) {
          store.commit('updateIndexItem', { ids: [...indexSetIds], items: [...indexSetItems] });
        }
      }

      const { addition, keyword, items } = store.state.indexItem;
      // 初始化时，判断当前单选索引集是否有默认条件
      if (items.length === 1 && !addition.length && !keyword) {
        let searchMode = 'ui';
        let defaultKeyword = '';
        let defaultAddition: any[] = [];
        if (items[0]?.query_string) {
          defaultKeyword = items[0].query_string;
          searchMode = 'sql';
        } else if (items[0]?.addition) {
          defaultAddition = [...items[0].addition];
          searchMode = 'ui';
        }
        store.commit('updateStorage', { [BK_LOG_STORAGE.SEARCH_TYPE]: ['ui', 'sql'].indexOf(searchMode ?? 'ui') });
        store.commit('updateIndexItem', {
          addition: defaultAddition,
          keyword: defaultKeyword,
          search_mode: searchMode,
        });
        router.replace({
          query: {
            ...route.query,
            addition: JSON.stringify(defaultAddition),
            keyword: defaultKeyword,
            search_mode: searchMode,
          },
        });
      }

      if (emptyIndexSetList.length === 0) {
        RetrieveHelper.setSearchingValue(true);

        const type = route.query.indexId ? 'single' : 'union';
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

  reoverRouteParams();
  const beforeMounted = () => {
    getIndexSetList();
  };

  beforeMounted();

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

  watch(
    () => isPreApiLoaded.value,
    val => {
      if (val) {
        nextTick(() => {
          RetrieveHelper.onMounted();
        });
      }
    },
    { immediate: true },
  );

  onUnmounted(() => {
    RetrieveHelper.destroy();
  });

  return {
    isSearchContextStickyTop,
    isSearchResultStickyTop,
    stickyStyle,
    isPreApiLoaded,
    getIndexSetList,
    setDefaultRouteUrl,
  };
};
