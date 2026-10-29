/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { reactive } from 'vue';
import { useRoute } from 'vue-router';
import { ServicesInstance } from '@/platform/services';
import useStore from '@/shared/composables/use-store';
import useLocale from '@/shared/composables/use-locale';
import * as authorityMap from '@/shared/lib/authority-map';
export type CollectionOperation =
  | 'add'
  | 'view'
  | 'status'
  | 'search'
  | 'edit'
  | 'field'
  | 'start'
  | 'stop'
  | 'delete'
  | 'clone'
  | 'storage'
  | 'clean'
  | 'masking'
  | 'report';
/** Add uses an empty row; all list actions receive the backend row. */
export interface CollectionOperationRow {
  collector_config_id?: string | number;
  index_set_id?: string | number;
  table_id?: string;
  bkdata_index_set_ids?: (string | number)[];
  permission?: Record<string, boolean>;
  status?: string;
  is_active?: boolean;
}
export interface PermissionRequest {
  action_ids: string[];
  resources: { type: string; id: string | number | undefined }[];
}
export interface CollectedItemsContext {
  spaceUid: string;
  isAllowedCreate: boolean;
  isTableLoading: boolean;
  collectProject: unknown;
  collectList: unknown[];
  pagination: { current: number; limit: number };
  leaveCurrentPage(row: CollectionOperationRow, operation: CollectionOperation): void;
  requestData(): unknown;
  stopStatusPolling(): void;
}
export function useCollectedItems(context: () => CollectedItemsContext) {
  const store = useStore();
  const route = useRoute();
  const { t } = useLocale();
  const disabledTips = reactive({
    terminated: {
      operateType: ['clone', 'storage', 'search', 'clean'] as CollectionOperation[],
      tips: t('请先完成采集接入'),
    },
    delete: t('删除前请先停用'),
  });

  async function operateHandler(row: CollectionOperationRow, operateType: CollectionOperation) {
    const model = context();
    // type: [view, status , search, edit, field, start, stop, delete]
    const isCanClick = getOperatorCanClick(row, operateType);
    if (!isCanClick) return;
    if (operateType === 'add') {
      // 新建权限控制
      if (!model.isAllowedCreate) {
        return getOptionApplyData({
          action_ids: [authorityMap.CREATE_COLLECTION_AUTH],
          resources: [
            {
              type: 'space',
              id: model.spaceUid,
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
    } else if (operateType === 'masking') {
      // if (!(row.permission?.[authorityMap.SEARCH_LOG_AUTH])) {
      //   return getOptionApplyData({
      //     action_ids: [authorityMap.SEARCH_LOG_AUTH],
      //     resources: [{
      //       type: 'indices',
      //       id: row.index_set_id,
      //     }],
      //   });
      // }
    }
    model.leaveCurrentPage(row, operateType);
  }

  function requestDeleteCollect(row: CollectionOperationRow) {
    const model = context();
    ServicesInstance.collect
      .deleteCollect({
        params: {
          collector_config_id: row.collector_config_id,
        },
      })
      .then(res => {
        if (res.result) {
          const page =
            model.collectList.length <= 1
              ? model.pagination.current > 1
                ? model.pagination.current - 1
                : 1
              : model.pagination.current;
          if (page !== model.pagination.current) {
            handlePageChange(page);
          } else {
            model.requestData();
          }
        }
      })
      .catch(() => {});
  }

  function handlePageChange(page: number) {
    const model = context();
    if (model.pagination.current !== page) {
      model.pagination.current = page;
      if (route.name === 'collection-item') {
        model.stopStatusPolling();
      }
      model.requestData();
    }
  }

  function handleLimitChange(page: number) {
    const model = context();
    if (model.pagination.limit !== page) {
      model.pagination.current = 1;
      model.pagination.limit = page;
      model.requestData();
    }
  }

  async function getOptionApplyData(paramData: PermissionRequest) {
    const model = context();
    try {
      model.isTableLoading = true;
      const res = await store.dispatch('getApplyData', paramData);
      store.commit('updateState', { authDialogData: res.data });
    } catch (err) {
      console.warn(err);
    } finally {
      model.isTableLoading = false;
    }
  }

  async function checkCreateAuth() {
    const model = context();
    try {
      const res = await store.dispatch('checkAllowed', {
        action_ids: [authorityMap.CREATE_COLLECTION_AUTH],
        resources: [
          {
            type: 'space',
            id: model.spaceUid,
          },
        ],
      });
      model.isAllowedCreate = res.isAllowed;
    } catch (err) {
      console.warn(err);
      model.isAllowedCreate = false;
    }
  }

  function getDisabledTipsMessage(row: CollectionOperationRow, operateType: CollectionOperation) {
    if (operateType === 'delete') return disabledTips.delete;
    if (operateType === 'clean' && !row.table_id) return t('请先完成采集接入');
    if (row.status === 'terminated' && disabledTips.terminated.operateType.includes(operateType))
      return disabledTips.terminated.tips;
    return '--';
  }

  function getOperatorCanClick(row: CollectionOperationRow, operateType: CollectionOperation) {
    const model = context();
    if (operateType === 'search') {
      return !(!row.is_active || (!row.index_set_id && !row.bkdata_index_set_ids!.length));
    }
    if (operateType === 'clean') {
      return !!row.table_id;
    }
    if (['storage', 'clone'].includes(operateType)) {
      return !row.status || row.table_id;
    }
    if (['stop', 'start'].includes(operateType)) {
      return (
        !(!row.status || row.status === 'running' || row.status === 'prepare' || !model.collectProject) ||
        row.is_active !== undefined
      );
    }
    if (operateType === 'delete') {
      return !(!row.status || row.status === 'running' || row.is_active || !model.collectProject);
    }
    return true;
  }

  return {
    disabledTips,
    operateHandler,
    requestDeleteCollect,
    handlePageChange,
    handleLimitChange,
    getOptionApplyData,
    checkCreateAuth,
    getDisabledTipsMessage,
    getOperatorCanClick,
  };
}
