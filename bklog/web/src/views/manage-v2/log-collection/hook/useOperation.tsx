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

import $http from '@/api';
// import useStore from '@/hooks/use-store';
export type CardItem = {
  key: number | string;
  title: string;
  renderFn: () => any;
};

export const useOperation = () => {
  // const store = useStore();
  // const spaceUid = computed(() => store.getters.spaceUid);
  // const bkBizId = computed(() => store.getters.bkBizId);
  const tableLoading = ref(false);
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
  const handleMultipleSelected = async (params, isList = false, callback) => {
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
   * 获取存储列表数据
   * 功能：请求存储数据并按权限排序，处理加载状态和错误提示
   */
  const getStorage = async () => {
    const queryParams = { bk_biz_id: bkBizId.value };

    try {
      loading.value = true;
      const response = await $http.request('collect/getStorage', { query: queryParams });

      if (response.data) {
        // 调用通用排序函数处理数据
        storageList.value = sortByPermission(response.data);
      }
    } catch (error) {
      showMessage(error.message, 'error');
    } finally {
      loading.value = false;
    }
  };

  /**
   * 获取集群列表数据
   * 功能：请求集群数据，按权限排序，过滤平台集群，处理路由参数
   */
  const fetchPageData = async () => {
    try {
      clusterLoading.value = true;
      const clusterRes = await $http.request('/source/logList', {
        query: {
          bk_biz_id: bkBizId.value,
          scenario_id: 'es',
        },
      });

      if (clusterRes.data) {
        // 调用通用排序函数并过滤非平台集群
        clusterList.value = sortByPermission(clusterRes.data).filter(cluster => !cluster.is_platform);

        // 处理路由参数设置默认集群
        const targetClusterId = route.query.cluster;
        if (targetClusterId) {
          const numericClusterId = Number(targetClusterId);
          const isClusterValid = clusterList.value.some(cluster => cluster.storage_cluster_id === numericClusterId);

          if (isClusterValid) {
            configData.value.storage_cluster_id = numericClusterId;
          }
        }
      }
    } catch (error) {
      console.warn('获取集群列表失败:', error);
    } finally {
      clusterLoading.value = false;
    }
  };

  return {
    tableLoading,
    // 具体的方法
    cardRender,
    handleMultipleSelected,
    sortByPermission,
  };
};
