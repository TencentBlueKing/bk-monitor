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

import { defineComponent, ref, watch, computed, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';

import { useCollectList } from '../../hook/useCollectList';
import { useOperation } from '../../hook/useOperation';
import { showMessage } from '../../utils';
import BaseInfo from '../business-comp/step2/base-info';
import BkdataSelectDialog from '../business-comp/step2/third-party-logs/bkdata-select-dialog';
import EsSelectDialog from '../business-comp/step2/third-party-logs/es-select-dialog';
import DragTag from '../common-comp/drag-tag';
import InfoTips from '../common-comp/info-tips';
import TableComponent from '../common-comp/table-component';
import $http from '@/api';

import './step2-bk-data-collection.scss';

// ==================== 类型定义 ====================

/**
 * 场景ID类型
 */
type ScenarioId = 'bkdata' | 'es' | 'linux';

/**
 * 索引项接口
 */
interface IIndexItem {
  /** 结果表ID */
  result_table_id: string;
  [key: string]: unknown;
}

/**
 * 集群项接口
 */
interface IClusterItem {
  /** 存储集群ID */
  storage_cluster_id: number | string;
  /** 存储集群名称 */
  storage_display_name: string;
  /** 是否为平台集群 */
  is_platform?: boolean;
  /** 权限信息 */
  permission?: Record<string, boolean>;
  [key: string]: unknown;
}

/**
 * 字段项接口
 */
interface IFieldItem {
  /** 字段名称 */
  field_name: string;
  /** 字段类型 */
  field_type: string;
  [key: string]: unknown;
}

/**
 * 匹配到的索引项接口
 */
interface IMatchedTableItem {
  /** 结果表ID */
  result_table_id: string;
  [key: string]: unknown;
}

/**
 * 时间索引配置接口
 */
interface ITimeIndex {
  /** 时间字段名称 */
  time_field: string;
  /** 时间字段类型 */
  time_field_type?: string;
  /** 时间精度单位 */
  time_field_unit?: string;
}

/**
 * 字段选择项接口
 */
interface IFieldSelectItem {
  /** 字段ID */
  id: string;
  /** 字段名称 */
  name: string;
}

/**
 * 配置数据接口
 */
interface IConfigData {
  /** 查看角色列表 */
  view_roles: string[];
  /** 索引集名称 */
  index_set_name: string;
  /** 存储集群ID */
  storage_cluster_id: number | string | null;
  /** 场景ID */
  scenario_id: string;
  /** 分类ID */
  category_id: string;
  /** 索引列表 */
  indexes: IIndexItem[];
  /** 目标字段列表 */
  target_fields: string[];
  /** 排序字段列表 */
  sort_fields: string[];
  parent_index_set_ids: number[];
}

/**
 * 索引集详情数据接口
 */
interface IIndexSetData {
  /** 索引列表 */
  indexes: IIndexItem[];
  /** 索引集名称 */
  index_set_name: string;
  /** 查看角色列表 */
  view_roles: string[];
  /** 存储集群ID */
  storage_cluster_id?: number | string;
  /** 排序字段列表 */
  sort_fields?: string[];
  /** 目标字段列表 */
  target_fields?: string[];
  [key: string]: unknown;
}

/**
 * 字段查询结果接口
 */
interface IFieldQueryResult {
  /** 数据对象 */
  data: {
    /** 字段列表 */
    fields: IFieldItem[];
  };
}

/**
 * 用于配置和管理数据收集的基础信息、数据源和字段设置
 * 支持两种场景：
 * - bkdata: 计算平台日志接入
 * - es: 第三方ES日志接入
 */
export default defineComponent({
  name: 'StepBkDataCollection',
  props: {
    /** 场景ID，用于区分不同的数据接入方式 */
    scenarioId: {
      type: String as PropType<ScenarioId>,
      default: 'linux',
    },
    /** 是否为编辑模式 */
    isEdit: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['next', 'prev', 'cancel'],

  setup(props, { emit }) {
    // ==================== 基础依赖 ====================
    const { t } = useLocale();
    const route = useRoute();
    const store = useStore();
    const { bkBizId, spaceUid } = useCollectList();
    const { cardRender, handleMultipleSelected, tableLoading, sortByPermission } = useOperation();

    // ==================== 响应式状态 ====================
    /** 页面加载状态 */
    const loading = ref(false);
    /** 提交加载状态 */
    const submitLoading = ref(false);
    /** 集群加载状态 */
    const clusterLoading = ref(false);
    /** 控制弹窗显示状态 */
    const isShowDialog = ref(false);
    /** 当前显示的索引ID */
    const currentActiveShowID = ref('');
    /** 基础信息表单引用 */
    const baseInfoRef = ref<InstanceType<typeof BaseInfo>>();
    /** 选择对话框引用 */
    const selectCollectionRef = ref();
    /** 索引列表是否为空 */
    const isIndexesEmpty = ref(false);
    const listLoading = ref(false);

    // ==================== 数据状态 ====================
    /** 集群列表 */
    const clusterList = ref<IClusterItem[]>([]);
    /** 匹配到的索引列表（ES场景使用） */
    const currentMatchedTableIds = ref<IMatchedTableItem[]>([]);
    /** 字段列表（计算平台场景使用） */
    const collectionTableData = ref<IFieldItem[]>([]);
    /** 目标字段选择列表 */
    const targetFieldSelectList = ref<IFieldSelectItem[]>([]);
    /** 时间索引配置 */
    const timeIndex = ref<ITimeIndex | null>(null);
    /** 配置数据 */
    const configData = ref<IConfigData>({
      view_roles: [],
      index_set_name: '',
      storage_cluster_id: null,
      scenario_id: props.scenarioId,
      category_id: 'application_check',
      indexes: [],
      target_fields: [],
      sort_fields: [],
      parent_index_set_ids: [],
    });

    const skeletonConfig = {
      columns: 2,
      rows: 4,
      widths: ['50%', '50%'],
    };

    // ==================== 计算属性 ====================
    /** 获取时间字段显示值 */
    const getTimeFiled = computed(() => timeIndex.value?.time_field || '--');
    /** 是否为ES场景 */
    const isEsScenario = computed(() => props.scenarioId === 'es');
    /** 是否为计算平台场景 */
    const isBkdataScenario = computed(() => props.scenarioId === 'bkdata');

    // ==================== 渲染函数 ====================

    /**
     * 渲染基础信息卡片
     * @returns JSX元素
     */
    const renderBaseInfo = () => (
      <BaseInfo
        ref={baseInfoRef}
        data={configData.value}
        typeKey='bk-data'
        on-change={(data) => {
          configData.value = { ...configData.value, ...data };
        }}
      />
    );

    /**
     * 渲染数据源卡片
     * 包含：集群选择（ES场景）、数据源选择、匹配索引列表/字段列表、时间字段（ES场景）
     * @returns JSX元素
     */
    const renderDataSource = () => (
      <div class='data-source-box'>
        {/* ES场景：集群选择 */}
        {isEsScenario.value && (
          <div class='label-form-box'>
            <span class='label-title'>{t('集群')}</span>
            <div class='form-box'>
              <bk-select
                class='w-40'
                clearable={false}
                disabled={props.isEdit}
                loading={clusterLoading.value}
                value={configData.value.storage_cluster_id}
                on-selected={(val) => {
                  configData.value.storage_cluster_id = val;
                }}
              >
                {clusterList.value.map(option => (
                  <bk-option
                    id={option.storage_cluster_id}
                    key={option.storage_cluster_id}
                    class='custom-no-padding-option'
                    name={option.storage_display_name}
                  />
                ))}
              </bk-select>
            </div>
          </div>
        )}

        {/* 数据源选择 */}
        <div class='label-form-box'>
          <span class='label-title'>{t('数据源')}</span>
          <div class='form-box'>
            <DragTag
              addType='custom'
              isError={isIndexesEmpty.value}
              idKey='result_table_id'
              nameKey='result_table_id'
              sortable={false}
              value={configData.value.indexes}
              on-custom-add={handleAddDataSource}
            />
            <div class='data-source-table'>
              {/* 计算平台场景：显示字段列表 */}
              {isBkdataScenario.value ? (
                <TableComponent
                  height={400}
                  loading={tableLoading.value}
                  data={collectionTableData.value}
                  skeletonConfig={skeletonConfig}
                  columns={[
                    {
                      title: t('字段'),
                      colKey: 'field_name',
                      ellipsis: true,
                    },
                    {
                      title: t('类型'),
                      colKey: 'field_type',
                      ellipsis: true,
                    },
                  ]}
                />
              ) : (
                /* ES场景：显示匹配到的索引列表 */
                <TableComponent
                  height={400}
                  loading={tableLoading.value}
                  data={currentMatchedTableIds.value}
                  skeletonConfig={skeletonConfig}
                  columns={[
                    {
                      title: t('匹配到的索引'),
                      colKey: 'result_table_id',
                      ellipsis: true,
                    },
                  ]}
                />
              )}
            </div>
          </div>
        </div>

        {/* ES场景：时间字段显示 */}
        {isEsScenario.value && (
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('时间字段')}</span>
            <div class='form-box'>
              <span class='time-field'>{getTimeFiled.value}</span>
            </div>
          </div>
        )}
      </div>
    );

    /**
     * 渲染字段设置卡片
     * 包含：目标字段选择、排序字段设置
     * @returns JSX元素
     */
    const renderFieldSetting = () => (
      <div class='field-setting-box'>
        <bk-alert
          class='field-setting-alert'
          title={t('未匹配到对应字段，请手动指定字段后提交。')}
          type='warning'
        />
        {/* 目标字段选择 */}
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('目标字段')}</span>
          <div class='form-box'>
            <bk-select
              class='select-sort'
              clearable={false}
              value={configData.value.target_fields}
              collapse-tag
              display-tag
              multiple
              searchable
              on-selected={(value) => {
                configData.value.target_fields = value;
              }}
            >
              {targetFieldSelectList.value.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
            <InfoTips
              class='block'
              tips={t('用于标识日志文件来源及唯一性')}
            />
          </div>
        </div>
        {/* 排序字段设置 */}
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('排序字段')}</span>
          <div class='form-box'>
            <DragTag
              addType='select'
              selectList={targetFieldSelectList.value}
              value={configData.value.sort_fields}
              on-change={(value) => {
                configData.value.sort_fields = value;
              }}
            />
            <InfoTips
              class='block'
              tips={t('用于控制日志排序的字段')}
            />
          </div>
        </div>
      </div>
    );

    /**
     * 卡片配置列表
     */
    const cardConfig = [
      {
        title: t('基础信息'),
        key: 'baseInfo',
        renderFn: renderBaseInfo,
      },
      {
        title: t('数据源'),
        key: 'dataSource',
        renderFn: renderDataSource,
      },
      {
        title: t('字段设置'),
        key: 'fieldSetting',
        renderFn: renderFieldSetting,
      },
    ];

    // ==================== 数据获取函数 ====================

    /**
     * 获取索引集详情数据（编辑模式使用）
     * 功能：从服务器获取索引集信息，更新配置数据，并初始化字段列表
     */
    const fetchIndexSetData = async (): Promise<void> => {
      try {
        loading.value = true;
        const indexSetId = route.params.collectorId as string;
        const { data: indexSetData } = (await $http.request('indexSet/info', {
          params: {
            index_set_id: indexSetId,
          },
        })) as { data: IIndexSetData };

        // 更新store中的当前索引集
        store.commit('collect/updateCurIndexSet', indexSetData);

        // 更新配置数据
        const { indexes, index_set_name, view_roles, storage_cluster_id, sort_fields, target_fields } = indexSetData;
        configData.value = {
          ...configData.value,
          indexes: indexes || [],
          index_set_name: index_set_name || '',
          view_roles: view_roles || [],
          storage_cluster_id: storage_cluster_id ?? null,
          sort_fields: sort_fields || [],
          target_fields: target_fields || [],
        };

        /**
         * 如果有索引，初始化显示列表和字段选择列表
         */
        if (indexes && indexes.length > 0 && indexes[0]?.result_table_id) {
          await handleChangeShowTableList(indexes[0].result_table_id, true);
        }
      } catch (error) {
        console.log('获取索引集详情失败:', error);
        showMessage(t('获取索引集详情失败'), 'error');
      } finally {
        loading.value = false;
      }
    };

    /**
     * 获取集群列表数据（ES场景使用）
     * 功能：
     * 1. 请求集群数据
     * 2. 按权限排序
     * 3. 过滤平台集群
     * 4. 处理路由参数设置默认集群
     */
    const fetchPageData = async (): Promise<void> => {
      try {
        clusterLoading.value = true;
        const clusterRes = (await $http.request('/source/logList', {
          query: {
            bk_biz_id: bkBizId.value,
            scenario_id: 'es',
          },
        })) as { data: IClusterItem[] };

        if (clusterRes.data && Array.isArray(clusterRes.data)) {
          // 按权限排序并过滤非平台集群
          const sortedClusters = sortByPermission(clusterRes.data);
          clusterList.value = sortedClusters.filter(cluster => !cluster.is_platform);

          // 处理路由参数设置默认集群
          const targetClusterId = route.query.cluster;
          if (targetClusterId) {
            const numericClusterId = Number(targetClusterId);
            const isClusterValid = clusterList.value.some(
              cluster => Number(cluster.storage_cluster_id) === numericClusterId,
            );

            if (isClusterValid) {
              configData.value.storage_cluster_id = numericClusterId;
            } else {
              /**
               * 如果路由参数中的集群无效，使用第一个可用集群
               */
              configData.value.storage_cluster_id = clusterList.value[0]?.storage_cluster_id ?? null;
            }
          } else {
            /**
             * 没有路由参数，使用第一个可用集群
             */
            configData.value.storage_cluster_id = clusterList.value[0]?.storage_cluster_id ?? null;
          }
        }
      } catch (error) {
        console.log('获取集群列表失败:', error);
        showMessage(t('获取集群列表失败'), 'error');
      } finally {
        clusterLoading.value = false;
      }
    };

    // ==================== 事件处理函数 ====================

    /**
     * 显示新增索引弹窗
     * ES场景需要先选择集群才能添加索引
     */
    const handleAddDataSource = (): void => {
      if (isEsScenario.value && !configData.value.storage_cluster_id) {
        showMessage(t('请先选择集群'), 'error');
        return;
      }
      isShowDialog.value = true;
    };

    /**
     * 关闭新增索引弹窗
     */
    const handleCancel = (): void => {
      isShowDialog.value = false;
    };

    /**
     * 保存配置
     * 功能：
     * 1. 验证表单
     * 2. 检查索引列表是否为空
     * 3. 构建请求参数
     * 4. 调用创建或更新接口
     */
    const handleSave = async (): Promise<void> => {
      try {
        // 检查索引列表是否为空
        isIndexesEmpty.value = configData.value.indexes.length === 0;

        // 验证基础信息表单
        if (baseInfoRef.value && 'validate' in baseInfoRef.value) {
          await (baseInfoRef.value as { validate: () => Promise<void> }).validate();
        }

        // 如果索引列表为空，不继续提交
        if (isIndexesEmpty.value) {
          return;
        }

        submitLoading.value = true;

        // 构建请求参数
        const params: Record<string, unknown> = {
          space_uid: spaceUid.value,
          ...configData.value,
        };

        // ES场景需要添加时间索引配置
        if (isEsScenario.value && timeIndex.value) {
          Object.assign(params, timeIndex.value);
        } else if (!isEsScenario.value) {
          // 非ES场景不需要存储集群ID
          params.storage_cluster_id = undefined;
        }

        // 根据编辑模式调用不同的接口
        const url = `/indexSet/${props.isEdit ? 'update' : 'create'}`;
        let paramsData = { data: params };
        if (props.isEdit) {
          paramsData = {
            ...paramsData,
            params: {
              index_set_id: route.params.collectorId,
            },
          };
        }
        const res = await $http.request(url, paramsData);

        if (res?.result) {
          showMessage(props.isEdit ? t('设置成功') : t('创建成功'), 'success');
          handleClose();
        }
      } catch (error) {
        // 表单验证失败或其他错误
        if (error && typeof error === 'object' && 'message' in error) {
          console.error('保存配置失败:', error);
        }
      } finally {
        submitLoading.value = false;
      }
    };

    /**
     * 获取ES场景匹配到的索引列表
     * @param resultTableId - 结果表ID（支持通配符）
     * @returns Promise<void>
     */
    const fetchList = async (resultTableId: string): Promise<void> => {
      listLoading.value = true;
      try {
        const res = (await $http.request('/resultTables/list', {
          query: {
            scenario_id: props.scenarioId,
            bk_biz_id: bkBizId.value,
            storage_cluster_id: configData.value.storage_cluster_id,
            result_table_id: resultTableId,
          },
        })) as { data: IMatchedTableItem[] };
        currentMatchedTableIds.value = res.data || [];
      } catch (error) {
        console.log('获取匹配索引列表失败:', error);
        currentMatchedTableIds.value = [];
      } finally {
        listLoading.value = false;
      }
    };

    /**
     * 获取计算平台场景的字段列表
     * 功能：获取所有索引的字段信息，合并去重后展示
     * @returns Promise<void>
     */
    const collectList = async (): Promise<void> => {
      listLoading.value = true;
      try {
        // 提取所有结果表ID
        const resultTableIds = configData.value.indexes.map(item => item.result_table_id);

        if (resultTableIds.length === 0) {
          collectionTableData.value = [];
          return;
        }

        // 并发请求所有结果表的字段信息
        const requests = resultTableIds.map(id => $http.request('/resultTables/info', {
          params: { result_table_id: id },
          query: {
            scenario_id: props.scenarioId,
            bk_biz_id: bkBizId.value,
          },
        }),
        );

        const results = (await Promise.all(requests)) as IFieldQueryResult[];

        // 使用Map去重，保留第一个出现的字段
        const fieldMap = new Map<string, IFieldItem>();
        for (const result of results) {
          const fields = result?.data?.fields || [];
          for (const field of fields) {
            if (field.field_name && !fieldMap.has(field.field_name)) {
              fieldMap.set(field.field_name, field);
            }
          }
        }

        collectionTableData.value = Array.from(fieldMap.values());
      } catch (error) {
        collectionTableData.value = [];
      } finally {
        listLoading.value = false;
      }
    };

    /**
     * 初始化字段设置所需的字段选择列表
     * 功能：
     * 1. 获取所有关联结果表的字段
     * 2. 合并已有目标字段和排序字段
     * 3. 生成去重的选择列表
     * @returns Promise<void>
     */
    const initTargetFieldSelectList = async (): Promise<void> => {
      try {
        // 提取所有结果表ID
        const resultTableIds = configData.value.indexes.map(item => item.result_table_id);

        if (resultTableIds.length === 0) {
          targetFieldSelectList.value = [];
          return;
        }

        /**
         * 构建字段查询配置
         * @param resultTableId - 结果表ID
         * @returns 查询配置参数
         */
        const getFieldQueryConfig = (resultTableId: string) => ({
          params: { result_table_id: resultTableId },
          query: {
            scenario_id: props.scenarioId,
            bk_biz_id: bkBizId.value,
            // 仅ES场景需要存储集群ID
            ...(isEsScenario.value && {
              storage_cluster_id: configData.value.storage_cluster_id,
            }),
          },
        });

        // 生成所有结果表的查询配置并并发请求
        const fieldQueries = resultTableIds.map(getFieldQueryConfig);
        const fetchPromises = fieldQueries.map(query => handleMultipleSelected(query, true));
        const fieldResults = (await Promise.all(fetchPromises)) as IFieldQueryResult[];

        // 提取已有目标字段和排序字段，初始化Set用于去重
        const { target_fields: targetFields = [], sort_fields: sortFields = [] } = configData.value;
        const fieldNameSet = new Set<string>([...sortFields, ...targetFields]);

        // 合并所有查询结果中的字段（去重）
        for (const result of fieldResults) {
          const fields = result?.data?.fields || [];
          for (const field of fields) {
            if (field.field_name) {
              fieldNameSet.add(field.field_name);
            }
          }
        }

        // 转换为选择列表所需格式
        targetFieldSelectList.value = Array.from(fieldNameSet).map(fieldName => ({
          id: fieldName,
          name: fieldName,
        }));
      } catch (error) {
        console.log('初始化字段选择列表失败:', error);
        targetFieldSelectList.value = [];
      }
    };

    /**
     * 切换显示的数据源列表
     * 功能：
     * 1. 根据场景类型获取对应的列表数据（ES场景获取匹配索引，计算平台场景获取字段列表）
     * 2. 可选地初始化字段选择列表
     * @param resultTableId - 结果表ID
     * @param isInitTarget - 是否初始化目标字段选择列表
     * @returns Promise<void>
     */
    const handleChangeShowTableList = async (resultTableId: string, isInitTarget = false): Promise<void> => {
      currentActiveShowID.value = resultTableId;

      // 根据场景类型获取不同的数据
      if (isEsScenario.value) {
        await fetchList(resultTableId);
      } else {
        await collectList();
      }

      // 如果需要初始化字段选择列表
      if (isInitTarget) {
        await initTargetFieldSelectList();
      }
    };

    /**
     * 处理索引选择事件
     * @param data - 选中的索引数据
     */
    const handleSelect = (data: IIndexItem): void => {
      configData.value.indexes.push(data);
      handleChangeShowTableList(data.result_table_id, true);
    };

    /**
     * 处理时间索引配置变化
     * @param data - 时间索引配置数据
     */
    const handleTimeIndex = (data: ITimeIndex): void => {
      timeIndex.value = data;
    };

    /**
     * 关闭并取消操作
     */
    const handleClose = (): void => {
      emit('cancel');
    };

    // ==================== 监听器 ====================

    /**
     * 监听编辑模式变化，编辑模式下加载索引集详情
     */
    watch(
      () => props.isEdit,
      (val: boolean) => {
        if (val) {
          fetchIndexSetData();
        }
      },
      { immediate: true },
    );

    /**
     * 监听场景ID变化，ES场景需要加载集群列表
     */
    watch(
      () => props.scenarioId,
      (val: string) => {
        if (val === 'es') {
          fetchPageData();
        }
      },
      { immediate: true },
    );

    // ==================== 渲染 ====================

    return () => (
      <div
        class='operation-step2-bk-data-collection'
        v-bkloading={{ isLoading: loading.value }}
      >
        {/* 卡片内容区域 */}
        {cardRender(cardConfig)}

        {/* 操作按钮区域 */}
        <div class='classify-btns-fixed'>
          {/* 非编辑模式显示上一步按钮 */}
          {!props.isEdit && (
            <bk-button
              class='mr-8'
              on-click={() => {
                emit('prev');
              }}
            >
              {t('上一步')}
            </bk-button>
          )}
          {/* 提交按钮 */}
          <bk-button
            class='width-88 mr-8'
            loading={submitLoading.value}
            theme='primary'
            on-click={handleSave}
          >
            {t('提交')}
          </bk-button>
          {/* 取消按钮 */}
          <bk-button on-click={handleClose}>{t('取消')}</bk-button>
        </div>

        {/* 索引选择对话框 */}
        {isBkdataScenario.value ? (
          <BkdataSelectDialog
            ref={selectCollectionRef}
            configData={configData.value}
            isShowDialog={isShowDialog.value}
            scenarioId={props.scenarioId}
            on-cancel={handleCancel}
            on-selected={handleSelect}
          />
        ) : (
          <EsSelectDialog
            configData={configData.value}
            isShowDialog={isShowDialog.value}
            scenarioId={props.scenarioId}
            on-cancel={handleCancel}
            on-selected={handleSelect}
            on-timeIndex={handleTimeIndex}
          />
        )}
      </div>
    );
  },
});
