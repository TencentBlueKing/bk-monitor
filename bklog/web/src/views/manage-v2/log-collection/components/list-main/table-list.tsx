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

import { defineComponent, onBeforeUnmount, onMounted, ref, nextTick, watch, computed, type PropType } from 'vue';
import useLocale from '@/hooks/use-locale';
import tippy, { type Instance } from 'tippy.js';
import { tenantManager } from '@/views/retrieve-core/tenant-manager';
import axios from 'axios';
import {
  formatBytes,
  getOperatorCanClick,
  showMessage,
  SETTING_FIELDS,
  MENU_LIST,
  GLOBAL_CATEGORIES_ENUM,
  COLLECTOR_SCENARIO_ENUM,
  STATUS_ENUM_FILTER,
} from '../../utils';
import useResizeObserver from '@/hooks/use-resize-observe';
import CollectIssuedSlider from '../business-comp/step3/collect-issued-slider';
import $http from '@/api';
import { useCollectList } from '../../hook/useCollectList';
import TagMore from '../common-comp/tag-more';
import type { IListItemData } from '../../type';
import EmptyStatus from '@/components/empty-status/index.vue';
import './table-list.scss';
import TableComponent from '../common-comp/table-component';

const CancelToken = axios.CancelToken;

/**
 * 表格行数据类型定义
 */
interface ITableRowData {
  index_set_id: number | string;
  collector_config_id?: number | string;
  collector_config_name?: string;
  name: string;
  status: string;
  status_name: string;
  storage_cluster_id?: number;
  storage_cluster_name?: string;
  daily_usage?: number;
  total_usage?: number;
  bk_data_name?: string;
  parent_index_sets?: Array<{ index_set_name: string; [key: string]: unknown }>;
  scenario_id?: string;
  scenario_name?: string;
  collector_scenario_id?: string;
  collector_scenario_name?: string;
  retention?: number;
  tags?: Array<{ name: string; [key: string]: unknown }>;
  created_by?: string;
  created_at?: string;
  updated_by?: string;
  updated_at?: string;
  environment?: string;
  [key: string]: unknown;
}

/**
 * 菜单项类型
 */
interface IMenuItem {
  key: string;
  label: string;
}

/**
 * 过滤条件类型
 */
interface IFilterCondition {
  key: string;
  value: string[];
}

/**
 * 过滤值类型
 */
interface IFilterValues {
  created_by: Array<{ label: string; value: string; key?: string }>;
  updated_by: Array<{ label: string; value: string; key?: string }>;
  storage_cluster_name: Array<{ label: string; value: string; key?: string }>;
}

/**
 * 分页信息类型
 */
interface IPaginationInfo {
  current: number;
  pageSize: number;
}

/**
 * 排序配置类型
 */
interface ISortConfig {
  descending?: boolean;
  sortBy?: string;
}

/**
 * 存储用量响应数据类型
 */
interface IStorageUsageItem {
  index_set_id: number | string;
  daily_usage?: number;
  total_usage?: number;
  [key: string]: unknown;
}

/**
 * 表格高度计算相关常量
 */
const HEIGHT_CONSTANTS = {
  MIN_TABLE_HEIGHT: 400, // 最小表格高度（至少显示 6-7 行数据）
  COLUMNS_HEIGHT: 43, // 每列高度
  FIXED_ELEMENTS_HEIGHT: 150, // 固定元素高度（头部、工具栏、分页器等）
  WINDOW_FIXED_HEIGHT: 400, // 窗口固定元素高度（用于后备方案）
} as const;

/**
 * 延迟时间常量
 */
const DELAY_CONSTANTS = {
  MENU_POP_INIT: 1000, // 菜单弹窗初始化延迟
  PAGINATION_HEIGHT_CALC: 150, // 分页高度计算延迟
  RESIZE_OBSERVER: 200, // 尺寸监听器延迟
} as const;

/**
 * 字段ID到列键的映射
 */
const FIELD_ID_TO_COL_KEY_MAP: Record<string, string> = {
  collector_config_name: 'name',
  storage_usage: 'daily_usage',
  total_usage: 'total_usage',
  table_id: 'bk_data_name',
  index_set_id: 'index_set_name',
  log_access_type: 'log_access_type',
  collector_scenario_id: 'collector_scenario_id',
  storage_cluster_name: 'storage_cluster_name',
  retention: 'retention',
  label: 'tags',
  es_host_state: 'status',
  updated_by: 'updated_by',
  updated_at: 'updated_at',
} as const;

