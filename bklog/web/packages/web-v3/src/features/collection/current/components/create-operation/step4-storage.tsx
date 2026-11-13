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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { useCollectionStore } from '@/app/state/domains/collection-store';


import { Button as TButton, InputNumber as TInputNumber } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
import type { IClusterItem } from '../business-comp/step4/cluster-table';
import type { IFormData } from '../../type';
import type { CleanFormState } from './clean-form.type';

import { computed, defineComponent, onMounted, ref } from 'vue';

import useLocale from '@/shared/composables/use-locale';
import useRouter from '@/shared/composables/use-router';

import { useRoute } from 'vue-router';

import ClusterTypeTabs from '../../../../clusters/current/cluster-manage/cluster-type-tabs.tsx';
import { CLUSTER_TYPES, ClusterType, useClusterType } from '../../../../clusters/current/cluster-manage/use-cluster-type';
import { useOperation } from '../../hook/useOperation';
import { showClusterSelectError } from '@/shared/lib/collector-api-error';
import { getFormValidateMessage } from '../../save-failure';
import { showCollectSaveFailure, showMessage, showUnshownRequestError } from '../../utils';
import ClusterTable from '../business-comp/step4/cluster-table';
import { deepEqual } from '@/shared/lib/util';

import { isCollectionEditRoute } from './route-utils';

import type { ISubmitOptions } from '../../type';

import './step4-storage.scss';

interface IStorageFieldData {
  allocation_min_days?: number | string | null;
  es_shards?: number | string | null;
  retention?: number | string | null;
  storage_replies?: number | string | null;
  storage_shards_nums?: number | string | null;
}

