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
import { useRouter, useRoute } from 'vue-router/composables';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import * as authorityMap from '@/common/authority-map';
import tippy, { type Instance } from 'tippy.js';
import { tenantManager, UserInfoLoadedEventData } from '@/views/retrieve-core/tenant-manager';
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
  IS_RELATED_SPACE_ENUM,
  LOG_TYPE_ICON_MAP,
} from '../../../utils';
import { copyMessage, projectManages } from '@/common/util';
import useResizeObserver from '@/hooks/use-resize-observe';
import CollectIssuedSlider from '../../business-comp/step3/collect-issued-slider';
import $http from '@/api';
import { useCollectList } from '../../../hook/useCollectList';
import { useTableLocalSetting } from '../../../hook/use-table-local-setting';
import TagMore from '../../common-comp/tag-more';
import type { IListItemData } from '../../../type';
import StopTypeDialog from '../stop-type-dialog';
import AddExistingCollectDialog from '../add-existing-collect-dialog';
import TableComponent from '../../common-comp/table-component';
import ClusterFilter from '@/views/retrieve-v2/search-result-panel/log-clustering/components/finger-tools/cluster-filter.tsx';
import '@/views/retrieve-v2/search-result-panel/log-clustering/components/finger-tools/cluster-filter.scss';
import BklogPopover from '@/components/bklog-popover';
import './new.scss';

const CancelToken = axios.CancelToken;
const TABLE_STYLE_UPDATE_ALERT_STORAGE_KEY = 'BKLOG_COLLECTION_TABLE_STYLE_UPDATE_ALERT_CLOSED';

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
  storage_display_name?: string;
  daily_usage?: number;
  total_usage?: number;
  bk_data_name?: string;
  table_id?: number | string;
  bk_data_id?: number | string;
  parent_index_sets?: Array<{ index_set_id?: number | string; index_set_name: string;[key: string]: unknown }>;
  parent_index_set_ids?: Array<number | string>;
  scenario_id?: string;
  scenario_name?: string;
  collector_scenario_id?: string;
  collector_scenario_name?: string;
  retention?: number;
  tags?: Array<{ name: string;[key: string]: unknown }>;
  created_by?: string;
  created_at?: string;
  updated_by?: string;
  updated_at?: string;
  environment?: string;
  [key: string]: unknown;
  log_access_type?: string;
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
  value: (string | number)[] | number | string;
}

/**
 * 过滤值类型
 */
interface IFilterValues {
  created_by: Array<{ label: string; value: string; key?: string }>;
  updated_by: Array<{ label: string; value: string; key?: string }>;
  storage_display_name: Array<{ label: string; value: string; key?: string }>;
}

interface IEnumItem {
  key: number | string;
  value: number | string;
}

interface ISearchSelectValue {
  id: string;
  name: string;
  values?: Array<{ id: number | string; name: string }>;
}

interface ICollectorSearchEnums {
  name: IEnumItem[];
  table_id: IEnumItem[];
  bk_data_id: IEnumItem[];
  storage_display_name: IEnumItem[];
  bk_data_name: IEnumItem[];
}

interface ICollectorFieldEnumsResponse extends ICollectorSearchEnums {
  created_by: Array<{ key: string; value: string }>;
  updated_by: Array<{ key: string; value: string }>;
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

interface IBklogPopoverInstance {
  show: (_target?: HTMLElement) => void;
  hide: (_delay?: number) => void;
}

type SortDirection = 'asc' | 'desc';
type SortField = 'name' | 'daily_usage' | 'total_usage' | 'retention' | 'updated_at' | 'created_at';
type CollectorOrdering = SortField | `-${SortField}`;

const ORDERING_MAP: Record<SortField, Record<SortDirection, CollectorOrdering>> = {
  name: { asc: 'name', desc: '-name' },
  daily_usage: { asc: 'daily_usage', desc: '-daily_usage' },
  total_usage: { asc: 'total_usage', desc: '-total_usage' },
  retention: { asc: 'retention', desc: '-retention' },
  updated_at: { asc: 'updated_at', desc: '-updated_at' },
  created_at: { asc: 'created_at', desc: '-created_at' },
};

const getOrdering = (sortInfo: ISortConfig): CollectorOrdering => {
  const sortField = sortInfo.sortBy as SortField;
  const direction: SortDirection = sortInfo.descending ? 'desc' : 'asc';
  return ORDERING_MAP[sortField]?.[direction] || '-updated_at';
};

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
  table_id: 'table_id',
  bk_data_name: 'bk_data_name',
  index_set_id: 'index_set_name',
  log_access_type: 'log_access_type',
  collector_scenario_id: 'collector_scenario_id',
  storage_display_name: 'storage_display_name',
  label: 'tags',
  es_host_state: 'status',
  updated_by: 'updated_by',
} as const;

/**
 * 列键到字段ID的映射（FIELD_ID_TO_COL_KEY_MAP 的反向映射，用于字段设置持久化）
 */
const COL_KEY_TO_FIELD_ID_MAP: Record<string, string> = Object.entries(FIELD_ID_TO_COL_KEY_MAP).reduce<
  Record<string, string>
>((acc, [fieldId, colKey]) => {
  acc[colKey] = fieldId;
  return acc;
}, {});

