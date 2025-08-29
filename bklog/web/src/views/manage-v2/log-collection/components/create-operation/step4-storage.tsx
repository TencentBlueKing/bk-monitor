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

import useLocale from '@/hooks/use-locale';

import { useOperation } from '../../hook/useOperation';
import ClusterTable from '../business-comp/cluster-table';
import { step4Data } from './data';

import './step4-storage.scss';

export default defineComponent({
  name: 'StepStorage',

  emits: ['prev'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const { cardRender } = useOperation();
    const activeName = ref(['shared', 'exclusive']);
    const data = step4Data;
    const clusterSelect = ref(null);
    const collapseList = computed(() => [
      {
        title: t('共享集群'),
        key: 'shared',
        data: data.filter(item => item.is_platform),
      },
      {
        title: t('业务独享集群'),
        key: 'exclusive',
        tips: t('你可以随时切换所选集群，切换集群后，不会造成数据丢失。原数据将在新集群存储时长到期后自动清除。'),
        data: data.filter(item => !item.is_platform),
      },
    ]);

    const handleChooseCluster = row => {
      clusterSelect.value = row.storage_cluster_id;
    };

    /** rCollapseItem的渲染 */
    const renderCollapseItem = item => (
      <bk-collapse-item
        hide-arrow={true}
        name={item.key}
      >
        <div class='cluster-title'>
          <i class={['bk-icon icon-angle-up-fill icon-cluster', { expand: activeName.value.includes(item.key) }]} />
          <span class='title'>{item.title}</span>
          {item.tips && (
            <span class='title-tips'>
              <i class='bk-icon icon-info-circle tips-icon' />
              {t('你可以随时切换所选集群，切换集群后，不会造成数据丢失。原数据将在新集群存储时长到期后自动清除。')}
            </span>
          )}
        </div>
        <div
          class='cluster-content'
          slot='content'
        >
          <ClusterTable
            clusterList={item.data}
            clusterSelect={clusterSelect.value}
            name={item.title}
            showBizCount={item.key === 'shared'}
            on-choose={handleChooseCluster}
          />
        </div>
      </bk-collapse-item>
    );

    /** 集群选择 */
    const renderCluster = () => (
      <div class='cluster-box'>
        <bk-collapse value={activeName.value}>{collapseList.value.map(item => renderCollapseItem(item))}</bk-collapse>
      </div>
    );

    /** 存储信息 */
    const renderStorage = () => (
      <div class='storage-box'>
        <div class='link-config label-form-box'>
          <span class='label-title'>{t('索引名')}</span>
          <bk-input class='storage-input'>
            <template slot='prepend'>
              <div class='group-text'>5000140_bklog_</div>
            </template>
          </bk-input>
        </div>
        <div class='link-config label-form-box'>
          <span class='label-title'>{t('过期时间')}</span>
          <bk-input
            class='min-width'
            type='number'
          >
            <template slot='append'>
              <div class='group-text'>{t('天')}</div>
            </template>
          </bk-input>
        </div>
        <div class='link-config label-form-box'>
          <span class='label-title'>{t('副本数')}</span>
          <bk-input
            class='min-width'
            type='number'
          ></bk-input>
        </div>
        <div class='link-config label-form-box'>
          <span class='label-title'>{t('分片数')}</span>
          <bk-input
            class='min-width'
            type='number'
          ></bk-input>
        </div>
      </div>
    );
    const cardConfig = [
      {
        title: t('集群选择'),
        key: 'cluster',
        renderFn: renderCluster,
      },
      {
        title: t('存储信息'),
        key: 'storage',
        renderFn: renderStorage,
      },
    ];
    return () => (
      <div class='operation-step4-storage'>
        {cardRender(cardConfig)}
        <div class='classify-btns-fixed'>
          <bk-button
            class='mr-8'
            on-click={() => {
              emit('prev');
            }}
          >
            {t('上一步')}
          </bk-button>
          <bk-button
            class='mr-8 width-88'
            theme='primary'
          >
            {t('提交')}
          </bk-button>
          <bk-button>{t('取消')}</bk-button>
        </div>
      </div>
    );
  },
});
