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

import { computed, ComputedRef, ref } from 'vue';
import $http from '../../../../api';
import { messageError } from '@/common/bkmagic';
export type IndexSetType = 'single' | 'union';

export default (props, { emit }) => {
  const singleHistoryList = ref([]);
  const unionHistoryList = ref([]);
  const historyLoading = ref(false);
  const favoriteLoading = ref(false);

  const unionFavoriteList = ref([]);
  const singleFavoriteList = computed(() => {
    if (props.type === 'single') {
      return props.list.filter(item => item.is_favorite);
    }

    return [];
  });

  const favoriteList = computed(() => {
    if (props.type === 'union') {
      return unionFavoriteList.value;
    }

    return singleFavoriteList.value;
  });

  const indexSetTagList: ComputedRef<{ tag_id: number; name: string; color: string }[]> = computed(() => {
    const listMap: Map<number, { tag_id: number; name: string; color: string }> = props.list.reduce((acc, item) => {
      item.tags.forEach(tag => {
        if (!acc.has(tag.tag_id)) {
          acc.set(tag.tag_id, tag);
        }
      });

      return acc;
    }, new Map<number, { tag_id: number; name: string; color: string }>());

    return Array.from(listMap.values());
  });

  /**
   * 多选：选中操作
   * @param item
   * @param value
   */
  const handleIndexSetItemCheck = (item, value) => {
    const targetValue = [];

    // 如果是选中
    if (value) {
      props.value.forEach((v: any) => {
        targetValue.push(v);
      });
      targetValue.push(item.index_set_id);
      emit('value-change', targetValue);
      return;
    }

    // 如果是取消选中
    props.value.forEach((v: any) => {
      if (v !== item.index_set_id) {
        targetValue.push(v);
      }
    });

    emit('value-change', targetValue);
  };

  /**
   * 获取历史列表
   * @param type
   * @param space_uid
   * @returns
   */
  const getHistoryList = () => {
    if (window?.__IS_MONITOR_TRACE__) {
      return;
    }

    if (props.type === 'single' && singleHistoryList.value.length) {
      return Promise.resolve(singleHistoryList);
    }

    if (props.type === 'union' && unionHistoryList.value.length) {
      return Promise.resolve(unionHistoryList);
    }

    historyLoading.value = true;
    return $http
      .request('unionSearch/unionHistoryList', {
        data: {
          space_uid: props.spaceUid,
          index_set_type: props.type,
        },
      })
      .then(res => {
        const result = res.data ?? [];
        if (props.type === 'single') {
          singleHistoryList.value = result;
          return singleHistoryList;
        }

        unionHistoryList.value = result;
        return unionHistoryList;
      })
      .finally(() => {
        historyLoading.value = false;
      });
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
   * @param value
   */
  const handleValueChange = (value: any) => {
    emit('value-change', value);
  };

  /**
   *  历史点击
   * @param item
   * @returns
   */
  const handleHistoryItemClick = (item: any) => {
    if (props.type === 'single') {
      emit('value-change', [`${item.index_set_id}`]);
      return;
    }

    emit(
      'value-change',
      item.index_set_ids.map(id => `${id}`),
    );
  };

  /**
   *  删除历史
   * @param item
   */
  const handleDeleteHistory = (item: any) => {
    historyLoading.value = true;
    return deleteHistoryItem(props.spaceUid, props.type, item?.id, !item)
      .then(resp => {
        if (resp.result) {
          if (props.type === 'single') {
            if (item === undefined || item === null) {
              singleHistoryList.value = [];
              return singleHistoryList.value;
            }

            const index = singleHistoryList.value.findIndex((item: any) => item.id !== item.id);
            singleHistoryList.value.splice(index, 1);
            return singleHistoryList.value;
          }

          if (props.type === 'union') {
            if (item === undefined || item === null) {
              unionHistoryList.value = [];
              return unionHistoryList.value;
            }

            const index = unionHistoryList.value.findIndex((item: any) => item.id !== item.id);
            unionHistoryList.value.splice(index, 1);
            return unionHistoryList.value;
          }
        }

        messageError(resp.message);
        return undefined;
      })
      .catch(error => {
        messageError(error.message ?? error);
      })
      .finally(() => {
        historyLoading.value = false;
      });
  };

  const getUnionFavoriteList = () => {
    if (props.type === 'union' && unionFavoriteList.value.length > 0) {
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
  const getFavoriteList = () => {
    if (props.type === 'single') {
      return Promise.resolve(singleFavoriteList.value);
    }

    return getUnionFavoriteList();
  };

  const cancelSingleFavorite = (item: any) => {
    return $http.request('indexSet/cancelMark', {
      params: {
        index_set_id: item.index_set_id,
      },
    });
  };

  const cancelUnionFavorite = (item: any) => {
    return $http.request('unionSearch/unionDeleteFavorite', {
      params: {
        favorite_union_id: item.id,
      },
    });
  };

  const cancelFavorite = (item: any) => {
    favoriteLoading.value = true;

    if (props.type === 'single') {
      return cancelSingleFavorite(item)
        .then(resp => {
          if (resp.result) {
            item.is_favorite = false;
            return;
          }

          messageError(resp.message);
        })
        .finally(() => {
          favoriteLoading.value = false;
        });
    }

    return cancelUnionFavorite(item)
      .then(resp => {
        if (resp.result) {
          const index = unionFavoriteList.value.findIndex(child => item.id === child.id);
          unionFavoriteList.value.splice(index, 1);
          return;
        }

        messageError(resp.message);
      })
      .finally(() => {
        favoriteLoading.value = false;
      });
  };

  return {
    handleIndexSetItemCheck,
    getHistoryList,
    getFavoriteList,
    handleDeleteHistory,
    handleHistoryItemClick,
    handleValueChange,
    cancelFavorite,
    indexSetTagList,
    favoriteList,
    historyLoading,
    favoriteLoading,
  };
};
