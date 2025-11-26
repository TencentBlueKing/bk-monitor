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
import useStore from '@/hooks/use-store';
import ItemSkeleton from '@/skeleton/item-skeleton';
import tippy, { type Instance } from 'tippy.js';
import { ConfigProvider as TConfigProvider, Table as TTable } from 'tdesign-vue';
import { getScenarioIdType, formatBytes, getOperatorCanClick, showMessage } from '../../utils';
import useResizeObserver from '@/hooks/use-resize-observe';
import { projectManages } from '@/common/util';
import CollectIssuedSlider from '../business-comp/step3/collect-issued-slider';
import $http from '@/api';
// import { useRouter } from 'vue-router/composables';

import { useCollectList } from '../../hook/useCollectList';
import {
  STATUS_ENUM,
  SETTING_FIELDS,
  MENU_LIST,
  GLOBAL_CATEGORIES_ENUM,
  COLLECTOR_SCENARIO_ENUM,
  STATUS_ENUM_FILTER,
} from '../../utils';
import TagMore from '../common-comp/tag-more';

import type { IListItemData } from '../../type';

import './table-list.scss';
import 'tdesign-vue/es/style/index.css';

export type SearchKeyItem = {
  id: string;
  name: string;
  values: any[];
};

export default defineComponent({
  name: 'TableList',
  props: {
    indexSet: {
      type: Object as PropType<IListItemData>,
      default: () => ({}),
    },
    data: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },

  emits: [],

  setup(props, { emit }) {
    const { t } = useLocale();
    const showCollectIssuedSlider = ref(false);
    /**
     * 是否展示一键检测
     */
    const isShowDetection = ref(false);
    const checkInfo = ref('');
    const globalLocale = {
      table: {
        sortIcon: () => <i class='bk-icon icon-down-shape sort-icon' />,
        filterIcon: () => <i class='bk-icon icon-funnel filter-icon' />,
      },
    };
    // const router = useRouter();
    const store = useStore();
    // 使用自定义 hook 管理状态
    const { authGlobalInfo, operateHandler, checkCreateAuth, spaceUid, bkBizId } = useCollectList();
    const tableList = ref([]);
    const listLoading = ref(false);
    // 保存原始数据顺序的索引映射（用于恢复排序）
    const originalOrderMap = ref<Map<number | string, number>>(new Map());

    // 容器和表格高度相关
    const containerRef = ref<HTMLElement | null>(null);
    const tableMainRef = ref<HTMLElement | null>(null);
    const maxTableHeight = ref<number>(0); // 表格最大可用高度

    let tippyInstances: Instance[] = [];
    let columnConfigTippyInstance: Instance | null = null;
    const columnConfigTriggerRef = ref<HTMLElement | null>(null);
    const columnConfigContentRef = ref<HTMLElement | null>(null);
    const searchKey = ref<SearchKeyItem[]>([]);
    const createdValues = ref([]); // 创建者筛选值
    const updatedByValues = ref([]); // 更新者筛选值
    // 过滤条件
    const conditions = ref<Array<{ key: string; value: string[] }>>([
      { key: 'name', value: ['demodemo0723001', 'zxp02252', 'test_012', 'hrlspf', '0911_test', 'test_012_clone'] },
    ]);

    const pagination = ref({
      current: 1,
      total: props.data.length,
      pageSize: 10,
      limitList: [10, 20, 50],
    });

    const collectProject = computed(() => projectManages(store.state.topMenu, 'collection-item'));

    const sortConfig = ref({});

    // 列配置相关状态
    const isShowColumnConfig = ref(false);
    // SETTING_FIELDS 中的 label 已经是字符串，直接使用
    const columnConfigFields = ref([...SETTING_FIELDS]);
    // 字段映射：SETTING_FIELDS 的 id 映射到 columns 的 colKey
    const fieldIdToColKeyMap: Record<string, string> = {
      collector_config_name: 'name',
      storage_usage: 'daily_usage',
      total_usage: 'total_usage',
      table_id: 'bk_data_name',
      index_set_id: 'index_set_name',
      category_name: 'scenario_name',
      collector_scenario_name: 'collector_scenario_name',
      storage_cluster_name: 'storage_cluster_name',
      retention: 'retention',
      label: 'tags',
      es_host_state: 'status',
      updated_by: 'updated_by',
      updated_at: 'updated_at',
    };
    // 默认显示的列（disabled: true 的列）
    const defaultVisibleColumns = computed(() => {
      return columnConfigFields.value
        .filter(field => field.disabled)
        .map(field => fieldIdToColKeyMap[field.id] || field.id);
    });
    // 用户选择的可见列（初始值为所有列）
    const visibleColumns = ref<string[]>(
      columnConfigFields.value.map(field => fieldIdToColKeyMap[field.id] || field.id),
    );
    // 临时选择的列（用于确认前）
    const tempVisibleColumns = ref<string[]>([]);

    // 高度计算相关常量
    const HEIGHT_CONSTANTS = {
      MIN_TABLE_HEIGHT: 250, // 最小表格高度（至少显示 6-7 行数据）
      COLUMNS_HEIGHT: 50,
    };

    /**
     * 使用窗口高度作为后备方案计算表格高度
     * @returns 计算出的表格高度
     */
    const calculateHeightByWindow = (): number => {
      const windowHeight = window.innerHeight;
      const fixedElementsHeight = 400;
      return Math.max(HEIGHT_CONSTANTS.MIN_TABLE_HEIGHT, windowHeight - fixedElementsHeight);
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
     * 3. 从容器高度中减去固定元素高度（150px），得到表格可用高度
     * 4. 确保计算出的高度不小于最小表格高度（MIN_TABLE_HEIGHT）
     * 5. 根据实际数据量和分页大小进行最终调整：
     *    - 如果分页数据的总高度超过计算出的最大高度，则使用最大高度（启用滚动）
     *    - 如果数据量较少，则根据实际行数计算高度（避免空白区域）
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

        // 计算表格最大可用高度：容器高度 - 所有固定元素高度（头部、工具栏、分页器等）
        const calculatedMaxHeight = containerHeight - 150;

        // 确保高度在合理范围内（不小于最小高度）
        maxTableHeight.value = Math.max(HEIGHT_CONSTANTS.MIN_TABLE_HEIGHT, calculatedMaxHeight);

        // 根据实际数据量和分页大小进行最终调整
        const listLen = tableList.value.length;
        const totalListHeight = listLen * HEIGHT_CONSTANTS.COLUMNS_HEIGHT + 5;

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
      200,
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
        }, 150);
      },
    );

    // 完整的搜索字段数据（原始数据，不修改）
    const allSearchFilterData = [
      {
        name: t('采集名'),
        id: 'name',
      },
      {
        name: t('存储名'),
        id: 'bk_data_name',
      },
      {
        name: t('集群名'),
        id: 'scenario_name',
      },
      {
        name: t('创建人'),
        id: 'created_by',
      },
      {
        name: t('更新人'),
        id: 'updated_by',
      },
    ];

    // 可用的搜索字段数据（动态过滤）
    const searchFilterData = ref([...allSearchFilterData]);
    /** 状态渲染 */
    const renderStatus = (key: string) => {
      const info = STATUS_ENUM.find(item => item.value === key);
      return info ? <span class={`table-status ${info.value}`}>{info.label}</span> : '--';
    };

    const renderMenu = row => {
      const { scenario_id, environment, collector_scenario_id } = row;
      const typeConfig = getScenarioIdType(scenario_id, environment, collector_scenario_id);
      if (!typeConfig) {
        return MENU_LIST;
      }
      if (typeConfig.value === 'custom_report') {
        return MENU_LIST.filter(item => ['clean', 'desensitization', 'disable', 'delete'].includes(item.key));
      }
      if (['bkdata', 'es'].includes(typeConfig.value)) {
        return MENU_LIST.filter(item => ['desensitization', 'delete'].includes(item.key));
      }
      return MENU_LIST;
    };

    // 所有列定义
    const allColumns = [
      {
        title: t('采集名'),
        colKey: 'name',
        sorter: true,
        sortType: 'all',
        cell: (h, { row }) => (
          <span
            class='link'
            on-click={() => handleEditOperation(row, 'view')}
          >
            {row.name}
          </span>
        ),
        fixed: 'left',
        minWidth: 180,
        ellipsis: true,
      },
      {
        title: t('日用量'),
        colKey: 'daily_usage',
        sorter: true,
        sortType: 'all',
        minWidth: 100,
        cell: (h, { row }) => <span>{formatBytes(row.daily_usage)}</span>,
      },
      {
        title: t('总用量'),
        colKey: 'total_usage',
        sorter: true,
        sortType: 'all',
        minWidth: 100,
        cell: (h, { row }) => <span>{formatBytes(row.total_usage)}</span>,
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
        cell: (h, { row }) => {
          const indexSetName = row.parent_index_sets.map(item => {
            return {
              ...item,
              name: item.index_set_name,
            };
          });
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
        colKey: 'scenario_name',
        width: 100,
        filter: {
          type: 'single',
          list: [{ label: t('全部'), value: '' }, ...GLOBAL_CATEGORIES_ENUM],
          // confirm to search and hide filter popup
          confirmEvents: ['onChange'],
          // 支持透传全部 Popup 组件属性
          popupProps: {
            overlayInnerClassName: 't-table__list-filter-input--sticky custom-filter-popup',
          },
        },
      },
      {
        title: t('日志类型'),
        colKey: 'collector_scenario_name',
        width: 100,
        filter: {
          type: 'single',
          list: [{ label: t('全部'), value: '' }, ...COLLECTOR_SCENARIO_ENUM],
          // confirm to search and hide filter popup
          confirmEvents: ['onChange'],
          // 支持透传全部 Popup 组件属性
          popupProps: {
            overlayInnerClassName: 't-table__list-filter-input--sticky custom-filter-popup',
          },
        },
      },
      {
        title: t('集群名'),
        colKey: 'storage_cluster_name',
        minWidth: 140,
        ellipsis: true,
      },
      {
        title: t('过期时间'),
        colKey: 'retention',
        cell: (h, { row }) => (
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
        cell: (h, { row }) =>
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
        cell: (h, { row }) => renderStatus(row.status),
        filter: {
          type: 'single',
          list: [{ label: t('全部'), value: '' }, ...STATUS_ENUM_FILTER],
          // confirm to search and hide filter popup
          confirmEvents: ['onChange'],
          // 支持透传全部 Popup 组件属性
          popupProps: {
            overlayInnerClassName: 't-table__list-filter-input--sticky custom-filter-popup',
          },
        },
      },
      {
        title: t('创建人'),
        colKey: 'created_by',
        width: 100,
        filterValue: createdValues.value,
        filters: [],
      },
      {
        title: t('创建时间'),
        colKey: 'created_at',
        sorter: true,
        sortType: 'all',
        width: 200,
      },
      {
        title: t('更新人'),
        width: 100,
        colKey: 'updated_by',
        filterValue: updatedByValues.value,
        filters: [],
      },
      {
        title: t('更新时间'),
        colKey: 'updated_at',
        sorter: true,
        sortType: 'all',
        width: 200,
      },
      {
        title: t('操作'),
        colKey: 'operation',
        width: 110,
        fixed: 'right',
        cell: (h, { row }) => (
          <div class='table-operation'>
            <span
              class={{
                'link mr-6': true,
                disabled: !getOperatorCanClick(row, 'search', collectProject.value),
              }}
              on-click={() => handleEditOperation(row, 'search')}
            >
              {t('检索')}
            </span>
            <span
              class={{
                link: true,
                disabled: !getOperatorCanClick(row, 'edit', collectProject.value),
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
                      disabled: !getOperatorCanClick(row, item.key, collectProject.value),
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
    ];

    // 根据可见列过滤后的列配置
    const columns = computed(() => {
      // 操作列始终显示
      const operationCol = allColumns.find(col => col.colKey === 'operation');
      // 根据 visibleColumns 过滤列，但始终包含默认列和操作列
      const filteredColumns = allColumns.filter(col => {
        if (col.colKey === 'operation') return false; // 操作列单独处理
        // 默认列始终显示
        if (defaultVisibleColumns.value.includes(col.colKey)) return true;
        // 其他列根据 visibleColumns 决定
        return visibleColumns.value.includes(col.colKey);
      });
      // 将操作列添加到末尾
      return operationCol ? [...filteredColumns, operationCol] : filteredColumns;
    });

    /** 销毁所有tippy */
    const destroyTippyInstances = () => {
      // biome-ignore lint/complexity/noForEach: <explanation>
      tippyInstances.forEach(i => {
        try {
          i.hide();
          i.destroy();
        } catch (_) {}
      });
      tippyInstances = [];
    };
    watch(
      () => listLoading.value,
      val => {
        if (!val) {
          setTimeout(() => {
            initMenuPop();
          }, 1000);
        }
      },
    );
    watch(
      () => props.indexSet,
      () => {
        pagination.value.current = 1;
        getTableList();
      },
    );

    /** 渲染操作下拉列表 */
    const initMenuPop = () => {
      // 销毁旧实例，避免重复绑定
      destroyTippyInstances();

      const targets = document.querySelectorAll('.v2-log-collection-table .t-table--layout-fixed .table-more-btn');
      if (!targets.length) {
        return;
      }

      const instances = tippy(targets as unknown as HTMLElement[], {
        trigger: 'click',
        placement: 'bottom-end',
        theme: 'light table-menu-popover',
        interactive: true,
        hideOnClick: true,
        arrow: false,
        offset: [0, 4],
        appendTo: () => document.body,
        onShow(instance) {
          (instance.reference as HTMLElement).classList.add('is-hover');
        },
        onHide(instance) {
          (instance.reference as HTMLElement).classList.remove('is-hover');
        },
        content(reference) {
          const btn = reference as HTMLElement;
          // 约定：内容紧跟在按钮后的兄弟元素中
          const container = btn.nextElementSibling as HTMLElement | null;
          const contentNode = container?.querySelector('.row-menu-content') as HTMLElement | null;
          return (contentNode ?? container ?? document.createElement('div')) as unknown as Element;
        },
      });

      // tippy 返回单个或数组，这里统一转为数组
      tippyInstances = Array.isArray(instances) ? instances : [instances];
    };

    // 初始化列配置 tippy
    const initColumnConfigTippy = () => {
      if (!columnConfigTriggerRef.value || !columnConfigContentRef.value) {
        return;
      }

      // 销毁旧实例
      if (columnConfigTippyInstance) {
        columnConfigTippyInstance.destroy();
        columnConfigTippyInstance = null;
      }

      columnConfigTippyInstance = tippy(columnConfigTriggerRef.value, {
        trigger: 'click',
        placement: 'bottom-end',
        theme: 'light column-config-popover',
        interactive: true,
        hideOnClick: 'toggle', // 点击外部区域时关闭，点击触发器时切换
        arrow: false,
        offset: [-52, 4],
        appendTo: () => document.body,
        onShow() {
          handleOpenColumnConfig();
        },
        onHide() {
          // 直接更新状态，不要调用 handleCloseColumnConfig，避免循环
          isShowColumnConfig.value = false;
        },
        content() {
          // 使用函数返回内容，确保能正确获取元素
          if (!columnConfigContentRef.value) {
            return document.createElement('div');
          }
          return columnConfigContentRef.value as unknown as Element;
        },
      });
    };

    onMounted(() => {
      nextTick(() => {
        !authGlobalInfo.value && checkCreateAuth();
        listLoading.value = true;
        // 初始化时计算表格最大高度
        calculateMaxTableHeight();
        // 监听窗口大小变化
        window.addEventListener('resize', handleWindowResize);
        // 初始化列配置 tippy - 使用 nextTick 确保 DOM 已渲染
        nextTick(() => {
          initColumnConfigTippy();
        });
      });
    });

    onBeforeUnmount(() => {
      destroyTippyInstances();
      // 销毁列配置 tippy
      if (columnConfigTippyInstance) {
        columnConfigTippyInstance.destroy();
        columnConfigTippyInstance = null;
      }
      // 移除窗口大小变化监听
      window.removeEventListener('resize', handleWindowResize);
    });

    /**
     * 获取存储用量
     * @param index_set_ids 索引集ID列表
     */
    const getStorageUsage = index_set_ids => {
      $http
        .request('collect/getStorageUsage', {
          data: {
            bk_biz_id: bkBizId.value,
            index_set_ids: index_set_ids.filter(id => id != null && id !== ''),
          },
        })
        .then(res => {
          tableList.value = tableList.value.map(item => {
            const info = res.data.find(val => Number(val.index_set_id) === item.index_set_id);
            const { index_set_id, ...rest } = info || {};
            return {
              ...item,
              ...rest,
            };
          });
        });
    };
    /**
     * 获取采集状态
     */
    const getCollectStatus = index_set_ids => {
      $http
        .request('collect/getCollectStatus', {
          query: {
            collector_id_list: index_set_ids.filter(id => id != null && id !== '').join(','),
          },
        })
        .then(res => {
          if (!res.result) {
            return;
          }
          tableList.value = tableList.value.map(item => {
            const info = res.data.find(val => val.collector_id === item.index_set_id);
            const { status_name, status } = info || {};
            return {
              ...item,
              status,
              status_name,
            };
          });
        })
        .catch(() => {
          // 请求失败时也停止轮询
        });
    };

    /**
     * 获取列表数据
     */
    const getTableList = async () => {
      try {
        listLoading.value = true;
        const { current, pageSize } = pagination.value;
        const params = {
          space_uid: spaceUid.value,
          page: current,
          pagesize: pageSize,
          conditions: conditions.value.length > 0 ? conditions.value : undefined,
        };
        const indexSetId = (props.indexSet as IListItemData)?.index_set_id;
        if (indexSetId && indexSetId !== 'all') {
          Object.assign(params, {
            parent_index_set_id: indexSetId,
          });
        }
        const res = await $http.request('collect/newCollectList', {
          data: params,
        });
        const index_set_ids = [];
        tableList.value = res.data?.list || [];
        pagination.value.total = res.data?.total || 0;
        tableList.value.map(item => index_set_ids.push(item.index_set_id));

        // 保存原始数据顺序的索引映射
        originalOrderMap.value = new Map();
        tableList.value.forEach((item, index) => {
          originalOrderMap.value.set(item.index_set_id, index);
        });

        /**
         * 获取存储用量
         */
        if (index_set_ids.length > 0) {
          getStorageUsage(index_set_ids);
          getCollectStatus(index_set_ids);
        }
      } catch (e) {
        console.log(e);
      } finally {
        listLoading.value = false;
      }
    };

    const handleCollectorCheck = async checkRecordId => {
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
    };

    // 删除
    const requestDeleteCollect = row => {
      $http
        .request('collect/deleteCollect', {
          params: {
            collector_config_id: row.collector_config_id,
          },
        })
        .then(res => {
          if (res.result) {
            // 重新获取表格数据
            showMessage(t('删除成功'));
            pagination.value.current = 1;
            getTableList();
          }
        })
        .catch(() => {
          showMessage(t('删除失败', 'err'));
        });
    };

    const handleMenuClick = (key: string, row: any) => {
      // 关闭 tippy
      for (const i of tippyInstances) {
        i?.hide();
      }
      console.log(key, row);
      /**
       * 停用
       */
      if (key === 'stop') {
        showCollectIssuedSlider.value = true;
        return;
      }
      /**
       * 删除操作
       */
      if (key === 'delete') {
        if (!collectProject.value) return;
        if (!row.is_active && row.status !== 'running') {
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
      /** 一键检测 */
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
          });
        return;
      }
      handleEditOperation(row, key);
    };
    /**
     * 表格分页
     * @param pageInfo
     */
    const handlePageChange = pageInfo => {
      pagination.value.current = pageInfo.current;
      pagination.value.pageSize = pageInfo.pageSize;
      getTableList();
    };
    /** 新增采集项 */
    const handleCreateOperation = () => {
      operateHandler({}, 'add', 'host_log');
    };

    const handleEditOperation = (row: any, type: string) => {
      const { scenario_id, environment, collector_scenario_id } = row;
      const typeConfig = getScenarioIdType(scenario_id, environment, collector_scenario_id);
      operateHandler(row, type, typeConfig.value);
    };
    /** 表格过滤 */

    const handleFilterChange = (filters: any) => {
      // 创建新的搜索条件数组
      const newSearchKey = [...searchKey.value];
      const newConditions: Array<{ key: string; value: any[] }> = [];

      // 处理 scenario_name (接入类型) 筛选器
      if (filters.scenario_name && filters.scenario_name.length > 0 && filters.scenario_name[0] !== '') {
        newConditions.push({
          key: 'scenario_id',
          value: [filters.scenario_name],
        });
      }

      // 处理 collector_scenario_name (日志类型) 筛选器
      if (
        filters.collector_scenario_name &&
        filters.collector_scenario_name.length > 0 &&
        filters.collector_scenario_name[0] !== ''
      ) {
        newConditions.push({
          key: 'collector_scenario_id',
          value: [filters.collector_scenario_name],
        });
      }

      // 处理 status (采集状态) 筛选器
      if (filters.status && filters.status.length > 0 && filters.status[0] !== '') {
        // 将字符串按照逗号拆分为数组
        const statusValue = Array.isArray(filters.status) ? filters.status[0] : filters.status;
        const statusArray =
          typeof statusValue === 'string'
            ? statusValue
                .split(',')
                .map(s => s.trim())
                .filter(s => s !== '')
            : [statusValue];

        if (statusArray.length > 0) {
          newConditions.push({
            key: 'status',
            value: statusArray,
          });
        }
      }

      // 更新搜索条件和过滤条件
      searchKey.value = newSearchKey;
      conditions.value = newConditions;

      // 重新获取表格数据
      pagination.value.current = 1;
      getTableList();
    };

    const handleSearchChange = (val: SearchKeyItem[]) => {
      // 更新搜索条件
      searchKey.value = val;

      // 获取已选择的字段 id 列表
      const selectedIds = val.map(item => item.id);

      // 从完整的搜索字段数据中过滤掉已存在的值，动态更新 searchFilterData
      searchFilterData.value = allSearchFilterData.filter(item => !selectedIds.includes(item.id));

      // 将搜索值转换成条件格式 [{"key": "name", "value": ["111"]}, ...]
      const searchConditions: Array<{ key: string; value: any[] }> = val
        .filter(item => item.values && item.values.length > 0)
        .map(item => {
          // 提取 values 中的 id 或 name，组成数组
          const values = item.values
            .map((v: any) => {
              // 如果值是对象，优先取 id，其次取 name；否则直接使用值
              if (typeof v === 'object' && v !== null) {
                return v.id || v.name || v;
              }
              return v;
            })
            .filter((v: any) => v !== null && v !== undefined && v !== '');

          // 字段映射：scenario_name 映射到 scenario_id
          let key = item.id;
          if (item.id === 'scenario_name') {
            key = 'scenario_id';
          }

          return {
            key,
            value: values,
          };
        });

      // 获取当前表格过滤器的条件（保留表格过滤条件）
      // 表格过滤器的 key 包括：scenario_id, collector_scenario_id, status
      const tableFilterKeys = ['scenario_id', 'collector_scenario_id', 'status'];
      const tableFilterConditions = conditions.value.filter(item => tableFilterKeys.includes(item.key));

      // 合并搜索条件和表格过滤条件
      // 如果搜索条件中有 scenario_id，需要与表格过滤器中的 scenario_id 合并
      const mergedConditions: Array<{ key: string; value: any[] }> = [];
      const allConditions = [...searchConditions, ...tableFilterConditions];

      // 合并相同 key 的条件
      allConditions.forEach(condition => {
        const existingIndex = mergedConditions.findIndex(item => item.key === condition.key);
        if (existingIndex >= 0) {
          // 如果已存在相同的 key，合并 value 并去重
          const existingValues = mergedConditions[existingIndex].value;
          const newValues = condition.value;
          const combinedValues = [...new Set([...existingValues, ...newValues])];
          mergedConditions[existingIndex] = {
            key: condition.key,
            value: combinedValues,
          };
        } else {
          // 如果不存在，直接添加
          mergedConditions.push(condition);
        }
      });

      // 更新 conditions
      conditions.value = mergedConditions;

      // 重新获取表格数据
      pagination.value.current = 1;
      getTableList();
    };

    const sortChange = (sortInfo: { descending?: boolean; sortBy?: string }): void => {
      sortConfig.value = sortInfo;
      handleSort(sortInfo);
    };

    /**
     * 将日期字符串转换为时间戳
     * @param dateStr 日期字符串，格式如 "2025-11-21 03:43:19+0800"
     * @returns 时间戳，如果转换失败返回 0
     */
    const parseDateToTimestamp = (dateStr: string | undefined | null): number => {
      if (!dateStr) return 0;
      try {
        // 处理格式 "2025-11-21 03:43:19+0800"
        const date = new Date(dateStr);
        return isNaN(date.getTime()) ? 0 : date.getTime();
      } catch {
        return 0;
      }
    };
    /**
     * 表格排序
     * @param sort
     */
    const handleSort = (sort: { descending?: boolean; sortBy?: string }): void => {
      if (sort?.sortBy) {
        const { descending, sortBy } = sort;
        tableList.value = tableList.value.concat().sort((a, b) => {
          let aValue: any = a[sortBy];
          let bValue: any = b[sortBy];

          // 处理日期字段：转换为时间戳
          if (sortBy === 'created_at' || sortBy === 'updated_at') {
            aValue = parseDateToTimestamp(aValue);
            bValue = parseDateToTimestamp(bValue);
          }
          // 处理 name 字段：字符串比较
          else if (sortBy === 'name') {
            aValue = aValue || '';
            bValue = bValue || '';
            const comparison = aValue.localeCompare(bValue);
            return descending ? -comparison : comparison;
          }

          // 其他字段：数值比较
          const result = descending ? bValue - aValue : aValue - bValue;
          return result;
        });
      } else {
        // 取消排序，恢复原始顺序
        if (originalOrderMap.value.size > 0) {
          tableList.value = tableList.value.concat().sort((a, b) => {
            const aOrder = originalOrderMap.value.get(a.index_set_id) ?? 0;
            const bOrder = originalOrderMap.value.get(b.index_set_id) ?? 0;
            return aOrder - bOrder;
          });
        }
      }
    };

    // 列配置相关方法
    const handleOpenColumnConfig = () => {
      isShowColumnConfig.value = true;
      // 初始化临时选择为当前可见列，确保包含默认列
      const allCurrentColumns = [
        ...defaultVisibleColumns.value,
        ...visibleColumns.value.filter(key => !defaultVisibleColumns.value.includes(key)),
      ];
      tempVisibleColumns.value = [...allCurrentColumns];
    };

    const handleCloseColumnConfig = () => {
      // 手动关闭 tippy（用于取消按钮点击）
      if (columnConfigTippyInstance) {
        columnConfigTippyInstance.hide();
      }
      isShowColumnConfig.value = false;
    };

    const handleColumnConfigChange = (fieldId: string, checked: boolean) => {
      const colKey = fieldIdToColKeyMap[fieldId] || fieldId;
      // 如果是默认列，不允许取消
      if (!checked && defaultVisibleColumns.value.includes(colKey)) {
        return;
      }

      if (checked) {
        if (!tempVisibleColumns.value.includes(colKey)) {
          tempVisibleColumns.value.push(colKey);
        }
      } else {
        tempVisibleColumns.value = tempVisibleColumns.value.filter(key => key !== colKey);
      }
    };

    const handleColumnConfigConfirm = () => {
      // 确保默认列始终包含在内
      const finalColumns = [
        ...defaultVisibleColumns.value,
        ...tempVisibleColumns.value.filter(key => !defaultVisibleColumns.value.includes(key)),
      ];
      visibleColumns.value = finalColumns;
      isShowColumnConfig.value = false;
      columnConfigTippyInstance?.hide();
    };

    const isColumnChecked = (fieldId: string): boolean => {
      const colKey = fieldIdToColKeyMap[fieldId] || fieldId;
      return tempVisibleColumns.value.includes(colKey);
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
          <bk-search-select
            class='tool-search-select'
            data={searchFilterData.value}
            placeholder={t('搜索 采集名、存储名、集群名、创建人、更新人')}
            value={searchKey.value}
            on-change={handleSearchChange}
          />
        </div>
        <div
          ref={tableMainRef}
          class='v2-log-collection-table-main'
        >
          <div class='table-set'>
            <div
              ref={columnConfigTriggerRef}
              class='column-config-trigger'
            >
              <i class='bk-icon icon-cog-shape'></i>
            </div>
            <div
              ref={columnConfigContentRef}
              class='column-config-dropdown'
            >
              <div class='column-config-title'>{t('字段显示设置')}</div>
              <div class='column-config-list'>
                {columnConfigFields.value.map(field => {
                  const colKey = fieldIdToColKeyMap[field.id] || field.id;
                  const isDefault = field.disabled || defaultVisibleColumns.value.includes(colKey);
                  const checked = isColumnChecked(field.id);
                  return (
                    <span
                      key={field.id}
                      class='column-config-item'
                    >
                      <bk-checkbox
                        value={checked}
                        disabled={isDefault}
                        on-change={(val: boolean) => {
                          if (!isDefault) {
                            handleColumnConfigChange(field.id, val);
                          }
                        }}
                      >
                        {field.label}
                      </bk-checkbox>
                    </span>
                  );
                })}
              </div>
              <div class='column-config-footer'>
                <bk-button
                  theme='primary'
                  size='small'
                  on-click={handleColumnConfigConfirm}
                >
                  {t('确定')}
                </bk-button>
                <bk-button
                  size='small'
                  on-click={handleCloseColumnConfig}
                >
                  {t('取消')}
                </bk-button>
              </div>
            </div>
          </div>
          <TConfigProvider
            class='log-collection-table'
            globalConfig={globalLocale}
          >
            {/* @ts-ignore - TTable type definition issue */}
            <TTable
              cache={true}
              cellEmptyContent={'--'}
              columns={columns.value}
              data={tableList.value}
              sort={sortConfig.value}
              loading={listLoading.value}
              loading-props={{ indicator: false }}
              on-page-change={handlePageChange}
              pagination={pagination.value}
              row-key='key'
              height={maxTableHeight.value}
              rowHeight={32}
              scroll={{ type: 'lazy', bufferSize: 10 }}
              virtual={true}
              on-sort-change={sortChange}
              on-filter-change={handleFilterChange}
              scopedSlots={{
                loading: () => (
                  <div class='table-skeleton-box'>
                    <ItemSkeleton
                      style={{ padding: '0 16px' }}
                      columns={5}
                      gap={'14px'}
                      rowHeight={'28px'}
                      rows={6}
                      widths={['25%', '25%', '20%', '20%', '10%']}
                    />
                  </div>
                ),
              }}
            />
          </TConfigProvider>
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
            // status={currentStatus.value.status}
            on-change={value => {
              showCollectIssuedSlider.value = value;
            }}
          />
        </div>
      </div>
    );
  },
});