type StorageFormState = IFormData & Partial<CleanFormState> & {
  retention: string | number; allocation_min_days: string | number;
  storage_replies: string | number; es_shards: string | number; need_assessment: boolean;
  storage_cluster_id?: number; clean_template_id?: number | null; bk_data_id?: number;
  custom_type?: string;
};
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

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useApplicationStore();
    const route = useRoute();
    const router = useRouter();
    const { cardRender, sortByPermission } = useOperation();

    const activeName = ref(['shared', 'exclusive']);
    const storageList = ref<IClusterItem[]>([]);
    const clusterSelect = ref();
    const clusterData = ref<Partial<IClusterItem>>({});
    const loading = ref(false);
    const submitLoading = ref(false);
    const STORAGE_DEFAULTS = {
      storage_replies: 1,
      retention: 7,
      es_shards: 3,
      allocation_min_days: 0,
    };
    const createCleanDefaults = () => ({
      // 清洗相关字段默认值，与旧版保持一致
      etl_config: 'bk_log_text',
      etl_params: {
        retain_original_text: true,
        retain_extra_json: false,
        separator_regexp: '',
        separator: '',
        enable_retain_content: true,
        path_regexp: '',
        metadata_fields: [],
      },
      fields: [],
    });
    const normalizeStorageFields = (data: IStorageFieldData = {}) => ({
      retention: data.retention ?? STORAGE_DEFAULTS.retention,
      allocation_min_days: data.allocation_min_days ?? STORAGE_DEFAULTS.allocation_min_days,
      storage_replies: data.storage_replies ?? STORAGE_DEFAULTS.storage_replies,
      es_shards: data.storage_shards_nums ?? data.es_shards ?? STORAGE_DEFAULTS.es_shards,
    });

    const storageFormRef = ref<import("@/shared/types/legacy-form").LegacyFormInstance | null>(null);
    const formData = ref<StorageFormState>({
      ...STORAGE_DEFAULTS,
      ...createCleanDefaults(),
      need_assessment: false,
      ...props.configData,
      ...normalizeStorageFields(props.configData),
    });
    const cleanStash = ref({});
    /**
     * 初始表单数据快照，用于对比是否有变更
     */
    const initialFormData = ref<StorageFormState | null>(null);

    const bkBizId = computed(() => store.bkBizId);
    const spaceUid = computed(() => store.spaceUid);
    const curCollect = computed(() => useCollectionStore().curCollect || {});
    const currentCollect = computed(() => (curCollect.value?.collector_config_id ? curCollect.value : formData.value));

    const getInitialTab = (): ClusterType => {
      const tabQuery = route.query.tab;
      if (tabQuery === 'doris') return CLUSTER_TYPES.DORIS;
      return CLUSTER_TYPES.ES;
    };

    const resetClusterSelection = () => {
      clusterSelect.value = undefined;
      clusterData.value = {};
      (formData.value as any).storage_cluster_id = undefined;
      Object.assign(formData.value, STORAGE_DEFAULTS);
    };

    const { activeTab, isDorisMode, isDorisEnabled, checkDorisAccess, handleTabClick } = useClusterType({
      bkBizId,
      spaceUid,
      initialTab: getInitialTab(),
      onAccessDenied: () => {
        const { tab, ...restQuery } = route.query;
        router.replace({
          name: route.name,
          params: route.params,
          query: restQuery,
        });
      },
      onTabChange: async (type, _previousType, isInitial) => {
        const currentQuery = { ...route.query };
        currentQuery.tab = type === CLUSTER_TYPES.DORIS ? 'doris' : 'es';
        router.replace({
          name: route.name,
          params: route.params,
          query: currentQuery,
        });

        if (!isInitial) {
          storageList.value = [];
          resetClusterSelection();
        }
        await getStorage();
      },
    });

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
      return clusterData.value?.setup_config?.es_shards_max || 3;
    });

    /**
     * 表单校验规则
     */
    const formRules = computed(() => ({
      retention: [
        {
          validator: (val: unknown) => Number(val) <= daysMax.value,
          message: t('最大自定义天数为{n}', { n: daysMax.value }),
          trigger: 'blur',
        },
        {
          validator: (val: unknown) => Number(val) <= daysMax.value,
          message: t('最大自定义天数为{n}', { n: daysMax.value }),
          trigger: 'change',
        },
      ],
      allocation_min_days: [
        {
          validator: (val: unknown) => Number(val) <= daysMax.value,
          message: t('最大自定义天数为{n}', { n: daysMax.value }),
          trigger: 'blur',
        },
        {
          validator: (val: unknown) => Number(val) <= daysMax.value,
          message: t('最大自定义天数为{n}', { n: daysMax.value }),
          trigger: 'change',
        },
        {
          validator: (val: unknown) => Number(val) <= Number(formData.value.retention),
          message: t('热数据天数不能大于过期时间'),
          trigger: 'blur',
        },
      ],
      storage_replies: [
        {
          validator: (val: unknown) => Number(val) <= numberOfReplicasMax.value,
          message: t('最大自定义副本数为: {n}', { n: numberOfReplicasMax.value }),
          trigger: 'blur',
        },
        {
          validator: (val: unknown) => Number(val) <= numberOfReplicasMax.value,
          message: t('最大自定义副本数为: {n}', { n: numberOfReplicasMax.value }),
          trigger: 'change',
        },
      ],
      es_shards: [
        {
          validator: (val: unknown) => Number(val) <= esShardsMax.value,
          message: t('最大自定义分片数为: {n}', { n: esShardsMax.value }),
          trigger: 'blur',
        },
        {
          validator: (val: unknown) => Number(val) <= esShardsMax.value,
          message: t('最大自定义分片数为: {n}', { n: esShardsMax.value }),
          trigger: 'change',
        },
      ],
    }));

    const showGroupText = computed(() => {
      const custom =
        Number(bkBizId.value) > 0 ? `${bkBizId.value}_bklog_` : `space_${Math.abs(Number(bkBizId.value))}_bklog_`;
      return custom;
    });

    const prependText = computed(() => {
      const { table_id: tableId, collector_config_name_en: collectorConfigNameEn } = currentCollect.value;
      if (props.isClone) {
        return collectorConfigNameEn || props.configData.collector_config_name_en;
      }
      return formData.value.table_id || tableId || collectorConfigNameEn || props.configData.collector_config_name_en;
    });

    /**
     * 是否为编辑
     */
    const isUpdate = computed(() => isCollectionEditRoute(route.name) && props.isEdit);

    /**
     * 保存初始表单数据快照
     */
    const saveInitialFormData = () => {
      initialFormData.value = structuredClone(formData.value);
    };

    /**
     * 判断配置是否有变更
     */
    const hasConfigChanged = () => {
      return initialFormData.value !== null && !deepEqual(formData.value, initialFormData.value);
    };

    /** 是否为编辑模式 */
    const isEditMode = computed(() => isCollectionEditRoute(route.name));

    /**
     * 异步获取存储列表并按权限排序
     * 功能：请求存储数据，将有管理权限的存储项优先展示，处理加载状态和错误提示
     */
    const getStorage = async () => {
      const queryParams = {
        bk_biz_id: bkBizId.value,
        cluster_type: activeTab.value,
      };

      try {
        loading.value = true;
        const res = await ServicesInstance.collect.getStorage({ query: queryParams }, { catchIsShowMessage: false });

        if (res.data) {
          storageList.value = sortByPermission(res.data);
        }
      } catch (error) {
        showClusterSelectError(error);
      } finally {
        loading.value = false;
      }
    };

    /**
     * 选择集群时重置为默认值（切换集群场景）
     */
    const handleSelectStorageCluster = (row: Partial<IClusterItem>) => {
      const { setup_config: setupConfig } = row;
      formData.value = {
        ...formData.value,
        storage_cluster_id: row.storage_cluster_id,
        retention: setupConfig?.retention_days_default ?? STORAGE_DEFAULTS.retention,
        storage_replies: setupConfig?.number_of_replicas_default ?? STORAGE_DEFAULTS.storage_replies,
        es_shards: setupConfig?.es_shards_default ?? STORAGE_DEFAULTS.es_shards,
        allocation_min_days: 0,
      };
    };
    /**
     * 选择集群
     * @param row
     */
    const handleChooseCluster = (row: Partial<IClusterItem>) => {
      if (row.storage_cluster_id !== clusterSelect.value) {
        handleSelectStorageCluster(row);
      }
      clusterSelect.value = row.storage_cluster_id;
      clusterData.value = row;
      // doris集群编辑时，接口返回的retention可能为null，使用选中集群的max_retention兜底
      if (
        isDorisMode.value &&
        props.isEdit &&
        (formData.value.retention === null || formData.value.retention === undefined)
      ) {
        formData.value.retention = row.max_retention ?? STORAGE_DEFAULTS.retention;
      }
      // 如果开启了冷热集群，天数不能为0
      if (row.enable_hot_warm && Number(formData.value.allocation_min_days) === 0) {
        formData.value.allocation_min_days = row.setup_config?.retention_days_default || '7';
      }
      // 切换集群后清除表单校验错误提示
      storageFormRef.value?.clearError();
    };
    /**
     * 获取采集项清洗缓存
     */

    const getCleanStash = async () => {
      const isStorageEdit = isEditMode.value && !!route.query.step;
      let id = currentCollect.value?.collector_config_id;
      if (isStorageEdit) {
        id = Number(route.params.collectorId);
      }
      if (!id) {
        return;
      }
      try {
        const res = await ServicesInstance.clean.getCleanStash({
          params: {
            collector_config_id: id,
          },
        });
        if (res.data) {
          cleanStash.value = res.data;
          // 回填清洗配置到 formData，与旧版保持一致
          formData.value = {
            ...formData.value,
            clean_template_id: res.data.clean_template_id ?? null,
            etl_config: res.data.clean_type,
            etl_params: res.data.etl_params,
            fields: res.data.etl_fields,
          };
        }
      } catch (error) {
        console.log(error);
      }
    };
    onMounted(async () => {
      initData();
      loading.value = true;
      checkDorisAccess();
      let clusterType: ClusterType | undefined;
      if (props.configData?.storage_cluster_type) {
        clusterType = props.configData.storage_cluster_type;
      }
      const isStorageEdit = isEditMode.value && !!route.query.step;
      if (isStorageEdit) {
        await ServicesInstance.collect.details(
            {
              params: { collector_config_id: route.params.collectorId },
            },
            { catchIsShowMessage: false },
          )
          .then(res => {
            if (res?.data) {
              useCollectionStore().setCurCollect(res.data);
              const { storage_cluster_id: storageClusterId, storage_cluster_type: storageClusterType } = res.data;
              if (storageClusterType) {
                clusterType = storageClusterType;
              }
              formData.value = {
                ...formData.value,
                ...res.data,
                ...normalizeStorageFields(res.data),
              };
              clusterSelect.value = storageClusterId;
            }
          })
          .catch(error => {
            showClusterSelectError(error);
          });
      }
      await handleTabClick(clusterType ?? activeTab.value, true);
      if (!isCustomReport.value) {
        await getCleanStash();
      }
      saveInitialFormData();
    });

    /**
     * rCollapseItem的渲染
     */
    const renderCollapseItem = (item: { title: string; key: string; data: IClusterItem[]; tips?: string }) => (
      <bk-collapse-item
        v-slots={{
          content: () => (
            <div class='cluster-content'>
              <ClusterTable
                clusterList={item.data}
                clusterSelect={clusterSelect.value}
                loading={loading.value}
                name={item.title}
                showBizCount={item.key === 'shared'}
                showDesc={!isDorisMode.value}
                onChoose={handleChooseCluster}
              />
            </div>
          ),
        }}
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
      </bk-collapse-item>
    );

    /** 集群选择 */
    const renderCluster = () => (
      <div
        class='cluster-box'
        v-loading={{ loading: loading.value }}
      >
        <ClusterTypeTabs
          activeTab={activeTab.value}
          isDorisEnabled={isDorisEnabled.value}
          onTabClick={handleTabClick}
        />

        <bk-collapse
          value={activeName.value}
          onChange={(value: string[]) => {
            activeName.value = value;
          }}
        >
          {collapseList.value.map(item => renderCollapseItem(item))}
        </bk-collapse>
      </div>
    );

    /** 存储信息 */
    const renderStorage = () => (
      <div class='storage-box'>
        <div class='link-config label-form-box'>
          <span class='label-title'>{t('索引名')}</span>
          <bk-input
            v-slots={{
              prepend: () => (
                <>
                  <div class='group-text'>{showGroupText.value}</div>
                </>
              ),
            }}
            class='storage-input'
            disabled={true}
            value={prependText.value}
          ></bk-input>
        </div>
        <bk-form
          ref={storageFormRef}
          label-width={100}
          {...{ ...{ model: formData.value, rules: formRules.value } }}
        >
          <bk-form-item
            label={t('过期时间')}
            property='retention'
          >
            <TInputNumber
              suffix={t('天')}
              class='number-input'
              theme='normal'
              decimalPlaces={0}
              allowInputOverLimit={false}
              value={formData.value.retention}
              min={1}
              onChange={val => {
                formData.value.retention = val ?? '';
              }}
              onBlur={val => {
                if (val == null || val === '') {
                  formData.value.retention =
                    clusterData.value?.setup_config?.retention_days_default ?? STORAGE_DEFAULTS.retention;
                }
              }}
            />
          </bk-form-item>
          {!isDorisMode.value && [
            clusterData.value.enable_hot_warm && (
              <bk-form-item
                label={t('热数据天数')}
                property='allocation_min_days'
              >
                <TInputNumber
                  suffix={t('天')}
                  class='number-input'
                  theme='normal'
                  decimalPlaces={0}
                  allowInputOverLimit={false}
                  min={0}
                  value={formData.value.allocation_min_days}
                  onChange={val => {
                    formData.value.allocation_min_days = val ?? '';
                  }}
                  onBlur={val => {
                    if (val == null || val === '') {
                      formData.value.allocation_min_days =
                        clusterData.value?.setup_config?.retention_days_default ?? STORAGE_DEFAULTS.retention;
                    }
                  }}
                />
              </bk-form-item>
            ),
            <bk-form-item
              label={t('副本数')}
              property='storage_replies'
            >
              <TInputNumber
                class='number-input'
                theme='normal'
                decimalPlaces={0}
                allowInputOverLimit={false}
                min={0}
                value={formData.value.storage_replies}
                onChange={val => {
                  formData.value.storage_replies = val ?? '';
                }}
                onBlur={val => {
                  if (val == null || val === '') {
                    formData.value.storage_replies =
                      clusterData.value?.setup_config?.number_of_replicas_default ?? STORAGE_DEFAULTS.storage_replies;
                  }
                }}
              />
            </bk-form-item>,
            <bk-form-item
              label={t('分片数')}
              property='es_shards'
            >
              <TInputNumber
                class='number-input'
                theme='normal'
                decimalPlaces={0}
                allowInputOverLimit={false}
                min={1}
                value={formData.value.es_shards}
                onChange={val => {
                  formData.value.es_shards = val ?? '';
                }}
                onBlur={val => {
                  if (val == null || val === '') {
                    formData.value.es_shards =
                      clusterData.value?.setup_config?.es_shards_default ?? STORAGE_DEFAULTS.es_shards;
                  }
                }}
              />
            </bk-form-item>,
          ]}
        </bk-form>
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
     * @param options 保存选项配置
     * @param options.action 操作类型: 'next'(默认) | 'saveOnly'
     * @param options.callback 保存完成后的回调函数
     */
    const handleCustomSubmit = ({ action = 'next', callback }: ISubmitOptions = {}) => {
      submitLoading.value = true;
      const {
        collector_config_name: collectorConfigName,
        collector_config_name_en,
        index_set_name: indexSetName,
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
      const submitData = {
        bk_data_id,
        custom_type,
        storage_cluster_id,
        retention: Number(retention),
        allocation_min_days: Number(allocation_min_days),
        storage_replies: Number(storage_replies),
        category_id,
        description,
        es_shards: Number(es_shards),
        parent_index_set_ids,
        collector_config_name_en,
        collector_config_name: collectorConfigName || indexSetName,
        bk_biz_id: Number(bkBizId.value),
        target_fields: props.configData.target_fields || [],
        sort_fields: props.configData.sort_fields || [],
        data_link_id: props.configData.data_link_id || '',
      };

      if (isDorisMode.value) {
        delete (submitData as Partial<typeof submitData>).es_shards;
        delete (submitData as Partial<typeof submitData>).storage_replies;
        delete (submitData as Partial<typeof submitData>).allocation_min_days;
      }

      ServicesInstance.custom[isUpdate.value ? 'setCustom' : 'createCustom']({
          params: {
            collector_config_id: props.configData.collector_config_id,
          },
          data: submitData,
        })
        .then(res => {
          if (!res?.result) {
            showCollectSaveFailure(res, t('保存失败'));
            callback?.(false);
            return;
          }
          showMessage(t('保存成功'));
          if (action === 'saveOnly') {
            // 只保存，不跳转
            callback?.(true);
          } else {
            emit('cancel');
          }
        })
        .catch(err => {
          showUnshownRequestError(err, t('保存失败'));
          callback?.(false);
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };
    /**
     * 采集场景提交
     * @param options 保存选项配置
     * @param options.action 操作类型: 'next'(默认) | 'saveOnly'
     * @param options.callback 保存完成后的回调函数
     */
    const handleNormalSubmit = ({ action = 'next', callback }: ISubmitOptions = {}) => {
      submitLoading.value = true;
      // 从 formData 读取清洗相关数据，与旧版保持一致
      const {
        etl_config,
        etl_params: etlParams,
        fields,
        retention,
        allocation_min_days,
        storage_replies,
        es_shards,
      } = formData.value;
      const collectorConfigId = currentCollect.value?.collector_config_id || route.params.collectorId;
      const tableId = props.isClone
        ? currentCollect.value.collector_config_name_en
        : formData.value.table_id || currentCollect.value.collector_config_name_en;
      // 仅透传公开的 expand_depth，避免覆盖后台隐藏的 overflow_strategy
      const submitEtlParams = (() => {
        if (!etlParams) return etlParams;
        const { ext_json_config: extJsonConfig, ...rest } = etlParams as any;
        if (!rest.retain_extra_json || !extJsonConfig || !('expand_depth' in extJsonConfig)) {
          return rest;
        }
        return {
          ...rest,
          ext_json_config: {
            expand_depth: extJsonConfig.expand_depth ?? null,
          },
        };
      })();
      const data = {
        clean_template_id: formData.value.clean_template_id ?? null,
        collector_config_id: collectorConfigId,
        retention: Number(retention),
        allocation_min_days: Number(allocation_min_days),
        storage_replies: Number(storage_replies),
        etl_params: submitEtlParams,
        es_shards: Number(es_shards),
        fields,
        etl_config,
        table_id: tableId,
        storage_cluster_id: clusterSelect.value,
      };
      ServicesInstance.collect.fieldCollection({
          params: {
            collector_config_id: collectorConfigId,
          },
          data,
        })
        .then(res => {
          if (res.data) {
            if (action === 'saveOnly') {
              // 只保存，不跳转
              callback?.(true);
            } else {
              emit('cancel');
              useCollectionStore().updateCurCollect({ ...formData.value, ...data, ...res.data });
            }
          } else {
            showCollectSaveFailure(res, t('保存失败'));
            callback?.(false);
          }
        })
        .catch(err => {
          showUnshownRequestError(err, t('保存失败'));
          callback?.(false);
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };
    /**
     * 保存配置
     * @param options 保存选项配置
     * @param options.action 操作类型: 'next'(默认) | 'saveOnly'
     * @param options.callback 保存完成后的回调函数
     */
    const handleSubmitSave = async ({ action = 'next', callback }: ISubmitOptions = {}) => {
      if (!clusterSelect.value) {
        showMessage(t('请选择集群'), 'error');
        callback?.(false);
        return;
      }
      // 表单校验
      try {
        await storageFormRef.value?.validate();
      } catch (err) {
        showMessage(getFormValidateMessage(err, t('请完善存储配置')), 'error');
        callback?.(false);
        return;
      }
      if (isCustomReport.value) {
        /**
         * 自定义上报存储保存
         */
        handleCustomSubmit({ action, callback });
      } else {
        /**
         * 采集场景提交
         */
        handleNormalSubmit({ action, callback });
      }
    };
    /**
     * 初始化回填数据
     * @param val
     */
    const initData = () => {
      formData.value = {
        ...formData.value,
        ...props.configData,
        ...normalizeStorageFields(props.configData),
      };
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

    expose({
      hasConfigChanged,
      handleSubmitSave,
    });

    return () => (
      <div class='operation-step4-storage'>
        {cardRender(cardConfig)}
        <div class='classify-btns-fixed'>
          <TButton theme='default' variant='outline'
            class='mr-8'
            onClick={() => {
              emit('prev');
            }}
          >
            {t('上一步')}
          </TButton>
          <TButton
            class='width-88 mr-8'
            loading={submitLoading.value}
            theme='primary'
            onClick={() => handleSubmitSave()}
          >
            {t('提交')}
          </TButton>
          <TButton theme="default"
            onClick={() => {
              emit('cancel');
            }}
          >
            {t('取消')}
          </TButton>
        </div>
      </div>
    );
  },
});
