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

import { computed, defineComponent, PropType, ref, watch } from 'vue';

import http from '@/api';
import type { CleanTemplateStatus } from '@/views/manage-v2/utils/clean-template';
import useLocale from '@/hooks/use-locale';

import CollectorTable, { CleanTemplateCollectorTableRow } from './collector-table';
import './sync-slider.scss';
import useTemplateCollectors, { CleanTemplateSyncResult } from './use-template-collectors';

export type SyncCollectorItem = CleanTemplateCollectorTableRow;

export interface SyncTemplateItem {
  clean_template_id: number;
  name: string;
  related_index_set_count: number;
  status: CleanTemplateStatus;
}

export default defineComponent({
  name: 'CleanTemplateSyncSlider',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    template: {
      type: Object as PropType<SyncTemplateItem | null>,
      default: null,
    },
  },
  emits: ['close', 'complete'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const isConfirmed = ref(false);
    const isSyncing = ref(false);
    const syncResults = ref<CleanTemplateSyncResult[]>([]);
    const { collectors, isCollectorsLoading, requestCollectors, resetCollectors } = useTemplateCollectors();

    const collectorCount = computed(() => collectors.value.length);
    const canSync = computed(
      () =>
        collectorCount.value > 0 &&
        props.template?.status === 'DRAFT' &&
        !isCollectorsLoading.value &&
        !isSyncing.value,
    );
    const syncSuccessCount = computed(() => syncResults.value.filter(item => item.status === 'SUCCESS').length);
    const syncFailedCount = computed(() => syncResults.value.filter(item => item.status === 'FAILED').length);
    const tableData = computed<CleanTemplateCollectorTableRow[]>(() => {
      const resultMap = new Map(syncResults.value.map(item => [item.id, item]));
      return collectors.value.map(collector => {
        const result = resultMap.get(collector.collector_config_id);
        return {
          ...collector,
          sync_result_message: result?.message,
          sync_result_status: result?.status,
        };
      });
    });

    const handleClose = () => {
      if (!isSyncing.value) {
        emit('close');
      }
    };
    const handleConfirm = async () => {
      const cleanTemplateId = props.template?.clean_template_id;
      if (!cleanTemplateId || !canSync.value) {
        return;
      }
      isSyncing.value = true;
      try {
        const res = await http.request('clean/syncCleanTemplateCollectors', {
          params: { clean_template_id: cleanTemplateId },
        });
        if (res.result === false) {
          return;
        }
        syncResults.value = Array.isArray(res.data) ? res.data : [];
        isConfirmed.value = true;
        emit('complete');
        await requestCollectors(cleanTemplateId);
      } catch (error) {
        console.warn(error);
      } finally {
        isSyncing.value = false;
      }
    };

    const summaryList = computed(() => {
      if (isConfirmed.value) {
        return [
          { label: t('生效采集项'), value: collectorCount.value },
          { label: t('同步成功'), theme: 'success', value: syncSuccessCount.value },
          { label: t('同步失败'), theme: 'danger', value: syncFailedCount.value },
        ];
      }
      return [
        { label: t('生效采集项'), value: collectorCount.value },
        { label: t('关联索引集'), value: props.template?.related_index_set_count ?? 0 },
        { label: t('本次同步对象'), value: collectorCount.value },
      ];
    });

    watch(
      () => [props.isShow, props.template?.clean_template_id] as const,
      ([isShow, cleanTemplateId]) => {
        if (isShow) {
          isConfirmed.value = false;
          syncResults.value = [];
          requestCollectors(cleanTemplateId);
          return;
        }
        resetCollectors();
      },
    );

    return () => (
      <bk-sideslider
        width={640}
        ext-cls='clean-template-sync-slider'
        is-show={props.isShow}
        quick-close={!isSyncing.value}
        show-mask={true}
        transfer
        onAnimation-end={handleClose}
      >
        <template slot='header'>
          <div class='sync-slider-title'>
            <span class='sync-slider-title-main'>{t('一键同步')}</span>
            <span class='sync-slider-title-divider' />
            <span
              class='sync-slider-title-subtitle'
              title={props.template?.name || ''}
            >
              {props.template?.name || '--'}
            </span>
          </div>
        </template>
        <template slot='content'>
          <div
            class='clean-template-sync-content'
            v-bkloading={{ isLoading: isCollectorsLoading.value }}
          >
            {!isConfirmed.value && (
              <bk-alert
                class='sync-warning'
                type='warning'
                title={t('确认同步后，会将模板最新清洗配置同步到以下所有采集项。该操作会影响线上日志字段解析结果。')}
              />
            )}

            <div class='sync-summary'>
              {summaryList.value.map(item => (
                <div
                  key={item.label}
                  class='sync-summary-card'
                >
                  <span class='summary-label'>{item.label}</span>
                  <strong class={['summary-value', item.theme && `is-${item.theme}`]}>{item.value}</strong>
                </div>
              ))}
            </div>

            <CollectorTable
              data={tableData.value}
              showSyncResult={isConfirmed.value}
            />

            {!isConfirmed.value && (
              <div class='sync-actions'>
                <bk-button
                  disabled={!canSync.value}
                  loading={isSyncing.value}
                  theme='primary'
                  onClick={handleConfirm}
                >
                  {t('确认同步')}
                </bk-button>
                <bk-button
                  disabled={isSyncing.value}
                  onClick={handleClose}
                >
                  {t('取消')}
                </bk-button>
              </div>
            )}
          </div>
        </template>
      </bk-sideslider>
    );
  },
});
