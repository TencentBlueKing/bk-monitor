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
import { useRoute } from 'vue-router/composables';

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
    isEdit: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否为clone模式
     */
    isClone: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['prev', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();
    const { cardRender, sortByPermission } = useOperation();
    const activeName = ref(['shared', 'exclusive']);
    const storageList = ref([]);
    const clusterSelect = ref();
    const clusterData = ref({});
    const loading = ref(false);
    const submitLoading = ref(false);
    const formData = ref({
      ...{
        storage_replies: 1,
        retention: 7,
        es_shards: 3,
        need_assessment: false,
        allocation_min_days: 0,
      },
      ...props.configData,
    });
    const cleanStash = ref({});

    const bkBizId = computed(() => store.state.bkBizId);
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
    /**
     * 是否为自定义上报
     */
    const isCustomReport = computed(() => props.scenarioId === 'custom_report');
    /**
     * 最大存储天数
     */
    const daysMax = computed(() => {
      return clusterData.value?.setup_config?.retention_days_max || 7;
    });
    /**
     * 最大副本数
     */
    const numberOfReplicasMax = computed(() => {
      return clusterData.value?.setup_config?.number_of_replicas_max || 1;
    });
    /**
     * 最大分片数
     */
    const esShardsMax = computed(() => {
      return clusterData.value?.setup_config?.es_shards_max || 1;
    });

    const showGroupText = computed(() => {
      const custom =
        Number(bkBizId.value) > 0 ? `${bkBizId.value}_bklog_` : `space_${Math.abs(Number(bkBizId.value))}_bklog_`;
      return custom;
    });

    const prependText = computed(() => {
      const { table_id, collector_config_name_en } = curCollect.value;
      return (
        formData.value.table_id || table_id || collector_config_name_en || props.configData.collector_config_name_en
      );
    });

    /**
     * 是否为编辑
     */
    const isUpdate = computed(() => route.name === 'collectEdit' && props.isEdit);

    /**
     * 异步获取存储列表并按权限排序
     * 功能：请求存储数据，将有管理权限的存储项优先展示，处理加载状态和错误提示
     */
    const getStorage = async () => {
      const queryParams = { bk_biz_id: bkBizId.value };

      try {
        loading.value = true;
        const res = await $http.request('collect/getStorage', { query: queryParams });

        if (res.data) {
          // 调用通用排序函数处理数据
          storageList.value = sortByPermission(res.data);
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
      if (row.storage_cluster_id !== clusterSelect.value) {
        const { number_of_replicas_max: replicasMax, retention_days_max: daysMax } = row.setup_config;
        formData.value = {
          ...formData.value,
          storage_cluster_id: row.storage_cluster_id,
          storage_replies: replicasMax,
          retention: daysMax,
          allocation_min_days: row.enable_hot_warm ? daysMax : 0,
        };
      }
      clusterSelect.value = row.storage_cluster_id;
      clusterData.value = row;
    };
    /**
     * 获取采集项清洗缓存
     */

    const getCleanStash = async () => {
      const isStorageEdit = route.name === 'collectEdit' && route.query.step;
      let id = curCollect.value.collector_config_id;
      if (isStorageEdit) {
        id = route.params.collectorId;
      }
      try {
        const res = await $http.request('clean/getCleanStash', {
          params: {
            collector_config_id: id,
          },
        });
        if (res.data) {
          cleanStash.value = res.data;
        }
      } catch (error) {
        console.log(error);
      }
    };
    onMounted(async () => {
      initData(true);
      loading.value = true;
      const isStorageEdit = route.name === 'collectEdit' && route.query.step;
      if (isStorageEdit) {
        await $http
          .request('collect/details', {
            params: { collector_config_id: route.params.collectorId },
          })
          .then(res => {
            if (res?.data) {
              const { storage_cluster_id } = res.data;
              formData.value = {
                ...formData.value,
                ...res.data,
              };
              clusterSelect.value = storage_cluster_id;
            }
          });
      }
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
      <div
        class='cluster-box'
        v-bkloading={{ isLoading: loading.value }}
      >
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
            value={prependText.value}
          >
            <template slot='prepend'>
              <div class='group-text'>{showGroupText.value}</div>
            </template>
          </bk-input>
        </div>
        <div class='link-config label-form-box'>
          <span class='label-title'>{t('过期时间')}</span>
          <bk-input
            class='min-width'
            type='number'
            value={formData.value.retention}
            max={daysMax.value}
            min={1}
            on-input={val => {
              formData.value.retention = val;
            }}
          >
            <template slot='append'>
              <div class='group-text'>{t('天')}</div>
            </template>
          </bk-input>
        </div>
        {clusterData.value.enable_hot_warm && (
          <div class='link-config label-form-box'>
            <span class='label-title'>{t('热数据天数')}</span>
            <bk-input
              class='min-width'
              type='number'
              max={daysMax.value}
              min={0}
              value={formData.value.allocation_min_days}
              on-input={val => {
                formData.value.allocation_min_days = val;
              }}
            >
              <template slot='append'>
                <div class='group-text'>{t('天')}</div>
              </template>
            </bk-input>
          </div>
        )}

        <div class='link-config label-form-box'>
          <span class='label-title'>{t('副本数')}</span>
          <bk-input
            class='min-width'
            type='number'
            max={numberOfReplicasMax.value}
            min={0}
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
            max={esShardsMax.value}
            min={0}
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
      const {
        collector_config_name,
        collector_config_name_en,
        index_set_name,
        bk_data_id,
        custom_type,
        retention,
        allocation_min_days,
        storage_replies,
        category_id,
        description,
        storage_cluster_id,
        es_shards,
        parent_index_set_ids,
      } = formData.value;
      $http
        .request(`custom/${isUpdate.value ? 'setCustom' : 'createCustom'}`, {
          params: {
            collector_config_id: props.configData.collector_config_id,
          },
          data: {
            bk_data_id,
            custom_type,
            storage_cluster_id,
            retention,
            allocation_min_days,
            storage_replies,
            category_id,
            description,
            es_shards,
            parent_index_set_ids,
            collector_config_name_en,
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
      const { collector_config_id, retention, allocation_min_days, storage_replies, es_shards, table_id } =
        formData.value;
      const data = {
        collector_config_id,
        retention,
        allocation_min_days,
        storage_replies,
        etl_params,
        es_shards,
        fields: etl_fields,
        etl_config: clean_type,
        table_id: table_id || curCollect.value.collector_config_name_en,
        storage_cluster_id: clusterSelect.value,
      };
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
    /**
     * 初始化回填数据
     * @param val
     */
    const initData = () => {
      formData.value = { ...formData.value, ...props.configData };
      clusterSelect.value = props.configData.storage_cluster_id;
    };
    // watch(
    //   () => props.isEdit || props.isClone,
    //   (val: boolean) => {
    //     if (val) {
    //       initData(val);
    //     }
    //   },
    //   { immediate: true },
    // );

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
