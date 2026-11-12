/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */

import { useApplicationStore } from '@/app/state/domains/application-store';
import { nextTick, onScopeDispose, watch, type WatchStopHandle } from 'vue';
import { useRouter } from 'vue-router';
import { ServicesInstance } from '@/platform/services';

import useLocale from '@/shared/composables/use-locale';
import { showClusterSelectError } from '@/shared/lib/collector-api-error';
import * as authorityMap from '@/shared/lib/authority-map';
export type StorageClusterId = string | number;
export interface StorageCluster {
  storage_cluster_id: StorageClusterId;
  is_platform: boolean;
  enable_hot_warm?: boolean;
  permission?: Record<string, boolean>;
  setup_config: {
    retention_days_default?: number;
    retention_days_max?: number;
    number_of_replicas_default?: number;
    number_of_replicas_max?: number;
    es_shards_default?: number;
    es_shards_max?: number;
  };
}
interface DayOption {
  id: string | number;
  name: string;
}
/** Explicit state and feedback owned by the collection/custom-report form. */
export interface StorageFormContext {
  bkBizId: string | number;
  curCollect?: { data_link_id?: number };
  clusterType?: string;
  formData: {
    storage_cluster_id: StorageClusterId;
    allocation_min_days: string | number;
    retention: string | number;
    storage_replies: string | number | undefined;
    es_shards: string | number | undefined;
  };
  storageList: StorageCluster[];
  clusterList: StorageCluster[];
  exclusiveList: StorageCluster[];
  selectedStorageCluster: StorageCluster;
  editStorageClusterID?: StorageClusterId;
  replicasMax: number;
  shardsMax: number;
  customRetentionDay: string;
  customHotDataDay: string;
  retentionDaysList: DayOption[];
  hotDataDaysList: DayOption[];
  globalsData: { storage_duration_time: { id: number; name: string }[] };
  basicLoading: boolean;
  $el: HTMLElement;
  messageWarn(message: string): void;
  messageError(message: string): void;
}
export function useStorageClusterForm(context: () => StorageFormContext) {
  const store = useApplicationStore();
  const router = useRouter();
  const { t } = useLocale();
  const watchers: WatchStopHandle[] = [];
  onScopeDispose(() => watchers.forEach(stop => stop()));

  async function getStorage() {
    const model = context();
    const queryData: { bk_biz_id: string | number; data_link_id?: number; cluster_type?: string } = {
      bk_biz_id: model.bkBizId,
    };
    if (model.curCollect?.data_link_id) {
      queryData.data_link_id = model.curCollect.data_link_id;
    }
    if (model.clusterType) {
      queryData.cluster_type = model.clusterType;
    }
    try {
      const res = await ServicesInstance.collect.getStorage<{ data?: StorageCluster[] }>(
        {
          query: queryData,
        },
        { catchIsShowMessage: false },
      );
      if (res.data) {
        // 根据权限排序
        const s1: StorageCluster[] = [];
        const s2: StorageCluster[] = [];
        for (const item of res.data) {
          if (item.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH]) {
            s1.push(item);
          } else {
            s2.push(item);
          }
        }
        model.storageList = s1.concat(s2);
        model.storageList.forEach(item =>
          item.is_platform ? model.clusterList.push(item) : model.exclusiveList.push(item),
        );
      }
    } catch (error) {
      showClusterSelectError(error);
    }
  }

  function enterCustomDay(val: string, type: 'retention' | 'hot') {
    const model = context();
    const numberVal = parseInt(val.trim(), 10);
    const stringVal = numberVal.toString();
    const isRetention = type === 'retention'; // 过期时间 or 热数据存储时间
    if (numberVal) {
      const maxDays = model.selectedStorageCluster.setup_config.retention_days_max || 30;
      if (numberVal > maxDays) {
        // 超过最大天数
        isRetention ? (model.customRetentionDay = '') : (model.customHotDataDay = '');
        model.messageError(t('最大自定义天数为') + maxDays);
      } else {
        if (isRetention) {
          if (!model.retentionDaysList.some(item => item.id === stringVal)) {
            model.retentionDaysList.push({
              id: stringVal,
              name: stringVal + t('天'),
            });
          }
          model.formData.retention = stringVal;
          model.customRetentionDay = '';
        } else {
          if (!model.hotDataDaysList.some(item => item.id === stringVal)) {
            model.hotDataDaysList.push({
              id: stringVal,
              name: stringVal + t('天'),
            });
          }
          model.formData.allocation_min_days = stringVal;
          model.customHotDataDay = '';
        }
        document.body.click();
      }
    } else {
      isRetention ? (model.customRetentionDay = '') : (model.customHotDataDay = '');
      model.messageError(t('请输入有效数值'));
    }
  }

  function changeCopyNumber(val: number | string) {
    const model = context();
    val === '' &&
      (model.formData.storage_replies = model.selectedStorageCluster.setup_config.number_of_replicas_default);
  }

  function changeShardsNumber(val: number | string) {
    const model = context();
    val === '' && (model.formData.es_shards = model.selectedStorageCluster.setup_config.es_shards_default);
  }

  function jumpToEsAccess() {
    const model = context();
    window.open(
      router.resolve({
        name: 'es-cluster-manage',
        query: {
          spaceUid: store.spaceUid,
        },
      }).href,
      '_blank',
      'noopener,noreferrer',
    );
  }

  async function applySearchAccess(item: StorageCluster) {
    const model = context();
    model.$el.click(); // 因为下拉在loading上面所以需要关闭下拉
    try {
      model.basicLoading = true;
      const res = await store.getApplyData({
        action_ids: [authorityMap.MANAGE_ES_SOURCE_AUTH],
        resources: [
          {
            type: 'es_source',
            id: item.storage_cluster_id,
          },
        ],
      });
      window.open(res.data.apply_url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      console.warn(err);
    } finally {
      model.basicLoading = false;
    }
  }

  function handleSelectStorageCluster(res: StorageCluster) {
    const model = context();
    // 因为有最大天数限制，不同集群限制可能不同，所以切换集群时展示默认
    const { setup_config: setupConfig } = res;
    model.formData.retention = setupConfig?.retention_days_default || '7';
    model.formData.storage_replies = setupConfig?.number_of_replicas_default || 0;
    model.formData.es_shards = setupConfig?.es_shards_default || 0;
    model.replicasMax = setupConfig?.number_of_replicas_max || 0;
    model.shardsMax = setupConfig?.es_shards_max || 1;
    model.formData.allocation_min_days = '0';
  }

  function updateDaysList() {
    const model = context();
    const retentionDaysList = [...model.globalsData.storage_duration_time].filter(item => {
      return item.id <= (model.selectedStorageCluster.setup_config.retention_days_max || 30);
    });
    model.retentionDaysList = retentionDaysList;
    model.hotDataDaysList = [...retentionDaysList];
  }

  function watchStorageCluster(newVal: StorageClusterId, oldVal: StorageClusterId) {
    const model = context();
    model.storageList.forEach(res => {
      if (res.storage_cluster_id === newVal) {
        model.selectedStorageCluster = res; // 当前选择的存储集群
        if (oldVal === '') {
          // 当oldVal为空时则表示第一次进入
          model.replicasMax = res.setup_config?.number_of_replicas_max || 0;
          model.shardsMax = res.setup_config?.es_shards_max || 1;
          if (!model.editStorageClusterID) handleSelectStorageCluster(res);
        } else {
          handleSelectStorageCluster(res);
        }
        updateDaysList();
        nextTick(() => {
          // 如果开启了冷热集群天数不能为0
          if (res.enable_hot_warm && model.formData.allocation_min_days === '0') {
            model.formData.allocation_min_days = String(res.setup_config.retention_days_default);
          }
        });
      }
    });
  }

  function watchAllocationDays(val: string | number) {
    const model = context();
    const max = model.formData.retention;
    if (Number(val) > Number(max)) {
      nextTick(() => {
        model.formData.allocation_min_days = max;
        model.messageWarn(t('过期时间不能大于存储天数'));
      });
    }
  }

  /** Called in created, after Options data exists and before loading requests. */
  function startStorageWatching() {
    if (watchers.length) return;
    watchers.push(watch(() => context().formData.storage_cluster_id, watchStorageCluster));
    watchers.push(watch(() => context().formData.allocation_min_days, watchAllocationDays));
  }
  return {
    getStorage,
    enterCustomDay,
    changeCopyNumber,
    changeShardsNumber,
    jumpToEsAccess,
    applySearchAccess,
    handleSelectStorageCluster,
    updateDaysList,
    startStorageWatching,
  };
}
