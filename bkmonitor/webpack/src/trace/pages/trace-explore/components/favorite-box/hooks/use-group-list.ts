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
import { computed, onBeforeUnmount, shallowRef, watch } from 'vue';

import { useStorage } from '@vueuse/core';
import _ from 'lodash';
import { listByGroupFavorite } from 'monitor-api/modules/model';

import { FAVORITE_SORT_TYPE_KEY, VIEW_DATA_ID_KEY } from '../constants';
import { GROUP_ID_NOT } from '../constants';
import useEventFavoriteDataId from './use-event-favorite-data-id';

import type { IFavoriteGroup } from '../types';

const isLoading = shallowRef(false);
const groupList = shallowRef<IFavoriteGroup[]>([]);
const groupListMemo = shallowRef<IFavoriteGroup[]>([]);

let isInit = false;

export default (type: string) => {
  const orderType = useStorage(FAVORITE_SORT_TYPE_KEY, 'asc');
  const isFilterByDataId = useStorage(VIEW_DATA_ID_KEY, false);
  const eventFavoriteDataId = useEventFavoriteDataId();

  const calcGroupList = () => {
    const removeNotGroup = (list: IFavoriteGroup[]) => {
      if (list.length > 2) {
        return list;
      }
      return list.reduce<IFavoriteGroup[]>((result, groupItem) => {
        if (groupItem.id === GROUP_ID_NOT && groupItem.favorites.length < 1) {
          return result;
        }
        result.push(groupItem);
        return result;
      }, []);
    };
    if (type !== 'event') {
      groupList.value = removeNotGroup(groupListMemo.value);
      return;
    }
    if (!eventFavoriteDataId.value) {
      groupList.value = removeNotGroup(groupListMemo.value);
      return;
    }
    groupList.value = removeNotGroup(
      (groupListMemo.value as IFavoriteGroup<'event'>[]).reduce<IFavoriteGroup<'event'>[]>((result, groupItem) => {
        result.push({
          ...groupItem,
          favorites: _.filter(
            groupItem.favorites,
            favoriteItem => favoriteItem.config.queryConfig?.result_table_id === eventFavoriteDataId.value
          ),
        });
        return result;
      }, [])
    );
  };

  const allFavoriteList = computed(() =>
    groupList.value.reduce<IFavoriteGroup['favorites']>((result, item) => {
      return result.concat(item.favorites);
    }, [])
  );
  const wholeFavoriteList = computed(() =>
    groupListMemo.value.reduce<IFavoriteGroup['favorites']>((result, item) => {
      return result.concat(item.favorites);
    }, [])
  );

  const editableGroupList = computed(() => _.filter(groupList.value, item => item.id !== null));

  const fetchGroupList = async () => {
    isLoading.value = true;
    try {
      const data = await listByGroupFavorite({
        type,
        order_type: orderType.value,
      });
      groupListMemo.value = data;
      calcGroupList();
    } finally {
      isLoading.value = false;
    }
  };

  if (!isInit) {
    isInit = true;
    fetchGroupList();
    watch(isFilterByDataId, () => {
      calcGroupList();
    });
    onBeforeUnmount(() => {
      isInit = false;
      isLoading.value = true;
      groupList.value = [];
    });
  }

  return {
    run: fetchGroupList,
    loading: isLoading,
    data: groupList,
    allFavoriteList,
    editableGroupList,
    wholeFavoriteList,
  };
};
