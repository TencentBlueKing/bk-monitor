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

import { computed, defineComponent, ref, watch, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';
import { bkMessage } from 'bk-magic-vue';
import { ConfigProvider as TConfigProvider, Table as TTable } from 'tdesign-vue';
import ItemSkeleton from '@/skeleton/item-skeleton';
import EmptyStatus from '@/components/empty-status/index.vue';

import $http from '@/api';

import './index-config-import-dialog.scss';
import 'tdesign-vue/es/style/index.css';

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
 * ETL配置项类型
 */
interface IEtlConfigItem {
  /** 配置ID */
  id: string | number;
  /** 配置名称 */
  name: string;
  [key: string]: unknown;
}

/**
 * API返回的采集器原始数据
 */
interface ICollectorRawData {
  /** 采集器配置ID */
  collector_config_id: number | string;
  /** 采集器配置名称 */
  collector_config_name?: string;
  /** 存储集群名称 */
  storage_cluster_name?: string;
  /** ETL配置ID */
  etl_config?: string | number;
  /** 存储时长（天） */
  retention?: number;
  /** 参数字符串（Python字典格式） */
  params?: string;
  /** 数据ID */
  bk_data_id?: number | string;
  [key: string]: unknown;
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
  emits: {
    /** 更新事件 */
    update: (_value: boolean) => true,
    /** 取消事件 */
    cancel: (_value: boolean) => true,
  },

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    // const route = useRoute();

    // ==================== 常量定义 ====================

    /** 同步类型选项列表 */
    const syncTypeList: ISyncTypeOption[] = [
      { name: t('同步源日志信息'), id: 'source_log_info' },
      { name: t('同步字段清洗配置'), id: 'field_clear_config' },
      { name: t('同步存储配置'), id: 'storage_config' },
      { name: t('同步采集目标'), id: 'acquisition_target' },
    ];

    // ==================== 响应式状态 ====================

    /** 选中的同步类型列表 */
    const syncType = ref<string[]>(['source_log_info']);

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
    const searchKeyword = ref<string>('1201');

    /** 当前选中的导入项ID */
    const currentCheckImportID = ref<number | string | null>(null);
    /**
     * 同步采集目标 只有在主机采集的时候才显示
     */
    const showType = computed(() => {
      if (['std_log_config', 'file_log_config'].includes(props.scenarioId)) {
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
        title: t('采集模式'),
        colKey: 'etl_config',
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

    // ==================== 计算属性 ====================

    /** ETL配置列表 */
    const etlConfigList = computed<IEtlConfigItem[]>(() => store.getters['globals/globalsData']?.etl_config || []);

    // ==================== 工具函数 ====================

    /**
     * 将Python字典字符串转换为JSON格式
     * 将Python的字典语法转换为JavaScript可解析的JSON格式
     * @param pythonString - Python字典格式的字符串
     * @returns 转换后的JSON字符串
     */
    const pythonDictString = (pythonString: string): string => {
      return pythonString
        .replace(/'/g, '"') // 将单引号替换为双引号
        .replace(/None/g, 'null') // 将 None 替换为 null
        .replace(/True/g, 'true') // 将 True 替换为 true
        .replace(/False/g, 'false'); // 将 False 替换为 false
    };

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
     * 处理保存操作
     * TODO: 实现保存逻辑，将选中的配置导入到当前索引集
     */
    const handleSave = (): void => {
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
          if (res.data) {
            const collect = res.data;
            const isPhysics = collect.environment !== 'container';
            if (collect.collector_scenario_id !== 'wineventlog' && isPhysics && collect?.params.paths) {
              collect.params.paths = collect.params.paths.map(item => ({ value: item }));
            }
            store.commit('collect/updateExportCollectObj', {
              collectID: currentCheckImportID.value,
              syncType: syncType.value,
              collect,
            });
            handleCancel();
          }
        })
        .catch(err => {
          console.warn(err);
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
        syncType.value = ['source_log_info'];
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
      isTableLoading.value = true;
      // const ids = route.query.ids as string; // 根据id来检索
      // const collectorIdList = ids ? decodeURIComponent(ids) : [];
      collectList.value = [];
      const { current, pageSize } = pagination.value;
      $http
        .request('collect/newCollectList', {
          data: {
            space_uid: store.getters.spaceUid,
            page: current,
            pagesize: pageSize,
            keyword: searchKeyword.value,
          },
        })
        .then(res => {
          const { list, total } = res?.data || { list: [], total: 0 };
          if (list?.length) {
            pagination.value.total = total;
            collectList.value = list.map(item => {
              const { etl_config, retention, params } = item;
              // let paths: string[] = [];
              // try {
              //   const value = JSON.parse(pythonDictString(params));
              //   paths = value?.paths ?? [];
              // } catch (e) {
              //   console.error(e);
              // }
              return {
                ...item,
                retention: retention ? `${retention}${t('天')}` : '--',
                // paths: paths?.join('; ') ?? '',
                // etl_config: etlConfigList.value.find(newItem => newItem.id === etl_config)?.name ?? '--',
              };
            });
          }
        })
        .catch(() => {
          emptyType.value = '500';
        })
        .finally(() => {
          isTableLoading.value = false;
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
        if (val) {
          getLinkList();
        }
      },
    );

    const handleEmptyOperation = () => {
      searchKeyword.value = '';
      changePagination();
    };

    const renderEmpty = () => (
      <div class='table-empty-content'>
        <EmptyStatus
          emptyType={emptyType.value}
          on-operation={() => handleEmptyOperation()}
        />
      </div>
    );

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
        on-confirm={handleSave}
        on-value-change={handleValueChange}
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
            <TConfigProvider class='config-import-table'>
              <TTable
                cellEmptyContent={'--'}
                columns={allColumns.value}
                data={collectList.value}
                loading={isTableLoading.value}
                loading-props={{ indicator: false }}
                on-page-change={handlePageChange}
                pagination={pagination.value}
                row-key='key'
                rowHeight={32}
                scroll={{ type: 'lazy', bufferSize: 10 }}
                scopedSlots={{
                  loading: () => (
                    <div class='table-skeleton-box'>
                      <ItemSkeleton
                        style={{ padding: '0 16px' }}
                        columns={5}
                        gap={'14px'}
                        rowHeight={'28px'}
                        rows={4}
                        widths={['20%', '20%', '20%', '20%', '20%']}
                      />
                    </div>
                  ),
                  empty: renderEmpty,
                }}
              />
            </TConfigProvider>
          </div>
        </div>
      </bk-dialog>
    );
  },
});
