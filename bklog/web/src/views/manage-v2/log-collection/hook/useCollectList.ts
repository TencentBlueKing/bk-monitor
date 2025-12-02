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

// biome-ignore lint/performance/noNamespaceImport: <explanation>
import * as authorityMap from '@/common/authority-map';
import { projectManages } from '@/common/util';
import useStore from '@/hooks/use-store';
import { useRouter, useRoute } from 'vue-router/composables';

/**
 * 采集列表的自定义 Hook
 */
export const useCollectList = () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();
  const loadingStatus = ref(false);
  const isAllowedCreate = ref(null);
  const isTableLoading = ref(false);
  const spaceUid = computed(() => store.getters.spaceUid);
  const bkBizId = computed(() => store.getters.bkBizId);
  const authGlobalInfo = computed(() => store.getters['globals/authContainerInfo']);
  const isShowMaskingTemplate = computed(() => store.getters.isShowMaskingTemplate);
  const collectProject = computed(() => projectManages(store.state.topMenu, 'collection-item'));
  /**
   * 跳转到采集项列表
   */
  const goListPage = () => {
    router.push({
      name: 'collection-item-list',
      query: {
        bizId: bkBizId.value,
        spaceUid: spaceUid.value,
      },
    });
  };

  /**
   * 是否有创建权限
   */
  const checkCreateAuth = async () => {
    try {
      const res = await store.dispatch('checkAllowed', {
        action_ids: [authorityMap.CREATE_COLLECTION_AUTH],
        resources: [
          {
            type: 'space',
            id: spaceUid.value,
          },
        ],
      });
      isAllowedCreate.value = res.isAllowed;
    } catch (err) {
      console.warn(err);
      isAllowedCreate.value = false;
    }
  };
  /**
   * 获取授权数据
   * @param paramData
   */
  const getOptionApplyData = async paramData => {
    try {
      isTableLoading.value = true;
      const res = await store.dispatch('getApplyData', paramData);
      store.commit('updateAuthDialogData', res.data);
    } catch (err) {
      console.warn(err);
    } finally {
      isTableLoading.value = false;
    }
  };
  const getOperatorCanClick = (row, operateType) => {
    if (operateType === 'search') {
      return !!(row.is_active && (row.index_set_id || row.bkdata_index_set_ids.length));
    }
    if (['clean', 'storage', 'clone'].includes(operateType)) {
      return !row.status || row.table_id;
    }
    if (['stop', 'start'].includes(operateType)) {
      return (
        !(!row.status || row.status === 'running' || row.status === 'prepare' || !collectProject.value) ||
        row.is_active !== undefined
      );
    }
    if (operateType === 'delete') {
      return !(!row.status || row.status === 'running' || row.is_active || !collectProject.value);
    }
    return true;
  };
  // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: <explanation>
  const leaveCurrentPage = (row, operateType, typeKey) => {
    if (operateType === 'status' && (!loadingStatus.value || row.status === 'terminated')) {
      return; // 已停用禁止操作
    }
    if (operateType === 'status' && (!row.status || row.status === 'prepare')) {
      return operateHandler(row, 'edit', typeKey);
    }
    // running、prepare 状态不能启用、停用
    if (operateType === 'start' || operateType === 'stop') {
      if (!loadingStatus.value || row.status === 'running' || row.status === 'prepare' || !collectProject.value) {
        return;
      }
      if (operateType === 'start') {
        // 启用
        // this.toggleCollect(row);
      } else {
        // 如果是容器采集项则停用页显示状态页
        router.push({
          name: 'collectStop',
          params: {
            collectorId: row.collector_config_id || '',
          },
          query: {
            spaceUid: spaceUid.value,
          },
        });
      }
      return;
    }

    // biome-ignore lint/suspicious/noEvolvingTypes: <explanation>
    let backRoute = null;
    const params = {};
    const query = {};
    const routeMap = {
      add: 'collectAdd',
      view: 'manage-collection',
      status: 'manage-collection',
      edit: 'collectEdit',
      field: 'collectField',
      search: 'retrieve',
      clean: 'collectEdit',
      storage: 'collectEdit',
      clone: 'collectAdd',
      masking: 'collectMasking',
    };
    query.typeKey = typeKey;
    const targetRoute = routeMap[operateType];
    // 查看详情 - 如果处于未完成状态，应该跳转到编辑页面
    if (targetRoute === 'manage-collection' && !row.table_id) {
      return operateHandler(row, 'edit', typeKey);
    }
    if (
      ['manage-collection', 'collectEdit', 'collectField', 'collectStorage', 'collectMasking'].includes(targetRoute)
    ) {
      params.collectorId = row.collector_config_id;
    }
    if (operateType === 'status') {
      query.type = 'collectionStatus';
    }
    if (operateType === 'search') {
      if (!(row.index_set_id || row.bkdata_index_set_ids.length)) {
        return;
      }
      params.indexId = row.index_set_id ? row.index_set_id : row.bkdata_index_set_ids[0];
    }
    if (operateType === 'clean') {
      query.step = 2;
      params.collectorId = row.collector_config_id;
      if (row.itsm_ticket_status === 'applying') {
        return operateHandler(row, 'field', typeKey);
      }
      backRoute = route.name;
    }
    // 克隆操作需要ID进行数据回显
    if (operateType === 'clone') {
      params.collectorId = row.collector_config_id;
      query.collectorId = row.collector_config_id;
      query.type = 'clone';
    }
    if (operateType === 'masking') {
      // 直接跳转到脱敏页隐藏左侧的步骤
      query.type = 'masking';
    }
    if (operateType === 'edit') {
      if (['bkdata', 'es'].includes(typeKey)) {
        params.collectorId = row.index_set_id;
      }
    }
    if (operateType === 'storage') {
      query.step = 3;
    }

    store.commit('collect/setCurCollect', row);

    router.push({
      name: targetRoute,
      params,
      query: {
        ...query,
        spaceUid: store.state.spaceUid,
        backRoute,
      },
    });
  };

  const operateHandler = (row, operateType, typeKey) => {
    // type: [view, status , search, edit, field, start, stop, delete]
    const isCanClick = getOperatorCanClick(row, operateType);
    if (!isCanClick) {
      return;
    }
    if (operateType === 'add') {
      // 新建权限控制
      if (!isAllowedCreate.value) {
        return getOptionApplyData({
          action_ids: [authorityMap.CREATE_COLLECTION_AUTH],
          resources: [
            {
              type: 'space',
              id: spaceUid.value,
            },
          ],
        });
      }
    } else if (operateType === 'view') {
      // 查看权限
      if (!row.permission?.[authorityMap.VIEW_COLLECTION_AUTH]) {
        return getOptionApplyData({
          action_ids: [authorityMap.VIEW_COLLECTION_AUTH],
          resources: [
            {
              type: 'collection',
              id: row.collector_config_id,
            },
          ],
        });
      }
    } else if (operateType === 'search') {
      // 检索权限
      if (!row.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
        return getOptionApplyData({
          action_ids: [authorityMap.SEARCH_LOG_AUTH],
          resources: [
            {
              type: 'indices',
              id: row.index_set_id,
            },
          ],
        });
      }
    } else if (!row.permission?.[authorityMap.MANAGE_COLLECTION_AUTH]) {
      // 管理权限
      return getOptionApplyData({
        action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
        resources: [
          {
            type: 'collection',
            id: row.collector_config_id,
          },
        ],
      });
    }
    leaveCurrentPage(row, operateType, typeKey);
  };

  return {
    spaceUid,
    bkBizId,
    authGlobalInfo,
    isShowMaskingTemplate,

    checkCreateAuth,
    operateHandler,
    goListPage,
  };
};