export default defineComponent({
  name: 'TableListNew',
  props: {
    indexSet: {
      type: Object as PropType<IListItemData>,
      default: () => ({}),
    },
    leftLoading: {
      type: Boolean,
      default: false,
    },
    indexGroupList: {
      type: Array as PropType<IListItemData[]>,
      default: () => [],
    },
  },

  emits: ['refresh-index-group'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const router = useRouter();
    const route = useRoute();
    const showTableStyleUpdateAlert = ref(
      localStorage.getItem(TABLE_STYLE_UPDATE_ALERT_STORAGE_KEY) !== 'true',
    );
    const showStopTypeDialog = ref(false);
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
    const { authGlobalInfo, operateHandler, checkCreateAuth, spaceUid, bkBizId, isAllowedCreate } = useCollectList();
    // 个人设置本地存储（归属、排序、字段设置、列宽、页大小）
    const { getSetting, updateSetting } = useTableLocalSetting();
    // 初始化时读取一次缓存，各设置项在使用前逐项校验合法性
    const cachedTableSetting = getSetting();
    /** 归属个人设置（持久值）：仅在非「全部」索引集视图下生效，切到「全部」时保留存储值 */
    const sourceSetting = ref<string>(
      IS_RELATED_SPACE_ENUM.some(item => item.value === cachedTableSetting?.source)
        ? (cachedTableSetting?.source as string)
        : '',
    );
    /** 字段设置个人设置：用户勾选的字段 id 列表（无缓存时默认全选） */
    const cachedSelectedFields = Array.isArray(cachedTableSetting?.selectedFields)
      ? cachedTableSetting.selectedFields.filter(id => SETTING_FIELDS.some(field => field.id === id))
      : null;
    const selectedFieldIds = ref<string[]>(
      cachedSelectedFields ?? SETTING_FIELDS.map(field => field.id),
    );
    /** 列宽个人设置 { [colKey]: number } */
    const columnsWidthSetting = ref<Record<string, number>>(
      (() => {
        const cached = cachedTableSetting?.columnsWidth;
        if (!cached || typeof cached !== 'object') {
          return {};
        }
        return Object.entries(cached).reduce<Record<string, number>>((acc, [colKey, width]) => {
          const numWidth = Number(width);
          if (colKey && Number.isFinite(numWidth) && numWidth > 0) {
            acc[colKey] = Math.round(numWidth);
          }
          return acc;
        }, {});
      })(),
    );
    /** 获取当前索引集视图下生效的归属筛选值（「全部」视图不生效） */
    const getEffectiveSource = () => {
      return (props.indexSet as IListItemData)?.index_set_id !== 'all' ? sourceSetting.value : '';
    };
    const tableList = ref<ITableRowData[]>([]);
    const listLoading = ref(false);
    const isLoading = computed(() => listLoading.value);

    const handleCopy = (value: number | string | undefined, successMessage: string) => {
      if (value === undefined || value === null || value === '') {
        return;
      }
      copyMessage(String(value), successMessage);
    };

    // 用户信息映射（username -> display_name）
    const userDisplayNameMap = ref<Map<string, string>>(new Map());

    /** 监听用户信息更新事件，更新显示名称映射 */
    const handleUserInfoUpdated = (data: UserInfoLoadedEventData) => {
      const newMap = new Map(userDisplayNameMap.value);
      let hasUpdate = false;
      for (const [bkUsername, userInfo] of data.userInfo.entries()) {
        if (userInfo?.display_name && newMap.get(bkUsername) !== userInfo.display_name) {
          newMap.set(bkUsername, userInfo.display_name);
          hasUpdate = true;
        }
      }
      if (hasUpdate) {
        userDisplayNameMap.value = newMap;

        // 同步更新过滤下拉项的 label（created_by / updated_by）
        type FilterItem = IFilterValues['created_by'][number];
        const updateFilterItems = (items: FilterItem[] | undefined): FilterItem[] | undefined => {
          if (!items || items.length === 0) return items;
          let changed = false;
          const next = items.map(item => {
            const displayName = newMap.get(item.key || '');
            if (displayName && displayName !== item.label) {
              changed = true;
              return { ...item, label: displayName };
            }
            return item;
          });
          return changed ? next : items;
        };

        const createdBy = updateFilterItems(IFilterValues.value.created_by);
        const updatedBy = updateFilterItems(IFilterValues.value.updated_by);
        if (createdBy !== IFilterValues.value.created_by || updatedBy !== IFilterValues.value.updated_by) {
          IFilterValues.value = {
            ...IFilterValues.value,
            created_by: createdBy,
            updated_by: updatedBy,
          };
        }
      }
    };
    // 全量标签列表（用于标签管理）
    const selectLabelList = ref<Array<{ tag_id: number; name: string; color: string; is_built_in?: boolean }>>([]);
    // 标签过滤下拉选项列表
    const filterLabelList = ref<Array<{ id: number; name: string }>>([]);
    // 标签过滤当前选中项
    const tagSelect = ref<(string | number)[]>(['all']);
    const editingIndexSetRowId = ref<number | string>('');
    const updatingIndexSetRowId = ref<number | string>('');
    const editingIndexSetDraftIds = ref<Record<string, Array<number | string>>>({});
    const localParentIndexSetMap = ref<Record<string, {
      ids: Array<number | string>;
      sets: ITableRowData['parent_index_sets'];
    }>>({});
    const indexSetSelectRef = ref<{ close?:() => void } | null>(null);
    const pendingIndexSetSubmitRowId = ref<number | string>('');
    const editingIndexSetRowMap = new Map<string, ITableRowData>();

    // 容器和表格高度相关
    const containerRef = ref<HTMLElement | null>(null);
    const tableMainRef = ref<HTMLElement | null>(null);
    const maxTableHeight = ref<number>(0);

    let tippyInstances: Instance[] = [];
    let collectStatusTimer: ReturnType<typeof setTimeout> | null = null;
    let isUnmounted = false;
    const IFilterValues = ref<IFilterValues>({
      created_by: [],
      updated_by: [],
      storage_display_name: [],
    });
    const searchSelectValues = ref<ISearchSelectValue[]>([]);
    const collectorSearchEnums = ref<ICollectorSearchEnums>({
      name: [],
      table_id: [],
      bk_data_id: [],
      storage_display_name: [],
      bk_data_name: [],
    });
    const searchFieldOptions = [
      { id: 'name', name: t('采集名') },
      { id: 'table_id', name: t('数据名') },
      { id: 'bk_data_id', name: t('数据ID') },
      { id: 'storage_display_name', name: t('存储集群') },
      { id: 'bk_data_name', name: t('存储名') },
    ] as const;
    const searchSelectData = computed(() => {
      return searchFieldOptions.map(field => ({
        ...field,
        multiable: true,
        children: collectorSearchEnums.value[field.id].map(item => ({
          id: item.key,
          name: String(item.value),
        })),
      }));
    });
    // 过滤条件（归属属于个人设置，初始化时恢复生效值对应的条件）
    const conditions = ref<IFilterCondition[]>(
      getEffectiveSource() ? [{ key: 'collector_source', value: [getEffectiveSource()] }] : [],
    );
    // 表格过滤值（用于设置默认选中状态）
    const filterValue = ref<Record<string, string |(string | number)[]>>({
      log_access_type: '',
      collector_scenario_id: '',
      storage_display_name: '',
      status: '',
      created_by: '',
      updated_by: '',
      tags: [],
      is_related_space: getEffectiveSource(),
    });

    const PAGE_SIZE_OPTIONS = [10, 20, 50];
    const pagination = ref({
      current: 1,
      total: 0,
      // 页大小个人设置，校验是否属于可选项后恢复
      pageSize: PAGE_SIZE_OPTIONS.includes(Number(cachedTableSetting?.pageSize))
        ? Number(cachedTableSetting?.pageSize)
        : 10,
      limitList: PAGE_SIZE_OPTIONS,
    });

    // 排序个人设置，校验排序字段合法性后恢复
    const sortConfig = ref<ISortConfig>(
      cachedTableSetting?.sortBy && Object.keys(ORDERING_MAP).includes(cachedTableSetting.sortBy)
        ? { sortBy: cachedTableSetting.sortBy, descending: cachedTableSetting.descending !== false }
        : { sortBy: 'updated_at', descending: true },
    );
    const usageSortPopoverRef = ref<IBklogPopoverInstance | null>(null);
    const pendingUsageSortInfo = ref<ISortConfig | null>(null);
    const sortFieldDraft = ref(sortConfig.value.sortBy || 'name');
    let isSyncingSortFieldDraft = false;
    const sortFieldOptions = [
      { id: 'name', name: t('采集名'), defaultDirection: 'asc' },
      { id: 'daily_usage', name: t('日用量'), defaultDirection: 'desc' },
      { id: 'total_usage', name: t('总用量'), defaultDirection: 'desc' },
      { id: 'retention', name: t('过期时间'), defaultDirection: 'desc' },
      { id: 'updated_at', name: t('更新时间'), defaultDirection: 'desc' },
      { id: 'created_at', name: t('创建时间'), defaultDirection: 'desc' },
    ];
    const sortDirectionOptions = computed(() => {
      const sortBy = sortConfig.value.sortBy || 'name';
      if (['daily_usage', 'total_usage', 'retention'].includes(sortBy)) {
        return [
          { id: 'desc', name: t('大-小') },
          { id: 'asc', name: t('小-大') },
        ];
      }
      if (['updated_at', 'created_at'].includes(sortBy)) {
        return [
          { id: 'desc', name: t('新-旧') },
          { id: 'asc', name: t('旧-新') },
        ];
      }
      return [
        { id: 'asc', name: '[A-Z][0-9][a-z]' },
        { id: 'desc', name: '[Z-A][9-0][z-a]' },
      ];
    });
    const sourceFilterOptions = [
      { label: t('全部'), value: '', className: '' },
      { label: IS_RELATED_SPACE_ENUM[0].label, value: IS_RELATED_SPACE_ENUM[0].value, className: 'current' },
      { label: IS_RELATED_SPACE_ENUM[1].label, value: IS_RELATED_SPACE_ENUM[1].value, className: 'related' },
    ];
    const stopTypeKey = ref(true);
    /** 当前操作行是否为自定义上报类型 */
    const isCustomReport = computed(() => currentRow.value?.log_access_type === 'custom_report');
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
     * 根据表格主区域的实际可用高度计算内容区最大高度。
     * TTable 的 maxHeight 只作用于内容区，因此需要扣除组件外置分页器的实际高度。
     */
    const calculateMaxTableHeight = () => {
      nextTick(() => {
        const tableMain = tableMainRef.value;
        const tableMainHeight = tableMain?.clientHeight || tableMain?.offsetHeight || 0;

        if (tableMainHeight > 0) {
          const paginationHeight = tableMain?.querySelector<HTMLElement>('.t-table__pagination')?.offsetHeight || 0;
          maxTableHeight.value = Math.max(0, tableMainHeight - paginationHeight);
          return;
        }

        maxTableHeight.value = calculateHeightByWindow();
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
      // status 是异步获取的，可能暂时为空，默认按非 terminated 状态处理
      const status = row?.status || '';

      if (!type) {
        return MENU_LIST.filter(item => item.key !== (status !== 'terminated' ? 'start' : 'stop'));
      }

      if (type === 'custom_report') {
        const excludeKey = status !== 'terminated' ? 'start' : 'stop';
        return MENU_LIST.filter(
          item => ['clean', 'desensitization', 'stop', 'start', 'delete'].includes(item.key) && item.key !== excludeKey,
        );
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

    const getRowUniqueId = (row: ITableRowData) => (
      row.collector_config_id || row.index_set_id || row.bk_data_id || row.name
    );

    const getLocalParentIndexSet = (row: ITableRowData) => {
      return localParentIndexSetMap.value[String(getRowUniqueId(row))];
    };

    const getRowParentIndexSets = (row: ITableRowData) => {
      return getLocalParentIndexSet(row)?.sets || row.parent_index_sets || [];
    };

    const getRowParentIndexSetIds = (row: ITableRowData) => {
      const localParentIndexSet = getLocalParentIndexSet(row);
      if (localParentIndexSet) {
        return localParentIndexSet.ids;
      }

      if (Array.isArray(row.parent_index_set_ids)) {
        return row.parent_index_set_ids;
      }
      return (row.parent_index_sets || [])
        .map(item => item.index_set_id)
        .filter(id => id !== undefined && id !== null) as Array<number | string>;
    };

    const buildParentIndexSets = (ids: Array<number | string>) => {
      const indexSetMap = new Map((props.indexGroupList || []).map(item => [String(item.index_set_id), item]));
      return ids.map((id) => {
        const matched = indexSetMap.get(String(id));
        return {
          index_set_id: id,
          index_set_name: matched?.index_set_name || String(id),
        };
      });
    };

    const getRowEditAuthKey = (row: ITableRowData) => {
      const isBkDataOrEs = ['bkdata', 'es'].includes(row.log_access_type);
      return isBkDataOrEs ? authorityMap.MANAGE_INDICES_AUTH : authorityMap.MANAGE_COLLECTION_AUTH;
    };

    const isRowIndexSetEditable = (row: ITableRowData) => {
      return getOperatorCanClick(row, 'edit');
    };

    const updateParentIndexSetLocal = (row: ITableRowData, ids: Array<number | string>) => {
      const rowId = getRowUniqueId(row);
      const parentIndexSets = buildParentIndexSets(ids);
      row.parent_index_set_ids = ids;
      row.parent_index_sets = parentIndexSets;
      localParentIndexSetMap.value = {
        ...localParentIndexSetMap.value,
        [String(rowId)]: {
          ids,
          sets: parentIndexSets,
        },
      };

      tableList.value = tableList.value.map((item) => {
        if (getRowUniqueId(item) !== rowId) {
          return item;
        }

        return {
          ...item,
          parent_index_set_ids: ids,
          parent_index_sets: parentIndexSets,
        };
      });

      if (getRowUniqueId(currentRow.value) === rowId) {
        currentRow.value = {
          ...currentRow.value,
          parent_index_set_ids: ids,
          parent_index_sets: parentIndexSets,
        };
      }
    };

    const normalizeIndexSetIds = (ids: Array<number | string>) => {
      return ids.map(id => Number(id)).filter(id => Number.isInteger(id));
    };

    const getDiffIndexSetIds = (sourceIds: number[], targetIds: number[]) => {
      const sourceSet = new Set(sourceIds);
      const targetSet = new Set(targetIds);
      return {
        addIds: targetIds.filter(id => !sourceSet.has(id)),
        removeIds: sourceIds.filter(id => !targetSet.has(id)),
      };
    };

    const requestUpdateParentIndexSet = async (
      row: ITableRowData,
      oldIds: Array<number | string>,
      ids: Array<number | string>,
    ) => {
      const childIndexSetId = Number(row.index_set_id);
      if (!Number.isInteger(childIndexSetId)) {
        return { result: false };
      }

      const normalizedOldIds = normalizeIndexSetIds(oldIds);
      const normalizedIds = normalizeIndexSetIds(ids);
      const { addIds, removeIds } = getDiffIndexSetIds(normalizedOldIds, normalizedIds);
      const requestList = [
        ...addIds.map(indexSetId => $http.request('collect/addIndexSetsToGroup', {
          params: {
            index_set_id: indexSetId,
          },
          data: {
            child_index_set_ids: [childIndexSetId],
          },
        })),
        ...removeIds.map(indexSetId => $http.request('collect/removeIndexSetsFromGroup', {
          params: {
            index_set_id: indexSetId,
          },
          data: {
            child_index_set_ids: [childIndexSetId],
          },
        })),
      ];

      if (!requestList.length) {
        return { result: true };
      }

      const results = await Promise.all(requestList);
      return { result: results.every(item => item?.result) };
    };

    const setEditingIndexSetDraftIds = (rowId: number | string, ids: Array<number | string>) => {
      editingIndexSetDraftIds.value = {
        ...editingIndexSetDraftIds.value,
        [String(rowId)]: ids,
      };
    };

    const clearEditingIndexSetDraftIds = (rowId: number | string) => {
      const nextDraftIds = { ...editingIndexSetDraftIds.value };
      delete nextDraftIds[String(rowId)];
      editingIndexSetDraftIds.value = nextDraftIds;
    };

    const isSameIndexSetIds = (sourceIds: Array<number | string>, targetIds: Array<number | string>) => {
      return sourceIds.map(String).sort()
        .join(',') === targetIds.map(String).sort()
        .join(',');
    };

    const handleParentIndexSetSubmit = async (row: ITableRowData) => {
      const rowId = getRowUniqueId(row);
      editingIndexSetRowMap.delete(String(rowId));
      pendingIndexSetSubmitRowId.value = '';
      if (updatingIndexSetRowId.value === rowId) {
        return;
      }

      const oldIds = getRowParentIndexSetIds(row);
      const ids = editingIndexSetDraftIds.value[String(rowId)] || oldIds;
      if (isSameIndexSetIds(oldIds, ids)) {
        clearEditingIndexSetDraftIds(rowId);
        if (editingIndexSetRowId.value === rowId) {
          editingIndexSetRowId.value = '';
        }
        return;
      }

      updatingIndexSetRowId.value = rowId;
      updateParentIndexSetLocal(row, ids);
      await nextTick();

      let shouldExitEdit = false;
      try {
        const res = await requestUpdateParentIndexSet(row, oldIds, ids);
        if (res?.result) {
          showMessage(t('更新成功'));
          shouldExitEdit = true;
          emit('refresh-index-group');
        } else {
          updateParentIndexSetLocal(row, oldIds);
          showMessage(t('更新失败'), 'error');
        }
      } catch (error) {
        updateParentIndexSetLocal(row, oldIds);
        showMessage(t('更新失败'), 'error');
        console.log('更新所属索引集失败:', error);
      } finally {
        updatingIndexSetRowId.value = '';
        clearEditingIndexSetDraftIds(rowId);
        if (shouldExitEdit && editingIndexSetRowId.value === rowId) {
          await nextTick();
          editingIndexSetRowId.value = '';
        }
      }
    };

    const isIndexSetSelectElement = (target: HTMLElement) => {
      return !!target.closest(
        [
          '.index-set-inline-select-wrap',
          '.bk-select-dropdown',
          '.bk-select-popover',
          '.bk-select-extension',
          '.bk-option',
          '.bk-options',
          '.bk-popover',
          '.bk-pop2-content',
          '.tippy-box',
        ].join(','),
      );
    };

    const waitIndexSetSelectPopoverClosed = () => {
      return new Promise((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            window.setTimeout(resolve, 80);
          });
        });
      });
    };

    const submitParentIndexSetAfterSelectClose = async (row: ITableRowData) => {
      const rowId = getRowUniqueId(row);
      if (updatingIndexSetRowId.value === rowId || pendingIndexSetSubmitRowId.value === rowId) {
        return;
      }

      pendingIndexSetSubmitRowId.value = rowId;
      indexSetSelectRef.value?.close?.();
      await waitIndexSetSelectPopoverClosed();

      if (editingIndexSetRowId.value !== rowId) {
        pendingIndexSetSubmitRowId.value = '';
        return;
      }

      await handleParentIndexSetSubmit(row);
    };

    const exitIndexSetEdit = () => {
      const rowId = editingIndexSetRowId.value;
      if (!rowId || updatingIndexSetRowId.value === rowId || pendingIndexSetSubmitRowId.value === rowId) {
        return;
      }

      const editingRow = editingIndexSetRowMap.get(String(rowId));
      if (!editingRow) {
        clearEditingIndexSetDraftIds(rowId);
        editingIndexSetRowId.value = '';
        return;
      }

      void submitParentIndexSetAfterSelectClose(editingRow);
    };

    const handleDocumentMouseDown = (event: MouseEvent) => {
      if (!editingIndexSetRowId.value) {
        return;
      }

      const target = event.target as HTMLElement | null;
      if (!target || isIndexSetSelectElement(target)) {
        return;
      }

      exitIndexSetEdit();
    };

    const renderParentIndexSetCell = (row: ITableRowData) => {
      const rowId = getRowUniqueId(row);
      const selectedIds = getRowParentIndexSetIds(row);
      const draftSelectedIds = editingIndexSetDraftIds.value[String(rowId)] || selectedIds;
      const parentIndexSets = getRowParentIndexSets(row);
      const indexSetName = parentIndexSets.map(item => ({
        ...item,
        name: item.index_set_name,
      }));
      const isEditing = editingIndexSetRowId.value === rowId;
      const isUpdating = updatingIndexSetRowId.value === rowId;
      const canEdit = isRowIndexSetEditable(row);

      if (isEditing) {
        return (
          <div
            class='index-set-inline-select-wrap'
            v-bkloading={{ isLoading: isUpdating, size: 'mini' }}
          >
            <bk-select
              ref={indexSetSelectRef}
              class='index-set-inline-select'
              disabled={isUpdating}
              display-tag
              loading={isUpdating}
              multiple
              searchable
              value={draftSelectedIds}
              auto-height={false}
              onChange={(val: Array<number | string>) => {
                setEditingIndexSetDraftIds(rowId, val || []);
              }}
              onToggle={(isOpen: boolean) => {
                if (!isOpen) {
                  void submitParentIndexSetAfterSelectClose(row);
                }
              }}
            >
              {(props.indexGroupList || []).map((option: IListItemData) => (
                <bk-option
                  id={option.index_set_id}
                  key={option.index_set_id}
                  name={option.index_set_name}
                />
              ))}
            </bk-select>
          </div>
        );
      }

      return (
        <div class='index-set-inline-display'>
          <span class='index-set-inline-tags'>
            {parentIndexSets.length > 0 ? (
              <TagMore
                tags={indexSetName}
                title={t('所属索引集')}
              />
            ) : (
              '--'
            )}
          </span>
          {canEdit && (
            <span
              class='bk-icon icon-edit-line index-set-inline-edit'
              v-cursor={{ active: !row.permission?.[getRowEditAuthKey(row)] }}
              on-click={() => {
                if (!row.permission?.[getRowEditAuthKey(row)]) {
                  handleEditOperation(row, 'edit');
                  return;
                }
                setEditingIndexSetDraftIds(rowId, getRowParentIndexSetIds(row));
                editingIndexSetRowMap.set(String(rowId), row);
                editingIndexSetRowId.value = rowId;
              }}
            />
          )}
        </div>
      );
    };

    const settingFields = computed(() => {
      const indexSetId = (props.indexSet as IListItemData)?.index_set_id;
      return indexSetId === 'all'
        ? SETTING_FIELDS.filter(field => field.id !== 'is_related_space')
        : SETTING_FIELDS;
    });

    /** 传给表格组件的受控可见列 colKey 列表：按当前视图可用字段过滤（「全部」视图无采集项来源列） */
    const visibleColKeys = computed(() => {
      const availableIds = new Set(settingFields.value.map(field => field.id));
      return selectedFieldIds.value
        .filter(id => availableIds.has(id))
        .map(id => FIELD_ID_TO_COL_KEY_MAP[id] || id);
    });

    // 所有列定义
    const allColumns = computed(() => {
      const indexSetId = (props.indexSet as IListItemData)?.index_set_id;
      const showSpaceSource = indexSetId !== 'all';
      const columns = [
        {
          title: t('采集名 / 数据名'),
          colKey: 'name',
          width: 310,
          ellipsis: true,
          cell: (h, { row }: { row: ITableRowData }) => {
            const logTypeIcon = LOG_TYPE_ICON_MAP[row.log_access_type || ''] || '';
            return (
              <div class='collection-name-cell'>
                {showSpaceSource && (
                  <span class={['space-source-bar', row.is_related_space ? 'related' : 'current']} />
                )}
                <span class='collection-type-icon'>
                  {logTypeIcon && <i class={logTypeIcon} />}
                </span>
                <span class='collection-name-content'>
                  <span
                    class='link collection-name-link'
                    on-click={() => {
                      const isBkDataOrEs = ['bkdata', 'es'].includes(row.log_access_type);
                      const type = isBkDataOrEs || row.storage_cluster_id !== -1 ? 'view' : 'edit';
                      handleEditOperation(row, type);
                    }}
                  >
                    {row.storage_cluster_id === -1 && <span class='link-tag'>{t('未完成')}</span>}
                    {row.name || '--'}
                  </span>
                  <span class='collection-data-name'>
                    {row.bk_data_id !== undefined && row.bk_data_id !== null && row.bk_data_id !== '' && (
                      <span
                        class='collection-data-id copyable-text'
                        on-click={() => handleCopy(row.bk_data_id, t('复制 {0} 成功', [t('数据ID')]))}
                      >
                        [{row.bk_data_id}]
                      </span>
                    )}
                    {row.table_id && (
                      <span
                        class='collection-data-name-text copyable-text'
                        on-click={() => handleCopy(row.table_id, t('复制 {0} 成功', [t('数据名')]))}
                      >
                        {row.table_id}
                      </span>
                    )}
                  </span>
                </span>
              </div>
            );
          },
        },
        {
          title: t('日用量 / 总用量'),
          colKey: 'daily_usage',
          width: 150,
          cell: (h, { row }: { row: ITableRowData }) => (
            <span class='storage-usage-cell'>
              {formatBytes(row.daily_usage)} / {formatBytes(row.total_usage)}
            </span>
          ),
        },
        {
          title: t('存储集群 / 过期时间'),
          colKey: 'storage_display_name',
          minWidth: 180,
          ellipsis: true,
          ellipsisTitle: false,
          filter: getColumnsFilter(IFilterValues.value.storage_display_name),
          cell: (h, { row }: { row: ITableRowData }) => {
            const retentionText = row.retention ? `${row.retention} ${t('天')}` : '';
            return (
              <div class='double-line-cell'>
                <span class='storage-meta-line'>
                  <i class='bklog-icon bklog-jiqun-2 storage-meta-icon' />
                  {row.storage_display_name ? (
                    <span
                      class='copyable-text storage-meta-text'
                      on-click={() => handleCopy(row.storage_display_name, t('复制 {0} 成功', [t('存储集群')]))}
                    >
                      {row.storage_display_name}
                    </span>
                  ) : (
                    <span class='storage-meta-text'>--</span>
                  )}
                </span>
                <span class={{ 'storage-meta-line': true, 'text-disabled': row.status === 'stop' }}>
                  <i class='bklog-icon bklog-shijian storage-meta-icon' />
                  {retentionText ? (
                    <span
                      class='copyable-text storage-meta-text'
                      on-click={() => handleCopy(retentionText, t('复制 {0} 成功', [t('过期时间')]))}
                    >
                      {retentionText}
                    </span>
                  ) : (
                    <span class='storage-meta-text'>--</span>
                  )}
                </span>
              </div>
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
          title: (_h) => {
            const isActive = filterValue.value.tags.length > 0;
            return (
            <ClusterFilter
              title={t('标签')}
              searchable
              popoverMinWidth={200}
              select={tagSelect.value}
              selectList={filterLabelList.value}
              toggle={() => handleToggleTagSelect()}
              isActive={isActive}
              on-selected={(v: string[]) => handleTagSelectChange(v)}
              on-submit={(v: string[]) => handleTagSubmit(v)}
            />
            );
          },
          colKey: 'tags',
          showTips: false,
          cell: (h, { row }: { row: ITableRowData }) => (
          <TagMore
            mode='label'
            tags={row.tags || []}
            rowData={row}
            selectLabelList={selectLabelList.value}
            title={t('标签')}
            on-refresh-label-list={() => fetchLabelList()}
            on-update-tags={(newTags) => handleUpdateTags(row, newTags)}
          />
          ),
          width: 200,
        },
        {
          title: t('存储名'),
          colKey: 'bk_data_name',
          width: 180,
          ellipsis: true,
          cell: (h, { row }: { row: ITableRowData }) => {
            if (!row.bk_data_name) {
              return <span>--</span>;
            }
            return (
              <span
                class='copyable-text'
                on-click={() => handleCopy(row.bk_data_name, t('复制 {0} 成功', [t('存储名')]))}
              >
                {row.bk_data_name}
              </span>
            );
          },
        },
        {
          title: t('采集状态'),
          colKey: 'status',
          width: 100,
          cell: (h, { row }: { row: ITableRowData }) => renderStatus(row),
          filter: getColumnsFilter(STATUS_ENUM_FILTER),
        },
        {
          title: t('最近更新'),
          colKey: 'updated_by',
          width: 180,
          filter: getColumnsFilter(IFilterValues.value.updated_by),
          cell: (h, { row }: { row: ITableRowData }) => (
            <div class='double-line-cell'>
              <span>{getName(row.updated_by)}</span>
              <span>{row.updated_at || '--'}</span>
            </div>
          ),
        },
        {
          title: t('所属索引集'),
          colKey: 'index_set_name',
          className: 'index-set-name-cell',
          width: 240,
          cell: (h, { row }: { row: ITableRowData }) => renderParentIndexSetCell(row),
        },
        ...(showSpaceSource
          ? [
            {
              title: t('采集项来源'),
              colKey: 'is_related_space',
              width: 120,
              cell: (h, { row }: { row: ITableRowData }) => (
                <span class='space-tag-wrapper'>
                  {!row.is_related_space && <span class='space-tag current'>{t('当前空间')}</span>}
                  {row.is_related_space && (
                    <span
                      class='space-tag related'
                      v-bk-tooltips={{
                        content: t('关联空间') + (row?.space_name ? `: ${row?.space_name}` : ''),
                      }}
                    >
                      {t('关联空间')}
                    </span>
                  )}
                </span>
              ),
              filter: getColumnsFilter(IS_RELATED_SPACE_ENUM),
            },
          ]
          : []),
        {
          title: t('日志类型'),
          colKey: 'collector_scenario_id',
          width: 100,
          cell: (h, { row }: { row: ITableRowData }) => <span>{row.collector_scenario_name || '--'}</span>,
          filter: getColumnsFilter(COLLECTOR_SCENARIO_ENUM),
        },
        {
          title: t('创建'),
          colKey: 'created_by',
          width: 180,
          filter: getColumnsFilter(IFilterValues.value.created_by),
          cell: (h, { row }: { row: ITableRowData }) => (
            <div class='double-line-cell'>
              <span>{getName(row.created_by)}</span>
              <span>{row.created_at || '--'}</span>
            </div>
          ),
        },
        {
          title: t('操作'),
          colKey: 'operation',
          width: 110,
          fixed: 'right',
          cell: (h, { row }: { row: ITableRowData }) => {
            const isBkDataOrEs = ['bkdata', 'es'].includes(row.log_access_type);
            const editKey = isBkDataOrEs ? authorityMap.MANAGE_INDICES_AUTH : authorityMap.MANAGE_COLLECTION_AUTH;
            const searchKey = isBkDataOrEs ? authorityMap.MANAGE_INDICES_AUTH : authorityMap.SEARCH_LOG_AUTH;
            const isRelatedSpace = !!row.is_related_space;
            return (
            <div class='table-operation'>
              <span
                class={{
                  'link mr-6': true,
                  disabled: !getOperatorCanClick(row, 'search'),
                }}
                v-cursor={{ active: !row.permission?.[searchKey] }}
                on-click={() => handleEditOperation(row, 'search')}
              >
                {t('检索')}
              </span>
              {isRelatedSpace ? (
                <BklogPopover
                  options={{
                    placement: 'top',
                    theme: 'dark',
                    appendTo: document.body,
                  } as any}
                  trigger='hover'
                  content={() => renderRelatedSpaceTipContent(row)}
                >
                  <span
                    class={{ link: true, disabled: true }}
                    v-cursor={{ active: !row.permission?.[editKey] }}
                  >
                    {t('编辑')}
                    </span>
                </BklogPopover>
              ) : (
                <span
                  class={{
                    link: true,
                    disabled: !getOperatorCanClick(row, 'edit'),
                  }}
                  v-cursor={{ active: !row.permission?.[editKey] }}
                  on-click={() => handleEditOperation(row, 'edit')}
                >
                  {t('编辑')}
                </span>
              )}
              {!isRelatedSpace && <span class='bk-icon icon-more more-btn table-more-btn' />}
              <div
                style={{ display: 'none' }}
                class='row-menu-popover'
              >
                <div class='row-menu-content'>
                  {renderMenu(row).map(item => (
                    <span
                      key={item.key}
                      v-cursor={{ active: !row.permission?.[editKey] }}
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
            );
          },
        },
      ];
      // 合并本地存储的列宽个人设置
      return columns.map((col) => {
        const storedWidth = col.colKey ? columnsWidthSetting.value[col.colKey] : undefined;
        return {
          ...col,
          ...(storedWidth ? { width: storedWidth } : {}),
          sorter: false,
        };
      });
    });

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

    /** 将 bk-search-select 选中值转换为列表接口 conditions */
    const getSearchConditions = (): IFilterCondition[] => {
      const conditionMap = new Map<string, Set<number | string>>();
      const queryValues = new Set<string>();
      const searchFieldIds = new Set(searchFieldOptions.map(field => field.id));

      for (const item of searchSelectValues.value) {
        if (!searchFieldIds.has(item.id)) {
          if (item.id) {
            queryValues.add(item.id);
          }
          continue;
        }

        const values = item.values || [];
        if (!values.length) {
          continue;
        }
        const conditionValues = conditionMap.get(item.id) || new Set<number | string>();
        for (const value of values) {
          conditionValues.add(value.id);
        }
        conditionMap.set(item.id, conditionValues);
      }

      const fieldConditions = Array.from(conditionMap.entries()).map(([key, values]) => ({
        key,
        value: Array.from(values),
      }));
      if (queryValues.size > 0) {
        fieldConditions.push({ key: 'query', value: Array.from(queryValues) });
      }
      return fieldConditions;
    };

    /** 合并同 key 的数组条件 */
    const mergeRequestConditions = (requestConditions: IFilterCondition[]): IFilterCondition[] => {
      const conditionMap = new Map<string, Set<number | string>>();

      for (const condition of requestConditions) {
        const conditionValues = conditionMap.get(condition.key) || new Set<number | string>();
        const values = Array.isArray(condition.value) ? condition.value : [condition.value];
        for (const value of values) {
          if (value !== '') {
            conditionValues.add(value);
          }
        }
        if (conditionValues.size > 0) {
          conditionMap.set(condition.key, conditionValues);
        }
      }

      const fieldConditions = Array.from(conditionMap.entries()).map(([key, values]) => ({
        key,
        value: Array.from(values),
      }));
      return fieldConditions;
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
        // 归属属于个人设置，切换索引集时保持不重置（「全部」视图下不生效但保留存储值）
        const effectiveSource = getEffectiveSource();
        // 清空其他过滤条件，保留归属条件
        conditions.value = effectiveSource ? [{ key: 'collector_source', value: [effectiveSource] }] : [];
        filterValue.value = {
          log_access_type: '',
          collector_scenario_id: '',
          storage_display_name: '',
          status: '',
          created_by: '',
          updated_by: '',
          tags: [],
          is_related_space: effectiveSource,
        };
        tagSelect.value = ['all'];
        searchSelectValues.value = [];
        reloadList();
        getCollectorFieldEnums();
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

    /** 获取全量标签列表 */
    const fetchLabelList = () => {
      $http.request('unionSearch/unionLabelList', {
        query: {
          space_uid: spaceUid.value,
        },
      }).then(res => {
        selectLabelList.value = res.data || [];
        // 构建过滤列表："全部"选项 + 非内置标签
        const notBuiltInList = (res.data || [])
          .filter(item => !item.is_built_in)
          .map(item => ({
            id: item.tag_id,
            name: item.name,
          }));
        filterLabelList.value = [{ id: 'all', name: t('全部') }, ...notBuiltInList];
      });
    };

    /** 更新行数据中的标签 */
    const handleUpdateTags = (row: ITableRowData, newTags: Array<{ name: string;[key: string]: unknown }>) => {
      row.tags = newTags;
    };

    /** 标签过滤 - 处理选中项变化 */
    const handleTagSelectChange = (v: (string | number)[]) => {
      if (!v.length) {
        tagSelect.value = ['all'];
        return;
      }
      const lastSelect = v[v.length - 1];
      if (lastSelect === 'all') {
        tagSelect.value = [lastSelect];
      } else {
        tagSelect.value = v.filter(item => !(item === 'all'));
      }
    };

    /** 标签过滤 - 处理提交（确定按钮） */
    const handleTagSubmit = (v: (string | number)[]) => {
      const tags = !v.includes('all') ? (v as number[]) : [];
      filterValue.value = { ...filterValue.value, tags };

      // 重建 conditions，保留非 tags 的过滤条件
      const newConditions: IFilterCondition[] = [];
      for (const condition of conditions.value) {
        if (condition.key !== 'tags') {
          newConditions.push(condition);
        }
      }
      if (tags.length > 0) {
        newConditions.push({ key: 'tags', value: tags });
      }

      conditions.value = newConditions;
      reloadList();
    };

    /** 标签过滤 - 处理下拉框展开/关闭时重置选中项 */
    const handleToggleTagSelect = () => {
      const currentTags = filterValue.value.tags;
      tagSelect.value = Array.isArray(currentTags) && currentTags.length > 0 ? [...currentTags] : ['all'];
    };

    onMounted(() => {
      // 监听用户信息更新事件
      tenantManager.on('userInfoUpdated', handleUserInfoUpdated);
      getCollectorFieldEnums();
      fetchLabelList();
      nextTick(() => {
        if (!authGlobalInfo.value) {
          checkCreateAuth();
        }
        // 初始化时计算表格最大高度
        calculateMaxTableHeight();
        // 监听窗口大小变化
        window.addEventListener('resize', handleWindowResize);
        document.addEventListener('mousedown', handleDocumentMouseDown, true);
      });
    });

    onBeforeUnmount(() => {
      tenantManager.off('userInfoUpdated', handleUserInfoUpdated);
      destroyTippyInstances();
      // 清除状态轮询定时器
      stopCollectStatusTimer();
      // 标记组件已卸载
      isUnmounted = true;
      // 移除窗口大小变化监听
      window.removeEventListener('resize', handleWindowResize);
      document.removeEventListener('mousedown', handleDocumentMouseDown, true);
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
        .then((res) => {
          const usageMap = new Map<number | string, IStorageUsageItem>();
          // 构建使用量映射表，提高查找效率
          for (const item of res.data || []) {
            if (item.index_set_id != null) {
              usageMap.set(Number(item.index_set_id), item);
            }
          }

          // 更新表格数据
          tableList.value = tableList.value.map((item) => {
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
        .catch((error) => {
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
        .then((res) => {
          if (isUnmounted || !res.result) {
            stopCollectStatusTimer();
            return;
          }
          const isHasRunning = res.data.filter(item => item.status === 'running').length > 0;
          tableList.value = tableList.value.map((item) => {
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
          ordering: getOrdering(sortConfig.value),
        };

        const requestConditions = mergeRequestConditions([...conditions.value, ...getSearchConditions()]);
        if (requestConditions.length > 0) {
          params.conditions = requestConditions;
        }

        const indexSetId = (props.indexSet as IListItemData)?.index_set_id;
        if (indexSetId && indexSetId !== 'all') {
          params.parent_index_set_id = indexSetId;
          params.include_related_spaces = true;
        } else {
          params.include_related_spaces = false;
        }

        const res = await $http.request(
          'collect/newCollectList',
          {
            data: params,
          },
          {
            cancelToken: new CancelToken((c) => {
              listInterfaceCancel.value = c;
              isCancelToken.value = true;
            }),
          },
        );
        listLoading.value = false;
        tableList.value = ((res.data?.list || []) as ITableRowData[]).map((item) => {
          const localParentIndexSet = getLocalParentIndexSet(item);
          if (!localParentIndexSet) {
            return item;
          }

          return {
            ...item,
            parent_index_set_ids: localParentIndexSet.ids,
            parent_index_sets: localParentIndexSet.sets,
          };
        });
        pagination.value.total = res.data?.total || 0;
        // 收集索引集ID
        const indexSetIds: Array<number | string> = [];
        const collectorConfigIds: Array<number | string> = [];

        for (const item of tableList.value) {
          item.collector_config_id && collectorConfigIds.push(item.collector_config_id);
          if (item.index_set_id !== null) {
            indexSetIds.push(item.index_set_id);
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
          // 批量获取用户信息，直接用返回值更新显示名称映射
          // （已缓存的用户不会触发 userInfoUpdated 事件，需要同步处理）
          const userInfoMap = await tenantManager.batchGetUserDisplayInfo(Array.from(userIds));
          const newMap = new Map(userDisplayNameMap.value);
          let hasUpdate = false;
          for (const [bkUsername, userInfo] of userInfoMap.entries()) {
            if (userInfo?.display_name && newMap.get(bkUsername) !== userInfo.display_name) {
              newMap.set(bkUsername, userInfo.display_name);
              hasUpdate = true;
            }
          }
          if (hasUpdate) {
            userDisplayNameMap.value = newMap;
          }
        }
      } catch (error) {
        listLoading.value = false;
        !isCancelToken.value && console.log('获取列表数据失败:', error, isCancelToken.value);
      }
    };

    /**
     * 从过滤选项数组中提取用户ID
     * @param items - 过滤选项数组
     * @returns 用户ID数组
     */
    const extractUserIds = (items: Array<{ key?: string;[key: string]: unknown }>): string[] => {
      return (items || []).map(item => item.key).filter(Boolean) as string[];
    };

    /**
     * 处理过滤选项，添加用户显示名称
     * @param items - 过滤选项数组
     * @param userInfoMap - 用户信息映射
     * @returns 处理后的过滤选项数组
     */
    const processFilterItemsWithUserInfo = (
      items: Array<{ key?: string; label?: string;[key: string]: unknown }>,
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
        const indexSetId = (props.indexSet as IListItemData)?.index_set_id;
        const res = await $http.request('collect/collectorFieldEnums', {
          query: {
            space_uid: spaceUid.value,
            include_related_spaces: indexSetId !== 'all',
          },
        });
        if (res.data) {
          const fieldEnums = res.data as ICollectorFieldEnumsResponse;
          const createdByList = fieldEnums.created_by || [];
          const updatedByList = fieldEnums.updated_by || [];
          collectorSearchEnums.value = {
            name: fieldEnums.name || [],
            table_id: fieldEnums.table_id || [],
            bk_data_id: fieldEnums.bk_data_id || [],
            storage_display_name: fieldEnums.storage_display_name || [],
            bk_data_name: fieldEnums.bk_data_name || [],
          };

          // 提取所有用户ID并去重
          const createdByUserIds = extractUserIds(createdByList);
          const updatedByUserIds = extractUserIds(updatedByList);
          const allUserIds = [...new Set([...createdByUserIds, ...updatedByUserIds])];

          // 批量获取用户信息
          let userInfoMap = new Map<string, { display_name: string }>();
          if (allUserIds.length > 0) {
            userInfoMap = await tenantManager.batchGetUserDisplayInfo(allUserIds);
            // 同步更新显示名称映射（已缓存的用户不会触发 userInfoUpdated 事件）
            const newMap = new Map(userDisplayNameMap.value);
            let hasUpdate = false;
            for (const [bkUsername, userInfo] of userInfoMap.entries()) {
              if (userInfo?.display_name && newMap.get(bkUsername) !== userInfo.display_name) {
                newMap.set(bkUsername, userInfo.display_name);
                hasUpdate = true;
              }
            }
            if (hasUpdate) {
              userDisplayNameMap.value = newMap;
            }
          }

          // 处理过滤选项，添加用户显示名称
          const processedCreatedBy = processFilterItemsWithUserInfo(createdByList, userInfoMap);
          const processedUpdatedBy = processFilterItemsWithUserInfo(updatedByList, userInfoMap);

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
      const isBkDataOrEs = ['bkdata', 'es'].includes(row.log_access_type);
      const requestConfig = isBkDataOrEs
        ? { api: 'indexSet/remove', params: { index_set_id: row.index_set_id } }
        : { api: 'collect/deleteCollect', params: { collector_config_id: row.collector_config_id } };

      $http
        .request(requestConfig.api, {
          params: requestConfig.params,
        })
        .then((res) => {
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
      // 前置校验：视觉禁用的菜单项，点击也不应执行
      if (!getOperatorCanClick(row, key)) return;

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
          .then((res) => {
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
        showStopTypeDialog.value = true;
        return;
      }

      // 删除操作（getOperatorCanClick 已做前置校验，这里直接弹确认框）
      if (key === 'delete') {
        window.mainComponent?.$bkInfo({
          type: 'warning',
          subTitle: t('当前采集项名称为{n}，确认要删除？', { n: row.collector_config_name || row.name }),
          confirmFn: () => {
            requestDeleteCollect(row);
          },
        });
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
          .then((res) => {
            if (res.data?.check_record_id) {
              isShowDetection.value = true;
              const checkRecordId = res.data.check_record_id;
              handleCollectorCheck(checkRecordId);
            }
          })
          .catch((error) => {
            console.log('一键检测失败:', error);
          });
        return;
      }

      handleEditOperation(row, key);
    };

    /**
     * 自定义上报类型直接调用停用接口
     * @param isStopIndexSet - 是否停用索引集
     */
    const handleDirectStop = (isStopIndexSet: boolean) => {
      $http
        .request('collect/stopCollect', {
          params: {
            collector_config_id: currentRow.value.collector_config_id,
          },
          data: {
            is_stop_index_set: isStopIndexSet,
          },
        })
        .then((res) => {
          if (res.result) {
            reloadList();
          }
        })
        .catch(() => {
          showMessage(t('停用失败'), 'error');
        });
    };

    /**
     * 处理表格分页变化
     * @param pageInfo - 分页信息
     */
    const handlePageChange = (pageInfo: IPaginationInfo) => {
      pagination.value.current = pageInfo.current;
      pagination.value.pageSize = pageInfo.pageSize;
      // 页大小为个人设置，变更即持久化
      updateSetting({ pageSize: pageInfo.pageSize });
      getTableList();
    };

    /**
     * 新增采集项
     */
    const handleCreateOperation = () => {
      const { index_set_id: indexSetId } = props.indexSet;
      operateHandler({}, 'add', 'linux', indexSetId);
    };

    /** 关闭表格样式更新提示，并在当前浏览器中持久隐藏 */
    const handleCloseTableStyleUpdateAlert = () => {
      showTableStyleUpdateAlert.value = false;
      localStorage.setItem(TABLE_STYLE_UPDATE_ALERT_STORAGE_KEY, 'true');
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
     * 跳转到关联空间的采集项管理页面
     * @param row - 表格行数据
     */
    const handleJumpToRelatedSpace = (row: ITableRowData) => {
      // 1. 获取权限 key
      const isBkDataOrEs = ['bkdata', 'es'].includes(row.log_access_type);
      const editKey = isBkDataOrEs
        ? authorityMap.MANAGE_INDICES_AUTH
        : authorityMap.MANAGE_COLLECTION_AUTH;

      // 2. 检查权限
      if (!row.permission?.[editKey]) {
        // 无权限，拉起申请弹窗
        operateHandler(row, 'edit', row.log_access_type, props.indexSet.index_set_id);
        return;
      }

      // 3. 有权限，手动构建路由并跳转（使用 row.space_uid）
      const routeData = router.resolve({
        name: 'collectEdit',
        params: {
          // bkdata/es 类型没有 collector_config_id，使用 index_set_id
          collectorId: String(
            isBkDataOrEs ? (row.index_set_id ?? '') : (row.collector_config_id ?? '')
          ),
        },
        query: {
          typeKey: String(row.log_access_type),
          spaceUid: String(row.space_uid), // 使用 row.space_uid
          backRoute: route.name,
        },
      });

      window.open(routeData.href, '_blank', 'noopener,noreferrer');
    };

    /**
     * 渲染关联空间提示弹窗内容
     * @param row - 表格行数据
     */
    const renderRelatedSpaceTipContent = (row: ITableRowData) => {
      return (
        <div class='related-space-tip-content'>
          <div>{t('关联空间的索引集，无法编辑')}</div>
          <div>
            <i18n path='请{0}编辑。'>
                <span
                  class='link-to-space'
                  on-click={() => {
                    handleJumpToRelatedSpace(row);
                  }}
                >
                {t('前往对应的空间')}
                <i class='bklog-icon bklog-jump'></i>
              </span>
            </i18n>
          </div>
        </div>
      );
    };

    /**
     * 处理表格过滤变化
     * @param filters - 过滤对象
     */
    const handleFilterChange = (filters: Record<string, string | string[]>) => {
      const nextFilters = { ...filterValue.value, ...filters };
      filterValue.value = nextFilters;

      const newConditions: IFilterCondition[] = [];
      for (const [key, value] of Object.entries(nextFilters)) {
        if (key === 'tags') {
          if (Array.isArray(value) && value.length > 0) {
            newConditions.push({ key: 'tags', value });
          }
          continue;
        }

        const values = Array.isArray(value) ? value : value ? [value] : [];
        if (values.length === 0) continue;
        newConditions.push({
          key: key === 'is_related_space' ? 'collector_source' : key,
          value: values,
        });
      }

      conditions.value = newConditions;
      reloadList();
    };

    /** 切换采集项归属 */
    const handleSourceFilterChange = (value: string) => {
      // 归属为个人设置，变更即持久化
      sourceSetting.value = value;
      updateSetting({ source: value });
      handleFilterChange({ is_related_space: value });
    };
    /** 同步排序字段下拉框的临时值 */
    const syncSortFieldDraft = (sortBy: string, callback?: () => void) => {
      if (sortFieldDraft.value === sortBy) {
        callback?.();
        return;
      }
      isSyncingSortFieldDraft = true;
      sortFieldDraft.value = sortBy;
      nextTick(() => {
        isSyncingSortFieldDraft = false;
        callback?.();
      });
    };

    const applySortChange = (sortInfo: ISortConfig): void => {
      sortConfig.value = sortInfo;
      syncSortFieldDraft(sortInfo.sortBy || 'name');
      // 排序为个人设置，变更即持久化
      updateSetting({ sortBy: sortInfo.sortBy, descending: !!sortInfo.descending });
      reloadList();
    };

    /**
     * 处理排序变化
     * @param sortInfo - 排序信息
     */
    const sortChange = (sortInfo: ISortConfig): void => {
      const isSameSort = sortInfo.sortBy === sortConfig.value.sortBy
        && !!sortInfo.descending === !!sortConfig.value.descending;
      if (isSameSort) {
        return;
      }

      const isSwitchingToUsageSort = sortInfo.sortBy
        && ['daily_usage', 'total_usage'].includes(sortInfo.sortBy)
        && sortInfo.sortBy !== sortConfig.value.sortBy;
      if (isSwitchingToUsageSort) {
        pendingUsageSortInfo.value = sortInfo;
        nextTick(() => {
          syncSortFieldDraft(sortConfig.value.sortBy || 'name', () => {
            usageSortPopoverRef.value?.show();
          });
        });
        return;
      }
      applySortChange(sortInfo);
    };

    const handleConfirmUsageSort = () => {
      const sortInfo = pendingUsageSortInfo.value;
      pendingUsageSortInfo.value = null;
      if (sortInfo) {
        applySortChange(sortInfo);
      }
      usageSortPopoverRef.value?.hide();
    };

    const handleCancelUsageSort = () => {
      pendingUsageSortInfo.value = null;
      syncSortFieldDraft(sortConfig.value.sortBy || 'name');
      usageSortPopoverRef.value?.hide();
    };

    /** 使用工具栏选择的字段和方向排序 */
    const handleToolbarSortChange = (sortBy: string, direction: string) => {
      sortChange({ sortBy, descending: direction === 'desc' });
    };

    /** 切换排序字段时采用该字段在 sort.text 中约定的默认方向 */
    const handleToolbarSortFieldChange = (sortBy: string) => {
      if (isSyncingSortFieldDraft) {
        return;
      }
      const fieldOption = sortFieldOptions.find(item => item.id === sortBy);
      handleToolbarSortChange(sortBy, fieldOption?.defaultDirection || 'asc');
    };

    /**
     * 字段设置变更：colKey 列表转字段 id 后持久化
     * @param colKeys - 表格组件确认的可见列 colKey 列表
     */
    const handleSettingChange = (colKeys: string[]) => {
      const fieldIds = colKeys.map(colKey => COL_KEY_TO_FIELD_ID_MAP[colKey] || colKey);
      selectedFieldIds.value = fieldIds;
      updateSetting({ selectedFields: fieldIds });
    };

    /**
     * 列宽变更：浅比较避免拖拽中的无效写入，变化时持久化
     * @param columnsWidth - 各列最新宽度 { [colKey]: number }
     */
    const handleColumnResizeChange = (columnsWidth: Record<string, number>) => {
      const prev = columnsWidthSetting.value;
      const keys = Object.keys(columnsWidth);
      const isUnchanged = keys.length === Object.keys(prev).length
        && keys.every(key => prev[key] === columnsWidth[key]);
      if (isUnchanged) {
        return;
      }
      columnsWidthSetting.value = { ...columnsWidth };
      updateSetting({ columnsWidth: columnsWidthSetting.value });
    };

    /**
     * 判断是否有过滤条件或搜索关键词
     * @returns 是否有过滤条件
     */
    const hasFilterOrSearch = computed(() => {
      const hasSearch = searchSelectValues.value.length > 0;
      const hasFilter = conditions.value.length > 0;
      return hasSearch || hasFilter;
    });

    const collectProject = computed(() => projectManages(store.state.topMenu, 'collection-item'));

    /**
     * 处理空状态操作
     * @param type - 操作类型
     */
    const handleEmptyOperation = (type: string) => {
      if (type === 'clear-filter') {
        conditions.value = [];
        filterValue.value = {
          log_access_type: '',
          collector_scenario_id: '',
          storage_display_name: '',
          status: '',
          created_by: '',
          updated_by: '',
          tags: [],
          is_related_space: '',
        };
        tagSelect.value = ['all'];
        // 用户主动清空筛选时同步清空归属个人设置
        sourceSetting.value = '';
        updateSetting({ source: '' });
      }
      searchSelectValues.value = [];
      reloadList();
    };

    return () => (
      <div
        ref={containerRef}
        class='v2-log-collection-table'
      >
        {showTableStyleUpdateAlert.value && (
          <bk-alert
            class='table-style-update-alert'
            type='info'
            title={t('管理页面于8月6号更新，更新后个性化设置会被重置覆盖。请重新调整配置表格样式。')}
            closable
            onClose={handleCloseTableStyleUpdateAlert}
          />
        )}
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
              v-cursor={{ active: isAllowedCreate }}
              disabled={!collectProject.value || isLoading.value || isAllowedCreate === null}
            >
              {t('采集项')}
            </bk-button>
            <AddExistingCollectDialog
              indexSetId={(props.indexSet as IListItemData)?.index_set_id ?? ''}
              spaceUid={spaceUid.value}
              on-confirm={() => {
                reloadList();
                emit('refresh-index-group');
              }}
            >
              <bk-button
                outline={true}
                theme='primary'
                v-cursor={{ active: isAllowedCreate }}
                disabled={!collectProject.value || isLoading.value || isAllowedCreate === null}
                v-show={(props.indexSet as IListItemData)?.index_set_id !== 'all'}
              >
                <i class='bklog-icon bklog-link-guanlian' />
                {t('关联采集项管理')}
              </bk-button>
            </AddExistingCollectDialog>
          </div>
          <div class='tool-filter-group'>
            {(props.indexSet as IListItemData)?.index_set_id !== 'all' && (
              <div class='source-filter-group'>
                <span class='source-filter-label'>{t('归属')}</span>
                <span class='source-filter-tabs'>
                  {sourceFilterOptions.map((item, index) => (
                    <span
                      key={item.value || 'all'}
                      class={{
                        'source-filter-tab': true,
                        active: filterValue.value.is_related_space === item.value,
                        'hide-divider': filterValue.value.is_related_space === item.value
                          || filterValue.value.is_related_space === sourceFilterOptions[index + 1]?.value,
                      }}
                      on-click={() => handleSourceFilterChange(item.value)}
                    >
                      {item.className && <i class={['source-filter-dot', item.className]} />}
                      {item.label}
                    </span>
                  ))}
                </span>
              </div>
            )}
            <div class='toolbar-sort-select'>
              <i class='bklog-icon bklog-paixu sort-prefix-icon' />
              <BklogPopover
                class='usage-sort-popover-trigger'
                ref={usageSortPopoverRef}
                trigger='manual'
                contentClass='usage-sort-confirm'
                options={{
                  placement: 'top',
                  theme: 'bklog-basic-light',
                  interactive: true,
                  maxWidth: 288,
                  appendTo: document.body,
                  onHidden: () => {
                    pendingUsageSortInfo.value = null;
                    syncSortFieldDraft(sortConfig.value.sortBy || 'name');
                  },
                } as any}
                {...{
                  scopedSlots: {
                    content: () => (
                      <div>
                        <div class='usage-sort-confirm-message'>
                          {t('按用量排序需要实时请求集群使用情况，需等待较长时间，点击确认执行')}
                        </div>
                        <div class='usage-sort-confirm-actions'>
                          <bk-button
                            size='small'
                            theme='primary'
                            on-click={handleConfirmUsageSort}
                          >
                            {t('确认')}
                          </bk-button>
                          <bk-button
                            size='small'
                            on-click={handleCancelUsageSort}
                          >
                            {t('取消')}
                          </bk-button>
                        </div>
                      </div>
                    ),
                  },
                }}
              >
                <bk-select
                  class='sort-field-select'
                  clearable={false}
                  disabled={isLoading.value}
                  value={sortFieldDraft.value}
                  onInput={(value: string) => {
                    if (!isSyncingSortFieldDraft) {
                      sortFieldDraft.value = value;
                    }
                  }}
                  onChange={(value: string) => handleToolbarSortFieldChange(value)}
                >
                  {sortFieldOptions.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    />
                  ))}
                </bk-select>
              </BklogPopover>
              <bk-select
                class={{
                  'sort-direction-select': true,
                  'is-name-sort': sortConfig.value.sortBy === 'name',
                }}
                clearable={false}
                disabled={isLoading.value}
                value={sortConfig.value.descending ? 'desc' : 'asc'}
                onChange={(value: string) => handleToolbarSortChange(sortConfig.value.sortBy || 'name', value)}
              >
                {sortDirectionOptions.value.map(item => (
                  <bk-option
                    key={item.id}
                    id={item.id}
                    name={item.name}
                  />
                ))}
              </bk-select>
            </div>
            <bk-search-select
              data={searchSelectData.value}
              ext-cls='tool-search-select'
              placeholder={t('搜索 数据 ID、采集名、数据名、存储集群、存储名')}
              show-condition={false}
              show-popover-tag-change={false}
              values={searchSelectValues.value}
              clearable
              onChange={(values: ISearchSelectValue[]) => {
                searchSelectValues.value = values;
                reloadList();
              }}
              onClear={() => {
                searchSelectValues.value = [];
                reloadList();
              }}
              onSearch={reloadList}
            />
          </div>
        </div>
        <div
          ref={tableMainRef}
          class='v2-log-collection-table-main'
        >
          <TableComponent
            class='log-collection-table'
            resizable={true}
            columns={allColumns.value}
            data={tableList.value}
            sortConfig={sortConfig.value}
            loading={isLoading.value}
            on-page-change={handlePageChange}
            pagination={pagination.value}
            height={tableList.value.length === 0 ? HEIGHT_CONSTANTS.MIN_TABLE_HEIGHT : undefined}
            maxHeight={tableList.value.length > 0 ? maxTableHeight.value : undefined}
            rowHeight={56}
            on-sort-change={sortChange}
            on-filter-change={handleFilterChange}
            filterValue={filterValue.value}
            on-empty-click={handleEmptyOperation}
            colKeyMap={FIELD_ID_TO_COL_KEY_MAP}
            settingFields={settingFields.value}
            visibleColKeys={visibleColKeys.value}
            on-setting-change={handleSettingChange}
            on-column-resize-change={handleColumnResizeChange}
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
            stopTypeKey={stopTypeKey.value}
            status={currentRow.value.status}
            config={currentRow.value}
            isStopCollection={true}
            isContainer={currentRow.value.environment === 'container'}
            on-change={(value: boolean) => {
              showCollectIssuedSlider.value = value;
            }}
            on-refresh={() => {
              reloadList();
              showCollectIssuedSlider.value = false;
            }}
          />
          <StopTypeDialog
            showDialog={showStopTypeDialog.value}
            isCustomReport={isCustomReport.value}
            on-update={(val: boolean) => {
              showCollectIssuedSlider.value = true;
              stopTypeKey.value = val;
            }}
            on-confirm={(val: boolean) => {
              handleDirectStop(val);
            }}
            on-cancel={() => {
              showStopTypeDialog.value = false;
            }}
          />
        </div>
      </div>
    );
  },
});
