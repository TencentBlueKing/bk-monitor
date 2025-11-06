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

import { computed, defineComponent, ref } from 'vue';

import { formatFileSize } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRouter } from 'vue-router/composables';

import './cluster-table.scss';

/**
 * 集群选择表格
 */

export default defineComponent({
  name: 'ClusterTable',
  props: {
    /** 集群列表 */
    clusterList: {
      type: Array,
      default: () => [],
    },
    showBizCount: {
      type: Boolean,
      default: true,
    },
    clusterSelect: {
      type: Number,
    },
    name: {
      type: String,
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['choose'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const router = useRouter();
    const store = useStore();
    const PERCENT_BASE = 100;
    const currentRow = ref(null);
    const setupConfig = ref(null);

    const getPercent = row => {
      return (PERCENT_BASE - row.storage_usage) / PERCENT_BASE;
    };
    /** 选中集群 */
    const handleSelectCluster = row => {
      setupConfig.value = row.setup_config;
      currentRow.value = row;
      emit('choose', row);
    };
    const isSelected = item => props.clusterSelect === item.storage_cluster_id;
    const isShowDesc = computed(() => props.clusterSelect && props.clusterList.find(item => isSelected(item)));

    const clusterDesc = computed(() => {
      if (!setupConfig.value || !currentRow.value) {
        return [];
      }
      const { number_of_replicas_max: replicasMax, retention_days_max: daysMax } = setupConfig.value;
      const { description, enable_hot_warm: hotWarm, enable_archive: archive } = currentRow.value;
      return [
        {
          label: t('副本数量'),
          value: t('最大 {num} 个', { num: replicasMax }),
        },
        {
          label: t('过期时间'),
          value: t('最大 {num} 天', { num: daysMax }),
        },
        {
          label: t('冷热数据'),
          value: hotWarm ? t('支持') : t('不支持'),
        },
        {
          label: t('日志归档'),
          value: archive ? t('支持') : t('不支持'),
        },
        {
          label: t('集群备注'),
          value: description || '--',
        },
      ];
    });
    const handleCreateCluster = () => {
      const newUrl = router.resolve({
        name: 'es-cluster-manage',
        query: {
          spaceUid: store.state.spaceUid,
        },
      });
      window.open(newUrl.href, '_blank');
    };
    /** 集群表格 */
    const renderClusterTable = () => (
      <div
        style={{ width: isShowDesc.value ? '58%' : '100%' }}
        class='cluster-content-table'
      >
        <bk-table
          class='cluster-table'
          v-bkloading={{ isLoading: props.loading }}
          data={props.clusterList}
          on-row-click={handleSelectCluster}
        >
          <bk-table-column
            scopedSlots={{
              default: ({ row }) => (
                <bk-radio checked={isSelected(row)}>
                  <div
                    class='overflow-tips'
                    v-bk-overflow-tips
                  >
                    <span class='cluster-name'>{row.storage_cluster_name}</span>
                  </div>
                </bk-radio>
              ),
            }}
            label={t('集群名')}
            min-width='240'
          />
          <bk-table-column
            scopedSlots={{
              default: ({ row }) => <span>{formatFileSize(row.storage_total)}</span>,
            }}
            label={t('总量')}
            min-width='90'
          />
          <bk-table-column
            scopedSlots={{
              default: ({ row }) => (
                <div class='percent'>
                  <div class='percent-progress'>
                    <bk-progress
                      percent={getPercent(row)}
                      show-text={false}
                      theme='success'
                    />
                  </div>
                  <span>{`${100 - row.storage_usage}%`}</span>
                </div>
              ),
            }}
            label={t('空闲率')}
            min-width='120'
          />
          <bk-table-column
            label={t('索引数')}
            prop='index_count'
          />
          {props.showBizCount && (
            <bk-table-column
              label={t('业务数')}
              prop='biz_count'
            />
          )}
        </bk-table>
      </div>
    );

    const renderEmpty = () => (
      <bk-exception
        class='cluster-content-empty'
        scene='part'
        type='empty'
      >
        <span>
          {t('暂无')}
          {t(props.name)}
        </span>
        <div
          class='text-wrap text-part'
          on-click={handleCreateCluster}
        >
          <span class='text-btn'>{t('创建集群')}</span>
        </div>
      </bk-exception>
    );

    /** 集群说明 */
    const renderClusterDesc = () => (
      <div class='cluster-content-desc'>
        <div class='desc-title'>{t('集群说明')}</div>
        <div class='desc-content'>
          {clusterDesc.value.map(item => (
            <div
              key={`${item.label}-${item.value}`}
              class='desc-content-item'
            >
              <span class='item-title'>{item.label}：</span>
              <span class='item-desc'>{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    );
    return () => (
      <div class='cluster-table-box'>
        {(props.clusterList || []).length === 0
          ? renderEmpty()
          : [renderClusterTable(), isShowDesc.value && renderClusterDesc()]}
      </div>
    );
  },
});
