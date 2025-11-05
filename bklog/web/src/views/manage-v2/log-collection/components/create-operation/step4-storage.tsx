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

import { computed, defineComponent, onMounted, ref } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useCollectList } from '../../hook/useCollectList';
import { useOperation } from '../../hook/useOperation';
import { showMessage } from '../../utils';
import ClusterTable from '../business-comp/step4/cluster-table';
import $http from '@/api';

import './step4-storage.scss';

export default defineComponent({
  name: 'StepStorage',
  props: {
    configData: {
      type: Object,
      default: () => ({}),
    },
    scenarioId: {
      type: String,
      default: '',
    },
  },

  emits: ['prev', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const { cardRender, sortByPermission } = useOperation();
    const activeName = ref(['shared', 'exclusive']);
    const storageList = ref([]);
    const clusterSelect = ref();
    const loading = ref(false);
    const submitLoading = ref(false);
    const formData = ref({
      ...{
        storage_replies: 1,
        retention: 7,
        es_shards: 3,
        need_assessment: false,
      },
      ...props.configData,
    });
    const cleanStash = ref({});
    // 是否是编辑
    const isEdit = ref(false);
    const { bkBizId, spaceUid, goListPage } = useCollectList();
    const curCollect = computed(() => store.getters['collect/curCollect']);
    const collapseList = computed(() => [
      {
        title: t('共享集群'),
        key: 'shared',
        data: storageList.value.filter(item => item.is_platform),
      },
      {
        title: t('业务独享集群'),
        key: 'exclusive',
        tips: t('你可以随时切换所选集群，切换集群后，不会造成数据丢失。原数据将在新集群存储时长到期后自动清除。'),
        data: storageList.value.filter(item => !item.is_platform),
      },
    ]);
    const isCustomReport = computed(() => props.scenarioId === 'custom_report');

    const showGroupText = computed(() => {
      const custom =
        Number(bkBizId.value) > 0 ? `${bkBizId.value}_bklog_` : `space_${Math.abs(Number(bkBizId.value))}_bklog_`;
      return isCustomReport.value ? custom : curCollect.value.collector_config_name_en;
    });

    const prependText = computed(() => {
      return isCustomReport.value ? props.configData.collector_config_name_en : curCollect.value.table_id_prefix;
    });

    /**
     * 异步获取存储列表并按权限排序
     * 功能：请求存储数据，将有管理权限的存储项优先展示，处理加载状态和错误提示
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
     * 选择集群
     * @param row
     */
    const handleChooseCluster = row => {
      clusterSelect.value = row.storage_cluster_id;
    };
    /**
     * 获取采集项清洗缓存
     */

    const getCleanStash = async () => {
      try {
        const res = await $http.request('clean/getCleanStash', {
          params: {
            collector_config_id: curCollect.value.collector_config_id,
          },
        });
        if (res.data) {
          cleanStash.value = res.data;
        }
      } catch (error) {}
    };
    onMounted(() => {
      getStorage();
      if (!isCustomReport.value) {
        getCleanStash();
      }
    });

    /**
     * rCollapseItem的渲染
     */
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
            loading={loading.value}
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
          <bk-input
            class='storage-input'
            disabled={true}
            value={showGroupText.value}
          >
            <template slot='prepend'>
              <div class='group-text'>{prependText.value}</div>
            </template>
          </bk-input>
        </div>
        <div class='link-config label-form-box'>
          <span class='label-title'>{t('过期时间')}</span>
          <bk-input
            class='min-width'
            type='number'
            value={formData.value.retention}
            on-input={val => {
              formData.value.retention = val;
            }}
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
            value={formData.value.storage_replies}
            on-input={val => {
              formData.value.storage_replies = val;
            }}
          />
        </div>
        <div class='link-config label-form-box'>
          <span class='label-title'>{t('分片数')}</span>
          <bk-input
            class='min-width'
            type='number'
            value={formData.value.es_shards}
            on-input={val => {
              formData.value.es_shards = val;
            }}
          />
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
    /**
     * 自定义上报存储保存
     * @returns
     */
    const handleCustomSubmit = () => {
      submitLoading.value = true;
      const { collector_config_name, index_set_name } = formData.value;
      $http
        .request(`custom/${isEdit.value ? 'setCustom' : 'createCustom'}`, {
          params: {
            collector_config_id: props.configData.collectorId,
          },
          data: {
            ...props.configData,
            ...formData.value,
            collector_config_name: collector_config_name || index_set_name,
            bk_biz_id: Number(bkBizId.value),
          },
        })
        .then(res => {
          res.result && showMessage(t('保存成功'));
          emit('cancel');
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };
    /**
     * 采集场景提交
     */
    const handleNormalSubmit = () => {
      submitLoading.value = true;
      const { etl_params, etl_fields, clean_type } = cleanStash.value;

      const data = {
        etl_params,
        fields: etl_fields,
        etl_config: clean_type,
        table_id: curCollect.value.collector_config_name_en,
        storage_cluster_id: clusterSelect.value,
        ...formData.value,
        allocation_min_days: 0,
      };
      console.log(cleanStash.value, '----', formData.value, data, curCollect.value);
      $http
        .request('collect/fieldCollection', {
          params: {
            collector_config_id: curCollect.value.collector_config_id,
          },
          data,
        })
        .then(res => {
          if (res.data) {
            emit('cancel');
            store.commit('collect/updateCurCollect', { ...formData.value, ...data, ...res.data });
          }
        })
        .catch(() => {
          console.log('error');
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };
    /**
     * 保存配置
     */
    const handleSubmit = () => {
      if (!clusterSelect.value) {
        showMessage(t('请选择集群'), 'error');
        return;
      }
      if (isCustomReport.value) {
        /**
         * 自定义上报存储保存
         */
        handleCustomSubmit();
      } else {
        /**
         * 采集场景提交
         */
        handleNormalSubmit();
      }
    };
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
            class='width-88 mr-8'
            loading={submitLoading.value}
            theme='primary'
            on-click={handleSubmit}
          >
            {t('提交')}
          </bk-button>
          <bk-button
            on-click={() => {
              emit('cancel');
            }}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
