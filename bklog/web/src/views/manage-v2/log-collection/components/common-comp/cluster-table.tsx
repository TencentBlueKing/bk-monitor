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

import { computed, defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';

import { formatFileSize } from '@/common/util';
import useLocale from '@/hooks/use-locale';

import './cluster-table.scss';

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
  },

  emits: ['choose'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const clusterSelect = ref(null);
    const getPercent = row => {
      return (100 - row.storage_usage) / 100;
    };
    /** 选中集群 */
    const handleSelectCluster = row => {
      emit('choose', row);
    };

    /** 集群表格 */
    const renderClusterTable = () => (
      <div class='cluster-content-table'>
        <bk-table
          class='cluster-table'
          data={props.clusterList}
          on-row-click={handleSelectCluster}
        >
          <bk-table-column
            scopedSlots={{
              default: ({ row }) => (
                <bk-radio checked={clusterSelect.value === row.storage_cluster_id}>
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
                    ></bk-progress>
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

    /** 集群说明 */
    const renderClusterDesc = () => (
      <div class='cluster-content-desc'>
        <div class='desc-title'>{t('集群说明')}</div>
        <div class='desc-content'>
          <div class='desc-content-item'>
            <span class='item-title'>{t('副本数量')}：</span>
            <span class='item-desc'>最大 0 个</span>
          </div>
          <div class='desc-content-item'>
            <span class='item-title'>{t('过期时间')}：</span>
            <span class='item-desc'>最大 14 天</span>
          </div>
          <div class='desc-content-item'>
            <span class='item-title'>{t('集群备注')}：</span>
            <span class='item-desc'>
              该集群用于接入日志量不大的业务日志场景 对于日志量大的业务，请申请独立 ES，避免影响公共 ES 限制：1.
              30台以下免审批 2. 副本数为 0 ，没有数据冗余 3. 无法使用日志归档功能
            </span>
          </div>
        </div>
      </div>
    );
    return () => (
      <div class='cluster-table-box'>
        {renderClusterTable()}
        {renderClusterDesc()}
      </div>
    );
  },
});
