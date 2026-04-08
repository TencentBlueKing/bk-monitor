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

import { computed, defineComponent, ref, watch, type PropType, onBeforeUnmount } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { bkMessage } from 'bk-magic-vue';
import axios from 'axios';
import $http from '@/api';
import TableComponent from '../../common-comp/table-component';

import './index-config-import-dialog.scss';

const CancelToken = axios.CancelToken;
/**
 * 同步类型选项
 */
interface ISyncTypeOption {
  /** 显示名称 */
  name: string;
  /** 唯一标识 */
  id: string;
}

/**
 * 处理后的采集器列表项
 */
interface ICollectorListItem {
  /** 数据ID */
  bk_data_id?: number | string;
  /** 采集器配置ID */
  collector_config_id: number | string;
  /** 采集器配置名称 */
  collector_config_name: string;
  /** 存储集群名称 */
  storage_cluster_name: string;
  /** 存储时长（格式化后） */
  retention: string;
  /** 采集路径（多个路径用分号分隔） */
  paths: string;
  /** ETL配置名称 */
  etl_config: string;
}

/**
 * 分页更新参数类型
 */

interface IPaginationConfig {
  current: number;
  pageSize: number;
}

/**
 * 索引配置导入对话框组件
 *
 * 功能说明：
 * - 用于从其他索引集导入配置信息
 * - 支持选择同步类型（源日志信息、字段清洗配置、存储配置、采集目标）
 * - 提供搜索功能，可按索引集名称筛选
 * - 支持分页展示采集器列表
 * - 支持单选目标索引集进行配置导入
 */
