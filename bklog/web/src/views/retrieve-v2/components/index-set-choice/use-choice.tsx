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

import { computed, ref, set } from 'vue';

import { messageError, messageSuccess } from '@/common/bkmagic';

import $http from '../../../../api';
export type IndexSetType = 'single' | 'union';
export type IndexSetTabList = 'favorite' | 'history' | 'single' | 'union';

export default (props, { emit }) => {
  const historyLoading = ref(false);
  const historyList = ref([]);
  const favoriteLoading = ref(false);

  // 联合查询本地存储数据
  const unionListValue = ref(props.value);

  const unionFavoriteList = ref([]);
  const singleFavoriteList = computed(() => {
    if (props.type === 'single') {
      return props.list.filter(item => item.is_favorite);
    }

    return [];
  });

  const favoriteList = computed(() => {
    return [
      ...singleFavoriteList.value.map(item => ({
        item,
        index_set_id: item.index_set_id,
        index_set_name: item.index_set_name,
        index_set_type: 'single',
      })),
      ...unionFavoriteList.value.map(item => ({ ...item, index_set_type: 'union' })),
    ];
  });

  /**
   * 获取历史列表
   * @param type
   * @param space_uid
   * @returns
   */
  const requestHistoryList = () => {
    if (window?.__IS_MONITOR_TRACE__) {
      return;
    }

    if (!historyList.value.length) {
      historyLoading.value = true;
      const singleRequest = $http
        .request('unionSearch/unionHistoryList', {
          data: {
            space_uid: props.spaceUid,
            index_set_type: 'single',
          },
        })
        .then(res => {
          return res.data ?? [];
        });

      const unionRequest = $http
        .request('unionSearch/unionHistoryList', {
          data: {
            space_uid: props.spaceUid,
            index_set_type: 'union',
          },
        })
        .then(res => {
          return res.data ?? [];
        });

      return Promise.all([singleRequest, unionRequest])
        .then(resp => {
          const list: any[] = [];
          for (const rows of resp) {
            for (const row of rows) {
              list.push({ ...row, update_time: new Date(row.updated_at).getTime() });
            }
          }
          historyList.value = list.sort((a, b) => b.update_time - a.update_time).slice(0, 20);
        })
        .finally(() => {
          historyLoading.value = false;
        });
    }
  };

  /**
   * 删除历史
   * @param space_uid
   * @param index_set_type
   * @param history_id
   * @param is_delete_all
   * @returns
   */
  const deleteHistoryItem = (space_uid, index_set_type, history_id, is_delete_all = false) => {
    return $http.request('unionSearch/unionDeleteHistory', {
      data: {
        space_uid,
        index_set_type,
        history_id,
        is_delete_all,
      },
    });
  };

  /**
   * 选中值改变抛出事件
   * @param value 选中值
   * @param type 选中类型： single | union
   * @param id 选中id
   */
  const handleValueChange = (value: any, type?: 'single' | 'union', id?: number | string) => {
    unionListValue.value = value;
    emit('value-change', value, type, id);
  };

  /**
   *  历史点击
   * @param item
   * @returns
   */
  const handleHistoryItemClick = (item: any) => {
    if (item.index_set_type === 'single') {
      unionListValue.value = [`${item.index_set_id}`];
      emit('value-change', [`${item.index_set_id}`], 'single', item.id);
      return;
    }

    unionListValue.value = item.index_set_ids.map(id => `${id}`);
    emit('value-change', unionListValue.value, 'union', item.id);
  };

  /**
   *  删除历史
   * @param item
   */
  const handleDeleteHistory = (item: any) => {
    historyLoading.value = true;
    return deleteHistoryItem(props.spaceUid, item?.index_set_type, item?.id, !item)
      .then(resp => {
        if (resp.result) {
          if (item?.index_set_type === 'single') {
            const index = historyList.value.findIndex((newItem: any) => newItem.id !== item.id);
            historyList.value.splice(index, 1);
            return historyList.value;
          }

          if (item?.index_set_type === 'union') {
            const index = historyList.value.findIndex((newItem: any) => newItem.id !== item.id);
            historyList.value.splice(index, 1);
            return historyList.value;
          }

          if (!item) {
            historyList.value = [];
            return [];
          }
        }

        messageError(resp.message);
        return;
      })
      .catch(error => {
        messageError(error.message ?? error);
      })
      .finally(() => {
        historyLoading.value = false;
      });
  };

  /**
   * 联合查询：获取收藏列表
   * @returns
   */
  const getUnionFavoriteList = () => {
    if (unionFavoriteList.value.length > 0) {
      return Promise.resolve(unionFavoriteList.value);
    }

    favoriteLoading.value = true;

    $http
      .request('unionSearch/unionFavoriteList', {
        params: {
          space_uid: props.spaceUid,
        },
      })
      .then(res => {
        if (res.result) {
          unionFavoriteList.value = res.data;
          return unionFavoriteList.value;
        }

        messageError(res.message);
        return [];
      })
      .finally(() => {
        favoriteLoading.value = false;
      });
  };

  /**
   *  获取收藏列表
   * @returns
   */
  const requestFavoriteList = (type?) => {
    if (type === 'single') {
      return Promise.resolve(singleFavoriteList.value);
    }

    return getUnionFavoriteList();
  };

  /**
   *  单选收藏状态设置
   * @param id  索引集ID
   * @param is_favorite   是否收藏
   * @description 该方法用于在单选情况下设置索引集的收藏状态
   */
  const setSingleFavorite = (id: string, is_favorite = false) => {
    const target = props.list.find(item => item.index_set_id === id);
    if (target) {
      set(target, 'is_favorite', is_favorite);
      if (target.parent_node) {
        const sourceNode = target.parent_node.children.find(child => child.index_set_id === id);
        if (sourceNode) {
          set(sourceNode, 'is_favorite', is_favorite);
        }
      }
    }
  };

  /**
   * 单选取消收藏
   * @param favorite
   * @returns
   */
  const cancelSingleFavorite = (favorite: any) => {
    return $http.request('indexSet/cancelMark', {
      params: {
        index_set_id: favorite.index_set_id,
      },
    });
  };

  /**
   * 联合查询取消收藏
   * @param item
   * @returns
   */
  const cancelUnionFavorite = (item: any) => {
    return $http.request('unionSearch/unionDeleteFavorite', {
      params: {
        favorite_union_id: item.id,
      },
    });
  };

  /**
   *  取消收藏
   * @param favorite
   * @param from: 'single' 'favorite'
   * @returns
   */
  const cancelFavorite = (favorite: any, from = 'single') => {
    favoriteLoading.value = true;

    if (favorite.index_set_type === 'single') {
      return cancelSingleFavorite(favorite)
        .then(resp => {
          if (resp.result) {
            if (from === 'single') {
              setSingleFavorite(favorite.index_set_id, false);
            }

            if (from === 'favorite') {
              setSingleFavorite(favorite.index_set_id, false);
            }
            return;
          }

          messageError(resp.message);
        })
        .finally(() => {
          favoriteLoading.value = false;
        });
    }

    return cancelUnionFavorite(favorite)
      .then(resp => {
        if (resp.result) {
          const index = unionFavoriteList.value.findIndex(child => favorite.id === child.id);
          unionFavoriteList.value.splice(index, 1);
          return;
        }

        messageError(resp.message);
      })
      .finally(() => {
        favoriteLoading.value = false;
      });
  };

  /**
   * 联合查询收藏
   * @param name
   */
  const unionFavoriteGroup = (name: string) => {
    return $http
      .request('unionSearch/unionCreateFavorite', {
        data: {
          name,
          space_uid: props.spaceUid,
          index_set_ids: unionListValue.value,
        },
      })
      .then(resp => {
        if (resp.result) {
          messageSuccess('收藏成功！');
          if (unionFavoriteList.value.length > 0 && !unionFavoriteList.value.some(item => item.id === resp.data.id)) {
            unionFavoriteList.value.push(resp.data);
          }

          return true;
        }

        return false;
      });
  };

  /** 单选情况下的收藏 */
  const singleFavorite = item => {
    $http
      .request('/indexSet/mark', {
        params: {
          index_set_id: item.index_set_id,
        },
      })
      .then(() => {
        setSingleFavorite(item.index_set_id, true);
      });
  };

  const favoriteIndexSet = (args: any | string) => {
    if (props.activeId === 'single') {
      return singleFavorite(args);
    }

    if (props.activeId === 'union') {
      return unionFavoriteGroup(args);
    }
  };

  return {
    requestHistoryList,
    requestFavoriteList,
    handleDeleteHistory,
    handleHistoryItemClick,
    handleValueChange,
    cancelFavorite,
    favoriteIndexSet,
    favoriteList,
    historyList,
    historyLoading,
    favoriteLoading,
    unionListValue,
  };
};
