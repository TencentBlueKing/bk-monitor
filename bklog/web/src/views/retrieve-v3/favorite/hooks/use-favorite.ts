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

import { computed, ref } from 'vue';

import useStore from '@/hooks/use-store';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { debounce } from 'lodash-es';
import { useRoute, useRouter } from 'vue-router/composables';

import { copyMessage } from '../../../../common/util';
import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '../../../../store/store.type';
import RetrieveHelper from '../../../retrieve-helper';
import { handleApiError, showMessage } from '../utils';
import $http from '@/api';

import type { IFavoriteItem, IGroupItem, SearchMode } from '../types';

/**
 * 收藏功能的自定义 Hook
 */
export const useFavorite = () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();

  // 响应式状态
  const favoriteLoading = ref(false);
  const activeTab = ref('origin');
  const isShowCurrentIndexList = ref(RetrieveHelper.isViewCurrentIndex);
  const searchValue = ref('');
  const isCollapseList = ref(true);
  const activeFavorite = ref<IFavoriteItem | null>(null);
  const expandedMap = ref<Record<string, boolean>>({});

  // 计算属性
  const isUnionSearch = computed(() => store.getters.isUnionSearch);
  const unionIndexList = computed(() => store.state.unionIndexList);
  const indexSetId = computed(() => `${store.getters.indexId}`);
  const favoriteList = computed(() => store.state.favoriteList || []);
  const indexSetList = computed(() => store.state.retrieve.indexSetList ?? []);

  /**
   * 过滤收藏列表数据
   */
  const filteredFavoriteList = computed(() => {
    let data = favoriteList.value ?? [];

    if (isShowCurrentIndexList.value) {
      data = data.map(({ group_id, group_name, group_type, favorites }) => ({
        group_id,
        group_name,
        group_type,
        favorites: favorites.filter(item => {
          if (isUnionSearch.value) {
            return (
              item.index_set_type === 'union' &&
              (item.index_set_ids ?? []).every(id => unionIndexList.value.includes(`${id}`))
            );
          }
          return item.index_set_type === 'single' && `${item.index_set_id}` === indexSetId.value;
        }),
      }));
    }

    // 排序逻辑
    const provideFavorite = data[0];
    const publicFavorite = data.at(-1);
    const sortFavoriteList = data.slice(1, data.length - 1).sort((a, b) => a.group_name.localeCompare(b.group_name));

    return [provideFavorite, ...sortFavoriteList, publicFavorite].filter(Boolean);
  });

  /**
   * 根据类型过滤数据
   */
  const filterByType = (dataType: string): IGroupItem[] => {
    return filteredFavoriteList.value.map(({ group_id, group_name, group_type, favorites }) => ({
      group_id,
      group_name,
      group_type,
      favorites: favorites.filter((item: IFavoriteItem) => item.favorite_type === dataType),
    }));
  };

  const originFavoriteList = computed(() => filterByType('search'));
  const chartFavoriteList = computed(() => filterByType('chart'));

  /**
   * 当前要展示的收藏列表
   */
  const showList = computed(() => (activeTab.value === 'origin' ? originFavoriteList.value : chartFavoriteList.value));

  /**
   * 搜索过滤后的列表
   */
  const filterDataList = computed(() =>
    showList.value.map((group: IGroupItem) => ({
      ...group,
      favorites: group.favorites.filter(
        ele => ele.created_by.includes(searchValue.value) || ele.name.includes(searchValue.value),
      ),
    })),
  );

  /**
   * 搜索是否为空结果
   */
  const isSearchEmpty = computed(
    () => !!searchValue.value?.length && filterDataList.value.filter(item => item.favorites.length).length === 0,
  );

  /**
   * 获取收藏列表数据
   */
  const getFavoriteList = async (): Promise<void> => {
    try {
      favoriteLoading.value = true;
      await store.dispatch('requestFavoriteList');
    } catch (error) {
      console.error('获取收藏列表失败:', error);
    } finally {
      favoriteLoading.value = false;
    }
  };

  /**
   * 获取搜索模式
   */
  const getSearchMode = (item: IFavoriteItem): SearchMode => {
    const { addition = [], keyword = '' } = item.params || {};

    if (addition.length > 0 && keyword.length > 0) {
      return item.search_mode as SearchMode;
    }
    if (addition.length > 0) {
      return 'ui';
    }
    return 'sql';
  };

  /**
   * 设置路由参数
   */
  const setRouteParams = (item: IFavoriteItem): void => {
    const { ids, isUnionIndex } = store.state.indexItem;
    const search_mode = SEARCH_MODE_DIC[store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? 'ui';
    const unionList = store.state.unionIndexList;
    const clusterParams = store.state.clusterParams;
    const { start_time, end_time, addition, begin, size, ip_chooser, host_scopes, interval, sort_list } =
      store.getters.retrieveParams;

    const routeParams = {
      addition,
      start_time,
      end_time,
      begin,
      size,
      ip_chooser,
      host_scopes,
      interval,
      bk_biz_id: store.state.bkBizId,
      search_mode,
      sort_list,
      ids,
      isUnionIndex,
      unionList,
      clusterParams,
    };

    const params = isUnionIndex
      ? { ...route.params, indexId: undefined }
      : { ...route.params, indexId: ids?.[0] ? `${ids?.[0]}` : route.params?.indexId };

    const query = { ...route.query };

    // 使用 URL 解析器
    // const { RetrieveUrlResolver } = require('@/store/url-resolver');
    const resolver = new RetrieveUrlResolver({
      ...routeParams,
      datePickerValue: store.state.indexItem.datePickerValue,
    });

    Object.assign(query, resolver.resolveParamsToUrl(), {
      tab: item?.favorite_type === 'chart' ? 'graphAnalysis' : 'origin',
    });

    router.replace({ params, query });
  };

  /**
   * 选择收藏项
   */
  const selectFavoriteItem = (item: IFavoriteItem | null): void => {
    if (!item) {
      activeFavorite.value = null;
      let clearSearchValueNum = store.state.clearSearchValueNum;
      store.commit('updateClearSearchValueNum', (clearSearchValueNum += 1));
      setRouteParams(item);
      setTimeout(() => {
        RetrieveHelper.setFavoriteActive(activeFavorite.value);
      });
      return;
    }

    const cloneValue = structuredClone(item);
    activeFavorite.value = structuredClone(item);

    const isUnionIndex = cloneValue.index_set_ids?.length > 0;
    const keyword = cloneValue.params?.keyword || '';
    const addition = cloneValue.params?.addition ?? [];
    const search_mode = getSearchMode(cloneValue);

    // 重置状态
    store.commit('resetIndexsetItemParams');
    store.commit('updateState', { 'indexId': cloneValue.index_set_id});
    store.commit('updateIsSetDefaultTableColumn', false);
    store.commit('updateStorage', {
      [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: item.index_set_type,
      [BK_LOG_STORAGE.SEARCH_TYPE]: ['ui', 'sql'].indexOf(search_mode ?? 'ui'),
    });

    // 处理 IP 选择器
    const ip_chooser = { ...(cloneValue.params?.ip_chooser ?? {}) };
    if (isUnionIndex) {
      store.commit(
        'updateUnionIndexList',
        cloneValue.index_set_ids.map(newItem => String(newItem)),
      );
    }

    if (JSON.stringify(ip_chooser) !== '{}') {
      addition.push({
        field: '_ip-select_',
        operator: '',
        value: [ip_chooser],
      });
    }

    const ids = isUnionIndex ? cloneValue.index_set_ids : [cloneValue.index_set_id];
    store.commit('updateIndexItem', {
      keyword,
      addition,
      ip_chooser,
      index_set_id: cloneValue.index_set_id,
      ids,
      items: ids.map(id => indexSetList.value.find(newItem => newItem.index_set_id === `${id}`)),
      isUnionIndex,
      search_mode,
    });

    setRouteParams(item);
    store.commit('updateChartParams', {
      ...cloneValue.params?.chart_params,
      fromCollectionActiveTab: 'unused',
    });

    store.commit('updateIndexSetQueryResult', {
      origin_log_list: [],
      list: [],
    });

    store.dispatch('requestIndexSetFieldInfo').then(() => {
      RetrieveHelper.setFavoriteActive({ ...activeFavorite.value, search_mode });
      store.dispatch('requestIndexSetQuery');
    });
  };

  /**
   * 切换展开状态
   */
  const toggleExpand = (groupId: number | string): void => {
    const key = String(groupId);
    expandedMap.value[key] = !expandedMap.value[key];
  };

  /**
   * 防抖搜索
   */
  const debouncedSearch = debounce((value: string) => {
    searchValue.value = value;
  }, 300);

  /**
   * 处理搜索输入
   */
  const handleSearchInput = (value: string): void => {
    debouncedSearch(value);
  };

  /**
   * 创建或更新分组名
   * @param groupData 分组数据
   * @param spaceUid 空间UID
   * @param isCreate 是否为创建操作
   * @returns Promise
   */
  const updateGroupName = async (
    groupData: { group_id?: number | string; group_new_name: string },
    spaceUid: number,
    isCreate = true,
    callback?: (res: any) => void,
  ): Promise<void> => {
    try {
      const { group_id, group_new_name } = groupData;
      const params = { group_id };
      const data = { name: group_new_name, space_uid: spaceUid };
      const requestStr = isCreate ? 'createGroup' : 'updateGroupName';

      await $http.request(`favorite/${requestStr}`, { params, data }).then(res => {
        showMessage(window.$t('操作成功'));
        callback?.(res.data || {});
      });
    } catch (error) {
      handleApiError(error, window.$t('操作失败'));
      throw error;
    }
  };
  /** 获取当前的跳转链接 */
  const handleNewLink = (item: IFavoriteItem, type: string) => {
    // const { RetrieveUrlResolver } = require('@/store/url-resolver');
    const params = { indexId: item.index_set_id };
    const resolver = new RetrieveUrlResolver({
      ...item.params,
      addition: item.params.addition,
      search_mode: item.search_mode,
      spaceUid: item.space_uid,
      unionList: item.index_set_ids.map((newItem: string) => String(newItem)),
      isUnionIndex: item.index_set_type === 'union',
    });

    const routeData = {
      name: 'retrieve',
      params,
      query: resolver.resolveParamsToUrl(),
    };

    let shareUrl = (window as any).SITE_URL;
    if (!shareUrl.startsWith('/')) {
      shareUrl = `/${shareUrl}`;
    }
    if (!shareUrl.endsWith('/')) {
      shareUrl += '/';
    }

    shareUrl = `${window.location.origin + shareUrl}${router.resolve(routeData).href}`;
    if (type === 'new-link') {
      window.open(shareUrl, '_blank');
    } else {
      copyMessage(shareUrl, window.$t('复制分享链接成功，通过链接，可直接查询对应收藏日志。'));
    }
  };

  /** 删除分组/删除收藏 */
  const handleDeleteApi = async (type: string, id: number, callback?: () => void) => {
    const isDel = type === 'delete';
    const url = `favorite/${isDel ? 'deleteFavorite' : 'deleteGroup'}`;
    await $http
      .request(url, {
        params: isDel ? { favorite_id: id } : { group_id: id },
      })
      .then(() => {
        showMessage(isDel ? window.$t('删除成功') : window.$t('该分组已成功解散，相关收藏项已移动到 [未分组]。'));
        callback?.();
      })
      .catch(err => {
        handleApiError(err, window.$t('操作失败'));
      });
  };

  /** 克隆 */
  const handleCreateCopy = (item: IFavoriteItem, isMultiIndex: boolean, callback?: () => void) => {
    const {
      index_set_id,
      params,
      name,
      group_id,
      display_fields,
      visible_type,
      is_enable_display_fields,
      index_set_type,
      index_set_ids,
      space_uid,
    } = item;
    const { host_scopes, addition, keyword, search_fields } = params;
    const data = {
      name: `${name} ${window.$t('副本')}`,
      group_id,
      display_fields,
      visible_type,
      host_scopes,
      addition,
      keyword,
      search_fields,
      is_enable_display_fields,
      index_set_id,
      index_set_type,
      space_uid,
    };
    if (isMultiIndex) {
      Object.assign(data, {
        index_set_ids,
      });
    }
    $http
      .request('favorite/createFavorite', { data })
      .then(() => {
        showMessage(window.$t('创建成功'));
        callback?.();
      })
      .catch(err => {
        handleApiError(err, window.$t('操作失败'));
      });
  };
  /** 获取收藏详情 */
  const getFavoriteData = async (id: number, item: IFavoriteItem) => {
    try {
      const res = await $http.request('favorite/getFavorite', { params: { id } });
      Object.assign(item, {
        ...res.data,
        ...res.data.params,
      });
    } catch (err) {
      handleApiError(err, '获取收藏数据失败');
    }
  };

  /** 获取组列表 */
  const requestGroupList = async (spaceUid: number, callback?: (res: any) => void) => {
    try {
      const res = await $http.request('favorite/getGroupList', {
        query: {
          space_uid: spaceUid,
        },
      });
      callback?.(res || {});
    } catch (error) {
      handleApiError(error, '获取组列表失败');
    }
  };

  /** 修改收藏 / 移动到分组 / 从该组移除 */
  const handleUpdateFavorite = async (
    item: IFavoriteItem,
    callback: (data: any) => void,
    tips?: string,
    isGroup = true,
  ) => {
    const {
      params,
      name,
      search_mode,
      group_id,
      display_fields,
      visible_type,
      id,
      index_set_id,
      index_set_ids,
      index_set_type,
      is_enable_display_fields,
    } = item;
    const { ip_chooser, addition, keyword, search_fields } = params;
    const searchParams =
      search_mode === 'sql'
        ? { keyword, addition: [] }
        : { addition: (addition || []).filter(v => v.field !== '_ip-select_'), keyword: '*' };

    const data = {
      name,
      group_id,
      display_fields,
      visible_type,
      ip_chooser,
      addition,
      keyword,
      search_fields,
      index_set_type,
      is_enable_display_fields,
    };

    Object.assign(data, index_set_type === 'union' ? { index_set_ids } : { index_set_id });

    try {
      const res = await $http.request('favorite/updateFavorite', {
        params: { id },
        data: isGroup ? { ...data, ...searchParams } : data,
      });
      if (res.result) {
        showMessage(tips || window.$t('保存成功'));
        callback?.(res.result);
      }
    } catch (error) {
      handleApiError(error, '更新收藏失败');
    }
  };

  return {
    // 状态
    favoriteLoading,
    activeTab,
    isShowCurrentIndexList,
    searchValue,
    isCollapseList,
    activeFavorite,
    expandedMap,

    // computed属性
    isUnionSearch,
    unionIndexList,
    indexSetId,
    favoriteList,
    indexSetList,
    filteredFavoriteList,
    originFavoriteList,
    chartFavoriteList,
    showList,
    filterDataList,
    isSearchEmpty,

    // handle方法
    getFavoriteList,
    selectFavoriteItem,
    toggleExpand,
    handleSearchInput,
    setRouteParams,
    getSearchMode,
    updateGroupName,
    handleNewLink,
    handleDeleteApi,
    handleCreateCopy,
    getFavoriteData,
    requestGroupList,
    handleUpdateFavorite,
  };
};