export default defineComponent({
  name: 'IndexConfigImportDialog',
  props: {
    /** 是否显示对话框 */
    showDialog: {
      type: Boolean as PropType<boolean>,
      default: false,
    },
    scenarioId: {
      type: String,
      default: '',
    },
  },
  emits: ['update', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    // const route = useRoute();
    const etlConfigEnum = {
      bk_log_text: t('直接入库'),
      bk_log_json: 'JSON',
      bk_log_delimiter: t('分隔符'),
      bk_log_regexp: t('正则表达式'),
    };

    // ==================== 常量定义 ====================

    /** 同步类型选项列表 */
    const syncTypeList: ISyncTypeOption[] = [
      { name: t('同步源日志信息'), id: 'sourceLogConfig' },
      { name: t('同步字段清洗配置'), id: 'cleanConfig' },
      { name: t('同步存储配置'), id: 'storageConfig' },
      { name: t('同步采集目标'), id: 'targetConfig' },
    ];

    // ==================== 响应式状态 ====================

    /** 选中的同步类型列表 */
    const syncType = ref<string[]>(['sourceLogConfig']);
    const isContainerKeys = ['container_stdout', 'container_file'];

    /** 分页配置 */
    const pagination = ref({
      current: 1,
      total: 0,
      pageSize: 10,
      showPageSize: false,
    });

    /** 表格加载状态 */
    const isTableLoading = ref<boolean>(false);

    const submitLoading = ref<boolean>(false);

    /** 采集器列表数据 */
    const collectList = ref<ICollectorListItem[]>([]);

    /** 空状态类型 */
    const emptyType = ref<'empty' | 'search-empty' | '500'>('empty');

    /** 搜索输入框的值 */
    const searchKeyword = ref<string>('');

    /** 当前选中的导入项ID */
    const currentCheckImportID = ref<number | string | null>(null);

    /**
     * 获取列表接口取消
     */
    const listInterfaceCancel = ref(null);
    /**
     * 是否取消接口请求
     */
    const isCancelToken = ref(false);
    /**
     * 同步采集目标 只有在主机采集的时候才显示
     */
    const showType = computed(() => {
      if (['container_stdout', 'container_file'].includes(props.scenarioId)) {
        return syncTypeList.slice(0, 3);
      }
      return syncTypeList;
    });
    // ==================== 插槽定义 ====================

    /** 复选框列插槽 - 用于显示选中状态 */
    const checkBoxSlot = row => (
      <div class='import-check-box'>
        <bk-checkbox
          class='group-check-box'
          checked={getCheckedStatus(row)}
          on-change={() => handleRowCheckChange(row)}
        />
      </div>
    );

    const allColumns = computed(() => [
      {
        title: '',
        colKey: '',
        cell: (h, { row }) => checkBoxSlot(row),
        width: 60,
        ellipsis: true,
      },
      {
        title: t('索引集'),
        colKey: 'name',
        ellipsis: true,
      },
      {
        title: t('采集路径'),
        colKey: 'paths',
        ellipsis: true,
      },
      {
        title: t('清洗模式'),
        colKey: 'eltString',
        ellipsis: true,
      },
      {
        title: t('存储集群'),
        colKey: 'storage_cluster_name',
        ellipsis: true,
      },
      {
        title: t('存储时长'),
        colKey: 'retention',
        ellipsis: true,
      },
    ]);

    // ==================== 工具函数 ====================

    /**
     * 更新分页配置
     * @param page - 要更新的分页参数
     */
    const changePagination = (): void => {
      pagination.value.current = 1;
      getLinkList();
    };

    /**
     * 判断行是否被选中
     * @param row - 表格行数据
     * @returns 是否选中
     */
    const getCheckedStatus = (row: ICollectorListItem): boolean => {
      return row.collector_config_id === currentCheckImportID.value;
    };

    // ==================== 事件处理函数 ====================
    /**
     * 处理行选中变化
     * 点击行时切换选中状态，如果已选中则取消选中
     * @param row - 表格行数据
     */
    const handleRowCheckChange = (row: ICollectorListItem): void => {
      if (currentCheckImportID.value === row.collector_config_id) {
        currentCheckImportID.value = null;
        return;
      }
      currentCheckImportID.value = row.collector_config_id;
    };

    const handlePageChange = (pageInfo: IPaginationConfig) => {
      pagination.value.current = pageInfo.current;
      getLinkList();
    };

    /**
     * 处理采集器数据，根据场景转换paths格式
     * @param collect - 采集器原始数据
     * @returns 处理后的采集器数据
     */
    const processCollectorData = (collect: Record<string, unknown>): Record<string, unknown> => {
      const isPhysics = isContainerKeys.includes(props.scenarioId);
      if (props.scenarioId !== 'winevent' && !isPhysics) {
        const params = collect?.params as { paths?: string[] } | undefined;
        if (params?.paths && Array.isArray(params.paths)) {
          params.paths = params.paths.map((item: string) => ({ value: item })) as unknown as string[];
        }
      }
      return collect;
    };

    /**
     * 构建配置对象
     * @param collect - 采集器数据
     * @returns 配置对象映射
     */
    const buildConfigMap = (collect: Record<string, unknown>) => {
      const isPhysics = isContainerKeys.includes(props.scenarioId);
      const {
        params,
        configs,
        target_node_type,
        target_nodes,
        data_encoding,
        bcs_cluster_id,
        retention,
        allocation_min_days,
        storage_replies,
        etl_params,
        es_shards,
        table_id,
        storage_cluster_id,
        etl_config: etlConfig,
        fields,
        extra_labels,
        add_pod_label,
        add_pod_annotation,
      } = collect;

      // 构建源日志信息配置
      const sourceLogConfig = isPhysics
        ? {
            configs,
            bcs_cluster_id,
            extra_labels,
            add_pod_label,
            add_pod_annotation,
          }
        : {
            params,
            extra_labels,
            data_encoding,
          };

      // 构建字段清洗配置
      const cleanConfig = {
        clean_type: etlConfig,
        etl_params,
        etl_fields: fields,
      };

      // 构建存储配置
      const storageConfig = {
        retention,
        allocation_min_days,
        storage_replies,
        etl_params,
        es_shards,
        table_id,
        storage_cluster_id,
      };

      // 构建采集目标配置
      const targetConfig = {
        target_node_type,
        target_nodes,
      };

      return {
        sourceLogConfig,
        cleanConfig,
        storageConfig,
        targetConfig,
      };
    };

    /**
     * 根据选中的同步类型合并配置
     * @param configMap - 配置对象映射
     * @returns 合并后的配置对象
     */
    const mergeSelectedConfigs = (configMap: Record<string, Record<string, unknown>>) => {
      return Object.entries(configMap)
        .filter(([key]) => syncType.value.includes(key))
        .reduce((acc, [, value]) => ({ ...acc, ...value }), {});
    };

    /**
     * 处理保存操作
     */
    const handleSave = (): void => {
      // 验证同步类型
      if (!syncType.value.length) {
        setTimeout(() => {
          bkMessage({
            theme: 'error',
            message: t('请选择需要同步的配置'),
          });
        }, 100);
        return;
      }

      submitLoading.value = true;
      $http
        .request('collect/details', {
          params: {
            collector_config_id: currentCheckImportID.value,
          },
        })
        .then(res => {
          if (!res.data) return;

          const processedCollect = processCollectorData(res.data);
          const configMap = buildConfigMap(processedCollect);
          const mergedConfig = mergeSelectedConfigs(configMap);

          emit('update', mergedConfig);
          handleCancel();
        })
        .catch(err => {
          console.log('获取采集器详情失败:', err);
          bkMessage({
            theme: 'error',
            message: t('获取配置信息失败，请稍后重试'),
          });
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };

    /**
     * 处理对话框显示状态变化
     * 当对话框关闭时，重置所有状态
     * @param v - 对话框是否显示
     */
    const handleValueChange = (v: boolean): void => {
      if (!v) {
        syncType.value = ['sourceLogConfig'];
        currentCheckImportID.value = null;
        emptyType.value = 'empty';
        searchKeyword.value = '';
      }
    };

    /**
     * 处理取消操作
     */
    const handleCancel = (): void => {
      emit('cancel', !props.showDialog);
    };

    /**
     * 执行搜索
     * 将搜索输入框的值同步到筛选关键词，并重置到第一页
     */
    const search = (): void => {
      emptyType.value = searchKeyword.value ? 'search-empty' : 'empty';
      // 搜索时重置到第一页
      if (searchKeyword.value) {
        changePagination();
      }
    };

    // ==================== 数据获取 ====================

    /**
     * 获取采集器列表
     * 从路由参数中获取索引集ID列表，调用接口获取对应的采集器数据
     */
    const getLinkList = (): void => {
      listInterfaceCancel.value?.();
      isTableLoading.value = true;
      collectList.value = [];
      const { current, pageSize } = pagination.value;
      $http
        .request(
          'collect/newCollectList',
          {
            data: {
              space_uid: store.getters.spaceUid,
              page: current,
              pagesize: pageSize,
              keyword: searchKeyword.value,
              conditions: [{ key: 'log_access_type', value: [props.scenarioId] }],
            },
          },
          {
            cancelToken: new CancelToken(c => {
              listInterfaceCancel.value = c;
              isCancelToken.value = true;
            }),
          },
        )
        .then(res => {
          isTableLoading.value = false;
          const { list, total } = res?.data || { list: [], total: 0 };
          if (list?.length) {
            pagination.value.total = total;
            collectList.value = list.map(item => {
              const { retention, collect_paths, etl_config } = item;
              return {
                ...item,
                retention: retention ? `${retention}${t('天')}` : '--',
                paths: collect_paths?.join('; ') ?? '',
                eltString: etlConfigEnum[etl_config],
              };
            });
          }
        })
        .catch(() => {
          emptyType.value = '500';
        });
    };

    // ==================== 监听器 ====================

    /**
     * 监听对话框显示状态
     * 当对话框打开时，自动获取采集器列表
     */
    watch(
      () => props.showDialog,
      (val: boolean) => {
        handleValueChange(val);
        if (val) {
          getLinkList();
        }
      },
    );

    const handleEmptyOperation = () => {
      searchKeyword.value = '';
      changePagination();
    };

    onBeforeUnmount(() => {
      listInterfaceCancel.value?.();
    });

    return () => (
      <bk-dialog
        width={1200}
        class='index-config-import-dialog'
        header-position='left'
        mask-close={false}
        position={{ top: 100 }}
        title={t('索引配置导入')}
        value={props.showDialog}
        on-cancel={handleCancel}
      >
        <div class='index-config-import-dialog-content'>
          <div class='content-top'>
            <bk-checkbox-group
              value={syncType.value}
              on-change={(val: string[]) => {
                syncType.value = val;
              }}
            >
              {showType.value.map(item => (
                <bk-checkbox
                  value={item.id}
                  key={item.id}
                  disabled={syncType.value.length === 1 && syncType.value.includes(item.id)}
                >
                  {item.name}
                </bk-checkbox>
              ))}
            </bk-checkbox-group>
            <bk-input
              placeholder={t('搜索名称')}
              right-icon='bk-icon icon-search'
              value={searchKeyword.value}
              on-change={(val: string) => {
                searchKeyword.value = val;
                if (val === '') {
                  handleEmptyOperation();
                }
              }}
              on-enter={search}
            />
          </div>
          <div class='content-bot'>
            <div class='content-bot-title'>{t('请选择目标索引集')}</div>
            <TableComponent class='config-import-table'
              columns={allColumns.value}
              data={collectList.value}
              loading={isTableLoading.value}
              on-page-change={handlePageChange}
              pagination={pagination.value}
              on-empty-click={handleEmptyOperation}
              emptyType={emptyType.value}
              height='430px'
            />
          </div>
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            class='mr-8'
            on-click={handleSave}
            loading={submitLoading.value}
            disabled={!currentCheckImportID.value}
          >
            {t('确定')}
          </bk-button>
          <bk-button on-click={handleCancel}>{t('取消')}</bk-button>
        </div>
      </bk-dialog>
    );
  },
});