export default defineComponent({
  name: 'TableList',
  props: {
    indexSet: {
      type: Object as PropType<IListItemData>,
      default: () => ({}),
    },
  },

  emits: [],

  setup(props) {
    const { t } = useLocale();
    const showCollectIssuedSlider = ref(false);
    const currentRow = ref<ITableRowData>({} as ITableRowData);
    /**
     * 获取列表接口取消
     */
    const listInterfaceCancel = ref(null);
    /**
     * 是否取消接口请求
     */
    const isCancelToken = ref(false);
    /**
     * 是否展示一键检测
     */
    const isShowDetection = ref(false);
    const checkInfo = ref('');

    // 使用自定义 hook 管理状态
    const { authGlobalInfo, operateHandler, checkCreateAuth, spaceUid, bkBizId } = useCollectList();
    const tableList = ref<ITableRowData[]>([]);
    const listLoading = ref(false);
    // 保存原始数据顺序的索引映射（用于恢复排序）
    const originalOrderMap = ref<Map<number | string, number>>(new Map());
    // 用户信息映射（username -> display_name）
    const userDisplayNameMap = ref<Map<string, string>>(new Map());

    // 容器和表格高度相关
    const containerRef = ref<HTMLElement | null>(null);
    const tableMainRef = ref<HTMLElement | null>(null);
    const maxTableHeight = ref<number>(0);

    let tippyInstances: Instance[] = [];
    let collectStatusTimer: ReturnType<typeof setTimeout> | null = null;
    const searchKey = ref('');
    const IFilterValues = ref<IFilterValues>({
      created_by: [],
      updated_by: [],
      storage_cluster_name: [],
    });
    // 过滤条件
    const conditions = ref<IFilterCondition[]>([]);
    // 表格过滤值（用于设置默认选中状态）
    const filterValue = ref<Record<string, string>>({
      log_access_type: '',
      collector_scenario_id: '',
      storage_cluster_name: '',
      status: '',
      created_by: '',
      updated_by: '',
    });

    const pagination = ref({
      current: 1,
      total: 0,
      pageSize: 10,
      limitList: [10, 20, 50],
    });

    const sortConfig = ref<ISortConfig>({});
    /**
     * 获取空状态类型
     * @returns 空状态类型
     */
    const emptyType = computed(() => {
      return hasFilterOrSearch.value ? 'search-empty' : 'empty';
    });

    /**
     * 使用窗口高度作为后备方案计算表格高度
     * @returns 计算出的表格高度
     */
    const calculateHeightByWindow = (): number => {
      const windowHeight = window.innerHeight;
      return Math.max(HEIGHT_CONSTANTS.MIN_TABLE_HEIGHT, windowHeight - HEIGHT_CONSTANTS.WINDOW_FIXED_HEIGHT);
    };

    /**
     * 根据屏幕大小计算表格最大可用高度
     *
     * 该方法用于动态计算表格组件的最大可用高度，确保表格能够自适应容器大小，
     * 同时考虑固定元素（如头部、工具栏、分页器等）占用的空间。
     *
     * 计算逻辑：
     * 1. 使用 nextTick 确保在 DOM 更新后执行，获取准确的容器尺寸
     * 2. 优先使用容器高度进行计算，如果容器未挂载或高度无效，则使用窗口高度作为后备方案
     * 3. 从容器高度中减去固定元素高度，得到表格可用高度
     * 4. 确保计算出的高度不小于最小表格高度
     * 5. 根据实际数据量和分页大小进行最终调整
     */
    const calculateMaxTableHeight = () => {
      nextTick(() => {
        // 如果容器未挂载或高度无效，使用窗口高度作为后备方案
        if (!containerRef.value) {
          maxTableHeight.value = calculateHeightByWindow();
          return;
        }

        const container = containerRef.value;
        const containerHeight = container.clientHeight || container.offsetHeight;

        if (!containerHeight || containerHeight <= 0) {
          maxTableHeight.value = calculateHeightByWindow();
          return;
        }

        // 计算表格最大可用高度：容器高度 - 所有固定元素高度
        const calculatedMaxHeight = containerHeight - HEIGHT_CONSTANTS.FIXED_ELEMENTS_HEIGHT;

        // 确保高度在合理范围内（不小于最小高度）
        maxTableHeight.value = Math.max(HEIGHT_CONSTANTS.MIN_TABLE_HEIGHT, calculatedMaxHeight);

        // 根据实际数据量和分页大小进行最终调整
        const listLen = tableList.value.length;
        if (listLen === 0) {
          maxTableHeight.value = HEIGHT_CONSTANTS.MIN_TABLE_HEIGHT;
          return;
        }
        const totalListHeight = listLen * HEIGHT_CONSTANTS.COLUMNS_HEIGHT + 36;

        // 如果分页数据总高度超过最大高度，使用最大高度（启用滚动）
        // 否则根据实际数据行数计算高度（避免空白区域）
        maxTableHeight.value = totalListHeight > maxTableHeight.value ? maxTableHeight.value : totalListHeight;
      });
    };

    // 监听容器大小变化
    useResizeObserver(
      () => containerRef.value,
      () => {
        calculateMaxTableHeight();
      },
      DELAY_CONSTANTS.RESIZE_OBSERVER,
    );

    // 监听窗口大小变化
    const handleWindowResize = () => {
      calculateMaxTableHeight();
    };

    // 监听数据变化，重新计算高度
    watch(
      () => [tableList.value.length, listLoading.value],
      () => {
        calculateMaxTableHeight();
      },
    );

    // 监听分页变化，重新计算高度（延迟执行，等待分页器渲染）
    watch(
      () => [pagination.value.current, pagination.value.pageSize, pagination.value.total],
      () => {
        setTimeout(() => {
          calculateMaxTableHeight();
        }, DELAY_CONSTANTS.PAGINATION_HEIGHT_CALC);
      },
    );

    /**
     * 渲染状态
     * @param row - 表格行数据
     * @returns JSX 元素
     */
    const renderStatus = (row: ITableRowData) => {
      return row.status ? <span class={`table-status ${row.status}`}>{row.status_name}</span> : <span>--</span>;
    };

    /**
     * 根据行数据渲染菜单列表
     * @param row - 表格行数据
     * @returns 过滤后的菜单列表
     */
    const renderMenu = (row: ITableRowData): IMenuItem[] => {
      const type = row?.log_access_type || 'linux';

      if (!type) {
        return MENU_LIST.filter(item => item.key !== (status !== 'terminated' ? 'start' : 'stop'));
      }

      if (type === 'custom_report') {
        return MENU_LIST.filter(item => ['desensitization', 'disable', 'delete'].includes(item.key));
      }

      if (['bkdata', 'es'].includes(type)) {
        return MENU_LIST.filter(item => ['desensitization', 'delete'].includes(item.key));
      }

      return MENU_LIST.filter(item => item.key !== (status !== 'terminated' ? 'start' : 'stop'));
    };

    /**
     * 获取表格过滤配置
     * @param filter - 过滤选项数组
     * @returns 过滤配置对象
     */
    const getColumnsFilter = (filter: Array<{ label: string; value: string; key?: string }>) => {
      const data = filter.map(item => ({
        ...item,
        label: item.label || item.key || '',
      }));
      return {
        type: 'single',
        list: [{ label: t('全部'), value: '' }, ...data],
        confirmEvents: ['onChange'],
        popupProps: {
          overlayInnerClassName: 't-table__list-filter-input--sticky custom-filter-popup',
        },
      };
    };

    /**
     * 同步获取用户显示名称
     * @param username - 用户名
     * @returns JSX 元素
     */
    const getName = (username: string | undefined | null) => {
      if (!username) {
        return <span>--</span>;
      }
      const displayName = userDisplayNameMap.value.get(username) || username;
      return <span>{displayName}</span>;
    };

    // 所有列定义
    const allColumns = computed(() => [
      {
        title: t('采集名'),
        colKey: 'name',
        sorter: true,
        sortType: 'all',
        cell: (h, { row }: { row: ITableRowData }) => (
          <span
            class='link'
            on-click={() => {
              const type = row.storage_cluster_id !== -1 ? 'view' : 'edit';
              handleEditOperation(row, type);
            }}
          >
            {row.storage_cluster_id === -1 && <span class='link-tag'>{t('未完成')}</span>}
            {row.name}
          </span>
        ),
        fixed: 'left',
        width: 220,
        ellipsis: true,
      },
      {
        title: t('日用量'),
        colKey: 'daily_usage',
        sorter: true,
        sortType: 'all',
        width: 100,
        cell: (h, { row }: { row: ITableRowData }) => <span>{formatBytes(row.daily_usage)}</span>,
      },
      {
        title: t('总用量'),
        colKey: 'total_usage',
        sorter: true,
        sortType: 'all',
        width: 100,
        cell: (h, { row }: { row: ITableRowData }) => <span>{formatBytes(row.total_usage)}</span>,
      },
      {
        title: t('存储名'),
        colKey: 'bk_data_name',
        width: 180,
        ellipsis: true,
      },
      {
        title: t('所属索引集'),
        colKey: 'index_set_name',
        width: 200,
        cell: (h, { row }: { row: ITableRowData }) => {
          const indexSetName = (row.parent_index_sets || []).map(item => ({
            ...item,
            name: item.index_set_name,
          }));
          return row.parent_index_sets?.length > 0 ? (
            <TagMore
              tags={indexSetName}
              title={t('所属索引集')}
            />
          ) : (
            '--'
          );
        },
      },
      {
        title: t('接入类型'),
        colKey: 'log_access_type',
        width: 140,
        cell: (h, { row }: { row: ITableRowData }) => <span>{row.log_access_type_name || '--'}</span>,
        filter: getColumnsFilter(GLOBAL_CATEGORIES_ENUM),
      },
      {
        title: t('日志类型'),
        colKey: 'collector_scenario_id',
        width: 100,
        cell: (h, { row }: { row: ITableRowData }) => <span>{row.collector_scenario_name || '--'}</span>,
        filter: getColumnsFilter(COLLECTOR_SCENARIO_ENUM),
      },
      {
        title: t('集群名'),
        colKey: 'storage_cluster_name',
        minWidth: 140,
        ellipsis: true,
        filter: getColumnsFilter(IFilterValues.value.storage_cluster_name),
      },
      {
        title: t('过期时间'),
        colKey: 'retention',
        cell: (h, { row }: { row: ITableRowData }) => (
          <span class={{ 'text-disabled': row.status === 'stop' }}>
            {row.retention ? `${row.retention} ${t('天')}` : '--'}
          </span>
        ),
        width: 100,
      },
      {
        title: t('标签'),
        colKey: 'tags',
        showTips: false,
        cell: (h, { row }: { row: ITableRowData }) =>
          (row.tags || []).length > 0 ? (
            <TagMore
              tags={row.tags}
              title={t('标签')}
            />
          ) : (
            '--'
          ),
        width: 200,
      },
      {
        title: t('采集状态'),
        colKey: 'status',
        width: 100,
        cell: (h, { row }: { row: ITableRowData }) => renderStatus(row),
        filter: getColumnsFilter(STATUS_ENUM_FILTER),
      },
      {
        title: t('创建人'),
        colKey: 'created_by',
        width: 100,
        cell: (h, { row }: { row: ITableRowData }) => getName(row.created_by),
        filter: getColumnsFilter(IFilterValues.value.created_by),
      },
      {
        title: t('创建时间'),
        colKey: 'created_at',
        sorter: true,
        sortType: 'all',
        width: 200,
        ellipsis: true,
      },
      {
        title: t('更新人'),
        width: 100,
        colKey: 'updated_by',
        cell: (h, { row }: { row: ITableRowData }) => getName(row.updated_by),
        filter: getColumnsFilter(IFilterValues.value.updated_by),
      },
      {
        title: t('更新时间'),
        colKey: 'updated_at',
        sorter: true,
        sortType: 'all',
        width: 200,
        ellipsis: true,
      },
      {
        title: t('操作'),
        colKey: 'operation',
        width: 110,
        fixed: 'right',
        cell: (h, { row }: { row: ITableRowData }) => (
          <div class='table-operation'>
            <span
              class={{
                'link mr-6': true,
                disabled: !getOperatorCanClick(row, 'search'),
              }}
              on-click={() => handleEditOperation(row, 'search')}
            >
              {t('检索')}
            </span>
            <span
              class={{
                link: true,
                disabled: !getOperatorCanClick(row, 'edit'),
              }}
              on-click={() => handleEditOperation(row, 'edit')}
            >
              {t('编辑')}
            </span>
            <span class='bk-icon icon-more more-btn table-more-btn' />
            <div
              style={{ display: 'none' }}
              class='row-menu-popover'
            >
              <div class='row-menu-content'>
                {renderMenu(row).map(item => (
                  <span
                    key={item.key}
                    class={{
                      'menu-item': true,
                      disabled: !getOperatorCanClick(row, item.key),
                    }}
                    on-Click={() => handleMenuClick(item.key, row)}
                  >
                    {item.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ),
      },
    ]);

    /**
     * 销毁所有 tippy 实例
     * 使用 for...of 循环替代 forEach，提高性能
     */
    const destroyTippyInstances = () => {
      for (const instance of tippyInstances) {
        instance?.hide();
        instance?.destroy();
      }
      tippyInstances = [];
    };

    /**
     * 重新刷新表格
     */
    const reloadList = () => {
      pagination.value.current = 1;
      getTableList();
    };

    watch(
      () => listLoading.value,
      (val: boolean) => {
        if (!val) {
          setTimeout(() => {
            initMenuPop();
          }, DELAY_CONSTANTS.MENU_POP_INIT);
        }
      },
    );

    watch(
      () => props.indexSet,
      () => {
        reloadList();
      },
    );

    /**
     * 初始化操作下拉列表的 tippy 实例
     */
    const initMenuPop = () => {
      // 销毁旧实例，避免重复绑定
      destroyTippyInstances();

      const targets = document.querySelectorAll('.v2-log-collection-table .t-table--layout-fixed .table-more-btn');
      // 确保 targets 存在且不为空
      if (!targets || targets.length === 0) {
        return;
      }

      // 将 NodeList 转换为数组，并过滤掉 null 值
      const validTargets = Array.from(targets).filter((target): target is HTMLElement => target instanceof HTMLElement);

      if (validTargets.length === 0) {
        return;
      }

      try {
        const instances = tippy(validTargets, {
          trigger: 'click',
          placement: 'bottom-end',
          theme: 'light table-menu-popover',
          interactive: true,
          hideOnClick: true,
          arrow: false,
          offset: [0, 4],
          appendTo: () => document.body,
          onShow(instance) {
            const ref = instance.reference as HTMLElement;
            ref?.classList?.add('is-hover');
          },
          onHide(instance) {
            const ref = instance.reference as HTMLElement;
            ref?.classList?.remove('is-hover');
          },
          content(reference) {
            const btn = reference as HTMLElement;
            if (!btn) {
              return document.createElement('div');
            }
            // 约定：内容紧跟在按钮后的兄弟元素中
            const container = btn.nextElementSibling as HTMLElement | null;
            const contentNode = container?.querySelector('.row-menu-content') as HTMLElement | null;
            return (contentNode ?? container ?? document.createElement('div')) as unknown as Element;
          },
        });

        // tippy 返回单个或数组，这里统一转为数组
        tippyInstances = Array.isArray(instances) ? instances : [instances];
      } catch (error) {
        console.error('初始化菜单弹窗失败:', error);
      }
    };

    onMounted(() => {
      getCollectorFieldEnums();
      nextTick(() => {
        if (!authGlobalInfo.value) {
          checkCreateAuth();
        }
        listLoading.value = true;
        // 初始化时计算表格最大高度
        calculateMaxTableHeight();
        // 监听窗口大小变化
        window.addEventListener('resize', handleWindowResize);
      });
    });

    onBeforeUnmount(() => {
      destroyTippyInstances();
      // 清除状态轮询定时器
      stopCollectStatusTimer();
      // 移除窗口大小变化监听
      window.removeEventListener('resize', handleWindowResize);
      listInterfaceCancel.value?.();
    });

    /**
     * 获取存储用量
     * @param indexSetIds - 索引集ID列表
     */
    const getStorageUsage = (indexSetIds: Array<number | string>) => {
      if (indexSetIds.length === 0) {
        return;
      }

      $http
        .request('collect/getStorageUsage', {
          data: {
            bk_biz_id: bkBizId.value,
            index_set_ids: indexSetIds,
          },
        })
        .then(res => {
          const usageMap = new Map<number | string, IStorageUsageItem>();
          // 构建使用量映射表，提高查找效率
          for (const item of res.data || []) {
            if (item.index_set_id != null) {
              usageMap.set(Number(item.index_set_id), item);
            }
          }

          // 更新表格数据
          tableList.value = tableList.value.map(item => {
            const usageInfo = usageMap.get(Number(item.index_set_id));
            if (usageInfo) {
              const { index_set_id: _id, ...rest } = usageInfo;
              return {
                ...item,
                ...rest,
              };
            }
            return item;
          });
        })
        .catch(error => {
          console.log('获取存储用量失败:', error);
        });
    };
    /**
     * 停止轮询状态
     */
    const stopCollectStatusTimer = () => {
      if (collectStatusTimer) {
        clearTimeout(collectStatusTimer);
        collectStatusTimer = null;
      }
    };
    /**
     * 轮询状态
     * @param collectorConfigIdList
     */
    const getCollectStatus = (collectorConfigIdList: Array<number | string>) => {
      if (collectorConfigIdList.length === 0) {
        return;
      }
      $http
        .request('collect/getCollectorStatus', {
          data: {
            collector_config_id_list: collectorConfigIdList,
          },
        })
        .then(res => {
          if (!res.result) {
            stopCollectStatusTimer();
            return;
          }
          const isHasRunning = res.data.filter(item => item.status === 'running').length > 0;
          tableList.value = tableList.value.map(item => {
            const info = res.data.find(val => val.collector_id === item.collector_config_id);
            const { status_name, status } = info || {};
            return {
              ...item,
              status,
              status_name,
            };
          });

          // 如果还有运行中的状态，则10s后继续轮询
          if (isHasRunning) {
            // 清除之前的定时器（如果存在）
            stopCollectStatusTimer();
            collectStatusTimer = setTimeout(() => {
              getCollectStatus(collectorConfigIdList);
            }, 10000);
          } else {
            // 没有运行中的状态，停止轮询
            stopCollectStatusTimer();
          }
        })
        .catch(() => {
          // 请求失败时也停止轮询
          stopCollectStatusTimer();
        });
    };

    /**
     * 获取列表数据
     */
    const getTableList = async () => {
      try {
        listInterfaceCancel.value?.();
        listLoading.value = true;
        tableList.value = [];
        const { current, pageSize } = pagination.value;
        const params: Record<string, unknown> = {
          space_uid: spaceUid.value,
          page: current,
          pagesize: pageSize,
        };

        if (searchKey.value) {
          params.keyword = searchKey.value;
        }

        if (conditions.value.length > 0) {
          params.conditions = conditions.value;
        }

        const indexSetId = (props.indexSet as IListItemData)?.index_set_id;
        if (indexSetId && indexSetId !== 'all') {
          params.parent_index_set_id = indexSetId;
        }

        const res = await $http.request(
          'collect/newCollectList',
          {
            data: params,
          },
          {
            cancelToken: new CancelToken(c => {
              listInterfaceCancel.value = c;
              isCancelToken.value = true;
            }),
          },
        );
        listLoading.value = false;
        tableList.value = (res.data?.list || []) as ITableRowData[];
        pagination.value.total = res.data?.total || 0;
        // 收集索引集ID并保存原始数据顺序
        const indexSetIds: Array<number | string> = [];
        const collectorConfigIds: Array<number | string> = [];
        originalOrderMap.value = new Map();

        for (let index = 0; index < tableList.value.length; index++) {
          const item = tableList.value[index];
          item.collector_config_id && collectorConfigIds.push(item.collector_config_id);
          if (item.index_set_id !== null) {
            indexSetIds.push(item.index_set_id);
            originalOrderMap.value.set(item.index_set_id, index);
          }
        }
        // 获取存储用量 & 状态
        getStorageUsage(indexSetIds);
        getCollectStatus(collectorConfigIds);

        // 批量获取用户信息
        const userIds = new Set<string>();
        for (const item of tableList.value) {
          if (item.created_by) {
            userIds.add(item.created_by);
          }
          if (item.updated_by) {
            userIds.add(item.updated_by);
          }
        }
        if (userIds.size > 0) {
          tenantManager
            .batchGetUserDisplayInfo(Array.from(userIds))
            .then(userMap => {
              // 更新用户信息映射（创建新 Map 以确保响应式更新）
              const newMap = new Map(userDisplayNameMap.value);
              for (const [userId, userInfo] of userMap.entries()) {
                if (userInfo?.display_name) {
                  newMap.set(userId, userInfo.display_name);
                }
              }
              userDisplayNameMap.value = newMap;
            })
            .catch(error => {
              console.log('批量获取用户信息失败:', error);
            });
        }
      } catch (error) {
        !isCancelToken.value && console.log('获取列表数据失败:', error, isCancelToken.value);
      }
    };

    /**
     * 从过滤选项数组中提取用户ID
     * @param items - 过滤选项数组
     * @returns 用户ID数组
     */
    const extractUserIds = (items: Array<{ key?: string; [key: string]: unknown }>): string[] => {
      return (items || []).map(item => item.key).filter(Boolean) as string[];
    };

    /**
     * 处理过滤选项，添加用户显示名称
     * @param items - 过滤选项数组
     * @param userInfoMap - 用户信息映射
     * @returns 处理后的过滤选项数组
     */
    const processFilterItemsWithUserInfo = (
      items: Array<{ key?: string; label?: string; [key: string]: unknown }>,
      userInfoMap: Map<string, { display_name: string }>,
    ) => {
      return (items || []).map(item => ({
        ...item,
        label: userInfoMap.get(item.key || '')?.display_name || item.key || item.label || '',
      }));
    };

    /**
     * 获取枚举值
     */
    const getCollectorFieldEnums = async () => {
      try {
        const res = await $http.request('collect/collectorFieldEnums', {
          query: { space_uid: spaceUid.value },
        });
        if (res.data) {
          const { created_by, updated_by } = res.data;

          // 提取所有用户ID并去重
          const createdByUserIds = extractUserIds(created_by || []);
          const updatedByUserIds = extractUserIds(updated_by || []);
          const allUserIds = [...new Set([...createdByUserIds, ...updatedByUserIds])];

          // 批量获取用户信息
          let userInfoMap = new Map<string, { display_name: string }>();
          if (allUserIds.length > 0) {
            userInfoMap = await tenantManager.batchGetUserDisplayInfo(allUserIds);
          }

          // 处理过滤选项，添加用户显示名称
          const processedCreatedBy = processFilterItemsWithUserInfo(created_by || [], userInfoMap);
          const processedUpdatedBy = processFilterItemsWithUserInfo(updated_by || [], userInfoMap);

          IFilterValues.value = {
            ...IFilterValues.value,
            ...res.data,
            created_by: processedCreatedBy,
            updated_by: processedUpdatedBy,
          };
        }
      } catch (error) {
        console.log('获取字段枚举失败:', error);
      }
    };

    /**
     * 处理采集项检测
     * @param checkRecordId - 检测记录ID
     */
    const handleCollectorCheck = async (checkRecordId: string | number) => {
      try {
        const res = await $http.request('collect/getCheckInfos', {
          data: {
            check_record_id: checkRecordId,
          },
        });
        if (res.data) {
          checkInfo.value = res.data.infos || '';

          if (!res.data.finished && isShowDetection.value) {
            // 未完成检测 且 弹窗未关闭则继续请求
            setTimeout(() => {
              handleCollectorCheck(checkRecordId);
            }, 1000);
          }
        }
      } catch (error) {
        console.log('获取检测信息失败:', error);
      }
    };

    /**
     * 删除采集项
     * @param row - 表格行数据
     */
    const requestDeleteCollect = (row: ITableRowData) => {
      $http
        .request('collect/deleteCollect', {
          params: {
            collector_config_id: row.collector_config_id,
          },
        })
        .then(res => {
          if (res.result) {
            showMessage(t('删除成功'));
            reloadList();
          }
        })
        .catch(() => {
          showMessage(t('删除失败'), 'error');
        });
    };

    /**
     * 处理菜单点击事件
     * @param key - 菜单项key
     * @param row - 表格行数据
     */
    const handleMenuClick = (key: string, row: ITableRowData) => {
      currentRow.value = row;
      // 关闭所有 tippy 实例
      for (const instance of tippyInstances) {
        instance?.hide();
      }

      // 启用
      if (key === 'start') {
        $http
          .request('collect/startCollect', {
            params: {
              collector_config_id: row.collector_config_id,
            },
          })
          .then(res => {
            if (res.result) {
              reloadList();
            }
          })
          .catch(() => {
            showMessage(t('启用失败'), 'error');
          });
        return;
      }

      // 停用
      if (key === 'stop') {
        showCollectIssuedSlider.value = true;
        return;
      }

      // 删除操作
      if (key === 'delete') {
        if (row.status !== 'running') {
          window.mainComponent?.$bkInfo({
            type: 'warning',
            subTitle: t('当前采集项名称为{n}，确认要删除？', { n: row.collector_config_name || row.name }),
            confirmFn: () => {
              requestDeleteCollect(row);
            },
          });
        }
        return;
      }

      // 一键检测
      if (key === 'one_key_check') {
        $http
          .request('collect/runCheck', {
            data: {
              collector_config_id: row.collector_config_id,
            },
          })
          .then(res => {
            if (res.data?.check_record_id) {
              isShowDetection.value = true;
              const checkRecordId = res.data.check_record_id;
              handleCollectorCheck(checkRecordId);
            }
          })
          .catch(error => {
            console.log('一键检测失败:', error);
          });
        return;
      }

      handleEditOperation(row, key);
    };

    /**
     * 处理表格分页变化
     * @param pageInfo - 分页信息
     */
    const handlePageChange = (pageInfo: IPaginationInfo) => {
      pagination.value.current = pageInfo.current;
      pagination.value.pageSize = pageInfo.pageSize;
      getTableList();
    };

    /**
     * 新增采集项
     */
    const handleCreateOperation = () => {
      const { index_set_id: indexSetId } = props.indexSet;
      operateHandler({}, 'add', 'linux', indexSetId);
    };

    /**
     * 处理编辑操作
     * @param row - 表格行数据
     * @param type - 操作类型
     */
    const handleEditOperation = (row: ITableRowData, type: string) => {
      const { index_set_id: indexSetId } = props.indexSet;
      operateHandler(row, type, row.log_access_type, indexSetId);
    };

    /**
     * 处理表格过滤变化
     * @param filters - 过滤对象
     */
    const handleFilterChange = (filters: Record<string, string>) => {
      // 同步更新 filterValue
      filterValue.value = { ...filterValue.value, ...filters };

      // 创建新的搜索条件数组
      const newConditions: IFilterCondition[] = [];

      for (const key of Object.keys(filters || {})) {
        if (filters[key]) {
          newConditions.push({
            key,
            value: [filters[key]],
          });
        }
      }

      // 更新搜索条件和过滤条件
      conditions.value = newConditions;
      // 重新获取表格数据
      reloadList();
    };

    /**
     * 处理排序变化
     * @param sortInfo - 排序信息
     */
    const sortChange = (sortInfo: ISortConfig): void => {
      sortConfig.value = sortInfo;
      handleSort(sortInfo);
    };

    /**
     * 将日期字符串转换为时间戳
     * @param dateStr - 日期字符串，格式如 "2025-11-21 03:43:19+0800"
     * @returns 时间戳，如果转换失败返回 0
     */
    const parseDateToTimestamp = (dateStr: string | undefined | null): number => {
      if (!dateStr) return 0;
      try {
        const date = new Date(dateStr);
        return Number.isNaN(date.getTime()) ? 0 : date.getTime();
      } catch {
        return 0;
      }
    };

    /**
     * 处理表格排序
     * @param sort - 排序配置
     */
    const handleSort = (sort: ISortConfig): void => {
      if (sort?.sortBy) {
        const { descending, sortBy } = sort;
        tableList.value = [...tableList.value].sort((a, b) => {
          let aValue: number | string = a[sortBy] as number | string;
          let bValue: number | string = b[sortBy] as number | string;

          // 处理日期字段：转换为时间戳
          if (sortBy === 'created_at' || sortBy === 'updated_at') {
            aValue = parseDateToTimestamp(aValue as string);
            bValue = parseDateToTimestamp(bValue as string);
          }
          // 处理 name 字段：字符串比较
          else if (sortBy === 'name') {
            aValue = (aValue as string) || '';
            bValue = (bValue as string) || '';
            const comparison = (aValue as string).localeCompare(bValue as string);
            return descending ? -comparison : comparison;
          }

          // 其他字段：数值比较
          const result = descending ? Number(bValue) - Number(aValue) : Number(aValue) - Number(bValue);
          return result;
        });
      } else {
        // 取消排序，恢复原始顺序
        if (originalOrderMap.value.size > 0) {
          tableList.value = [...tableList.value].sort((a, b) => {
            const aOrder = originalOrderMap.value.get(a.index_set_id) ?? 0;
            const bOrder = originalOrderMap.value.get(b.index_set_id) ?? 0;
            return aOrder - bOrder;
          });
        }
      }
    };

    /**
     * 判断是否有过滤条件或搜索关键词
     * @returns 是否有过滤条件
     */
    const hasFilterOrSearch = computed(() => {
      const hasSearch = searchKey.value && searchKey.value !== '' && searchKey.value !== '1201';
      const hasFilter = conditions.value.length > 0;
      return hasSearch || hasFilter;
    });

    /**
     * 处理空状态操作
     * @param type - 操作类型
     */
    const handleEmptyOperation = (type: string) => {
      if (type === 'clear-filter') {
        conditions.value = [];
      }
      searchKey.value = '';
      reloadList();
    };

    return () => (
      <div
        ref={containerRef}
        class='v2-log-collection-table'
      >
        <div class='v2-log-collection-table-header'>
          <div class='header-left'>
            {(props.indexSet as IListItemData)?.index_set_name || ''}
            <span class='table-header-count'>{(props.indexSet as IListItemData)?.index_count || 0}</span>
          </div>
        </div>
        <div class='v2-log-collection-table-tool'>
          <div class='tool-btns'>
            <bk-button
              icon='plus'
              theme='primary'
              on-Click={handleCreateOperation}
            >
              {t('采集项')}
            </bk-button>
          </div>
          <bk-input
            class='tool-search-select'
            value={searchKey.value}
            placeholder={t('搜索 采集名、存储名')}
            clearable
            right-icon={'bk-icon icon-search'}
            on-input={(val: string) => {
              searchKey.value = val;
            }}
            on-clear={() => {
              searchKey.value = '';
              reloadList();
            }}
            on-enter={() => {
              reloadList();
            }}
          />
        </div>
        <div
          ref={tableMainRef}
          class='v2-log-collection-table-main'
        >
          <TableComponent
            class='log-collection-table'
            columns={allColumns.value}
            data={tableList.value}
            sortConfig={sortConfig.value}
            loading={listLoading.value}
            on-page-change={handlePageChange}
            pagination={pagination.value}
            height={maxTableHeight.value}
            on-sort-change={sortChange}
            on-filter-change={handleFilterChange}
            filterValue={filterValue.value}
            on-empty-click={handleEmptyOperation}
            colKeyMap={FIELD_ID_TO_COL_KEY_MAP}
            settingFields={SETTING_FIELDS}
            emptyType={emptyType.value}
          />

          {/* 一键检测弹窗 */}
          <bk-sideslider
            width={800}
            class='collection-report-detail'
            before-close={() => {
              isShowDetection.value = false;
            }}
            scopedSlots={{
              header: () => <span class='title'>{t('一键检测')}</span>,
              content: () => <div class='check-info'>{checkInfo.value}</div>,
            }}
            is-show={isShowDetection.value}
            quick-close={true}
            transfer
          />
          {/* 停用 */}
          <CollectIssuedSlider
            isShow={showCollectIssuedSlider.value}
            collectorConfigId={
              currentRow.value.collector_config_id ? Number(currentRow.value.collector_config_id) : undefined
            }
            status={currentRow.value.status}
            config={currentRow.value}
            isStopCollection={true}
            on-change={(value: boolean) => {
              showCollectIssuedSlider.value = value;
            }}
            on-refresh={reloadList}
          />
        </div>
      </div>
    );
  },
});
