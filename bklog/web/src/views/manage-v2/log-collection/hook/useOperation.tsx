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

/**
 * 新建采集的自定义 Hook
 */
import { computed, ref } from 'vue';

import * as authorityMap from '@/common/authority-map';
import useStore from '@/hooks/use-store';

import $http from '@/api';
export type CardItem = {
  key: number | string;
  title: string;
  renderFn: () => any;
};

export const useOperation = () => {
  const store = useStore();
  const spaceUid = computed(() => store.getters.spaceUid);
  // const bkBizId = computed(() => store.getters.bkBizId);
  const tableLoading = ref(false);
  /**
   * 获取采集项列表loading
   */
  const indexGroupLoading = ref(false);
  const cardRender = (cardConfig: CardItem[]) => (
    <div class='classify-main-box'>
      {cardConfig.map(item => (
        <div
          key={item.key}
          class='info-card'
        >
          <div class='card-title'>{item.title}</div>
          {item.renderFn()}
        </div>
      ))}
    </div>
  );
  /**
   * 选择采集项获取字段列表
   * @param params
   * @param isList 是否返回list
   * @returns
   */
  const handleMultipleSelected = async (params, isList = false, callback?) => {
    try {
      tableLoading.value = true;
      const res = await $http.request('/resultTables/info', params);
      const data = callback?.(res) || res.data?.fields || [];
      return isList ? res : data;
    } catch (e) {
      console.warn(e);
    } finally {
      tableLoading.value = false;
    }
  };

  /**
   * 通用权限判断函数
   * 判断项目是否拥有管理ES源的权限
   * @param {Object} item - 待判断权限的项目对象（存储项或集群）
   * @returns {boolean} 是否拥有管理权限
   */
  const hasManageEsPermission = item => {
    return item.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH];
  };
  /**
   * 按权限排序数据的通用函数
   * 将有权限的项目排在前面，无权限的排在后面
   * @param {Array} data - 待排序的数据数组
   * @returns {Array} 按权限排序后的数组
   */
  const sortByPermission = data => {
    const withPermission = [];
    const withoutPermission = [];

    for (const item of data) {
      if (hasManageEsPermission(item)) {
        withPermission.push(item);
      } else {
        withoutPermission.push(item);
      }
    }

    return [...withPermission, ...withoutPermission];
  };
  /**
   * 获取列表数据
   */
  const getIndexGroupList = callback => {
    indexGroupLoading.value = true;
    $http
      .request('collect/getIndexGroupList', {
        query: {
          space_uid: spaceUid.value,
        },
      })
      .then(res => {
        callback?.(res.data);
      })
      .catch(err => {
        console.warn(err);
      })
      .finally(() => {
        indexGroupLoading.value = false;
      });
  };

  return {
    tableLoading,
    indexGroupLoading,
    // 具体的方法
    cardRender,
    handleMultipleSelected,
    getIndexGroupList,
    sortByPermission,
  };
};
