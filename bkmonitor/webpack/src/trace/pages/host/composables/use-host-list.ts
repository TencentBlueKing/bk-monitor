/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type Ref, type ShallowRef, computed, onMounted, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Message } from 'bkui-vue';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';
import { copyText } from 'monitor-common/utils/utils';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';

import { type SelectTypeEnum, SelectType } from '../../../components/across-page-selection/across-page-selection';
import { EMode } from '../../../components/retrieval-filter/typing';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useTableColumnsCache } from '../../../hooks/use-table-columns-cache';
import useUserConfig from '../../../hooks/useUserConfig';
import { useAppStore } from '../../../store/modules/app';
import { useHostStore } from '../../../store/modules/host';
import { HostSelectAllModeEnum } from '../constants/enum';
import { HOST_FILTER_FIELDS, HOST_LIST_COLUMNS, HOST_LIST_DEFAULT_PAGE_SIZE } from '../constants/host-list';
import { hostTargetKey, resolveHostRequestScope } from '../utils/share-scope';
import { useHostListData } from './use-host-list-data';
import { useHostListWorker } from './use-host-list-worker';
import { useHostUrlParams } from './use-host-url-params';

import type {
  IGetValueFnParams,
  IWhereItem,
  IWhereValueOptionsItem,
} from '../../../components/retrieval-filter/typing';
import type { EHostQuickCategory, HostSelectAllModeType, IHostListRow, TCopyIpField } from '../types';
import type { IHostTopoTreeNode } from '../types/topo';

interface IUseHostListOptions {
  activeCategory: ShallowRef<'' | EHostQuickCategory>;
  filterExpanded: ShallowRef<boolean>;
  keyword: ShallowRef<string>;
  readonly: boolean;
  /** 当前选中的拓扑节点（页面层注入），用于联动过滤主机列表 */
  selectedNode: Ref<IHostTopoTreeNode | null>;
  where: ShallowRef<IWhereItem[]>;
}

/**
 * @description 主机列表业务编排（Controller）：数据加载、拓扑联动、快捷过滤、检索过滤、
 * 关键字搜索、排序、分页、行勾选、列设置、指标聚合方式切换、复制 IP。
 * 视图层只消费这里暴露的状态与方法，保证 MVC 分层。
 * 全量数据的行转换、过滤、排序、分页切片在 Web Worker 中执行，避免超大数据阻塞主线程。
 */
export const useHostList = (options: IUseHostListOptions) => {
  const route = useRoute();
  const appStore = useAppStore();
  const { selectedNode, where, filterExpanded, activeCategory, keyword } = options;
  const { setUrlParams } = useHostUrlParams();
  const hostListWorker = useHostListWorker();
  const { timeRange, timezone, refreshGeneration, refreshInterval } = storeToRefs(useHostStore());
  const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();

  /** retrieval-filter 语句模式 */
  const queryString = shallowRef('');
  /** retrieval-filter 模式 */
  const filterMode = shallowRef<EMode>(EMode.ui);

  /** 排序（tdesign 字符串格式：`-key` 倒序 / `key` 正序） */
  const sortInfo = shallowRef('');
  /** 当前页码 */
  const page = shallowRef(1);
  /** 每页条数（初始值取全局统一页码配置，未配置时回退到默认 50） */
  const pageSize = shallowRef(commonPageSizeGet() ?? HOST_LIST_DEFAULT_PAGE_SIZE);
  /** 选中行 key 集合（唯一权威来源，Set 便于 O(1) 判定与增删，父组件用于复制 IP 等） */
  const selectedRowKeys = shallowRef<Set<string>>(new Set());
  /** 全选模式：none=手动选择；page=本页全选；across=跨页全选。决定过滤变化时重算范围（none 清空） */
  const selectAllMode = shallowRef<HostSelectAllModeType>(HostSelectAllModeEnum.NONE);
  /** 跨页全选模式下被用户手动排除的行 key（筛选/分页/置顶变化时保持排除语义） */
  const excludedRowKeys = shallowRef<Set<string>>(new Set());
  /** 当前展示列与列宽（公共 hook，localStorage 持久化） */
  const { storageColumns: visibleColumns, fieldsWidthConfig } = useTableColumnsCache({
    storageKey: 'trace_host_list_columns',
    defaultColumns: HOST_LIST_COLUMNS.filter(c => c.checked).map(c => c.id),
    validColumnKeys: HOST_LIST_COLUMNS.map(c => c.id),
  });
  /** 置顶配置映射（rowId -> 1），与旧版 performance-table 数据结构一致 */
  const stickyValue = shallowRef<Record<string, 1>>({});

  const filterFields = HOST_FILTER_FIELDS;
  let selectionRequestGeneration = 0;
  const authorizedScope = resolveHostRequestScope(options.readonly, route.query, selectedNode.value);
  const getRequestScope = () => ({
    ...authorizedScope,
    bk_biz_id: selectedNode.value?.bk_biz_id ?? appStore.bizId,
  });
  const getPageScope = () => {
    const scope = getRequestScope();
    const node = selectedNode.value;
    if (!node) return scope;
    if ('bk_host_id' in node) return { bk_biz_id: scope.bk_biz_id, bk_host_id: node.bk_host_id };
    return { bk_biz_id: scope.bk_biz_id, bk_obj_id: node.bk_obj_id, bk_inst_id: node.bk_inst_id };
  };

  const data = useHostListData({
    getComputeParams: () => getComputeParams(),
    getPageScope,
    getScope: getRequestScope,
    getTimeParams: () => {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      return { start_time: startTime, end_time: endTime };
    },
    page,
    pageSize,
    worker: hostListWorker,
  });
  const {
    loading,
    loadError,
    metricLoading,
    metricLoadError,
    rawRowCount,
    categoryStats,
    total,
    pagedRows,
    filterOptionsMap,
    fullDataReady,
    loadMetricData,
    loadPageData,
  } = data;

  const resetSelection = () => {
    selectionRequestGeneration += 1;
    selectAllMode.value = HostSelectAllModeEnum.NONE;
    selectedRowKeys.value = new Set();
    excludedRowKeys.value = new Set();
  };
  const loadData = () => {
    if (!selectedNode.value) return;
    resetSelection();
    return data.loadData();
  };
  watch(
    [timeRange, timezone, refreshGeneration, () => JSON.stringify(getRequestScope())],
    () => {
      setUrlParams();
      void loadData();
    },
    { flush: 'sync' }
  );
  watch(refreshInterval, () => setUrlParams());

  const targetKey = computed(() => hostTargetKey(selectedNode.value));

  // 节点变化先重置页码与选择，下面的单次视图更新使用最新上下文。
  watch(
    targetKey,
    () => {
      resetPage();
      resetSelection();
      if (!fullDataReady.value) void data.loadCategoryStats();
    },
    { flush: 'sync' }
  );

  watch([targetKey, page, pageSize], () => data.invalidatePage(), { flush: 'sync' });
  watch([targetKey, page, pageSize], () => {
    if (!selectedNode.value) return;
    if (!fullDataReady.value) void loadPageData();
    void data.refreshList();
  });
  watch(
    [activeCategory, where, keyword, sortInfo, stickyValue],
    () => {
      data.invalidateView();
      refreshList();
    },
    { deep: true, flush: 'sync' }
  );

  watch(fullDataReady, async ready => {
    if (!ready || !selectedRowKeys.value.size) return;
    const requestGeneration = ++selectionRequestGeneration;
    const requestedKeys = [...selectedRowKeys.value];
    try {
      const { rows } = await hostListWorker.getSelectedRows(requestedKeys);
      if (requestGeneration !== selectionRequestGeneration || !fullDataReady.value) return;
      const validKeys = new Set(rows.map(row => String(row.id)));
      const removedKeys = new Set(requestedKeys.filter(key => !validKeys.has(key)));
      selectedRowKeys.value = new Set([...selectedRowKeys.value].filter(key => !removedKeys.has(key)));
    } catch {
      // 选择辅助查询失败不改变当前已展示的数据。
    }
  });

  // 过滤条件（分类 / where / keyword）变化：
  // - 跨页全选：重算全量匹配并排除用户手动取消的行
  // - 本页全选 / 手动选择：清空已选（对齐旧版 current 模式 handleResetCheck 行为）
  watch(
    [activeCategory, where, keyword],
    async () => {
      if (!fullDataReady.value) return;
      const requestGeneration = ++selectionRequestGeneration;
      if (selectAllMode.value === HostSelectAllModeEnum.ACROSS) {
        const { rowKeys } = await hostListWorker.getFilteredRowKeys(getComputeParams());
        if (requestGeneration !== selectionRequestGeneration || selectAllMode.value !== HostSelectAllModeEnum.ACROSS) {
          return;
        }
        const allKeys = new Set(rowKeys.map(String));
        selectedRowKeys.value = new Set([...allKeys].filter(k => !excludedRowKeys.value.has(k)));
        return;
      }
      // page / none 模式：过滤条件变化后清空选择（对齐旧版 current 模式）
      selectAllMode.value = HostSelectAllModeEnum.NONE;
      selectedRowKeys.value = new Set();
      excludedRowKeys.value = new Set();
    },
    { deep: true }
  );

  /** 获取计算参数 */
  const getComputeParams = () => ({
    activeCategory: activeCategory.value,
    keyword: keyword.value,
    page: page.value,
    pageSize: pageSize.value,
    selectedNode: selectedNode.value,
    sortInfo: sortInfo.value,
    stickyValue: stickyValue.value,
    where: where.value,
  });

  const scheduleRefresh = useDebounceFn(() => data.refreshList(), 150);
  const refreshList = (immediate = false) => {
    if (immediate) {
      void data.refreshList();
    } else {
      void scheduleRefresh();
    }
  };

  /** 检索候选项获取函数（Worker 内基于全量数据构建的候选项映射） */
  const getValueFn = async (params: IGetValueFnParams): Promise<IWhereValueOptionsItem> => {
    if (!fullDataReady.value) return { count: 0, list: [] };
    const field = params.fields?.[0] || '';
    const search = String(params.where?.[0]?.value?.[0] || '').toLowerCase();
    const response = await hostListWorker.getFilterOptions(field, search, params.limit || 200);
    return response.result;
  };

  /** 加载置顶配置（与旧版 performance-table 共用 key 和数据结构） */
  const loadStickyConfig = async () => {
    try {
      const config = await handleGetUserConfig<Record<string, 1>>('userStikyNote', { reject403: true });
      stickyValue.value = config || {};
    } catch {
      stickyValue.value = {};
    }
  };

  /** 主机置顶/取消置顶 */
  const handleIpMark = async (row: IHostListRow) => {
    if (!fullDataReady.value) return;
    if (stickyValue.value[row.rowId]) {
      const next = { ...stickyValue.value };
      delete next[row.rowId];
      stickyValue.value = next;
    } else {
      stickyValue.value = { ...stickyValue.value, [row.rowId]: 1 };
    }
    await handleSetUserConfig(JSON.stringify(stickyValue.value));
    refreshList(true);
  };

  /** 过滤条件变化后统一回到第一页 */
  const resetPage = () => {
    page.value = 1;
  };

  const handleKeywordChange = useDebounceFn((value: string) => {
    if (!fullDataReady.value) return;
    keyword.value = value;
    resetPage();
  }, 500);
  const handleWhereChange = (value: IWhereItem[]) => {
    if (!fullDataReady.value) return;
    where.value = value;
    resetPage();
  };
  const handleQueryStringChange = (value: string) => {
    if (!fullDataReady.value) return;
    queryString.value = value;
  };
  const handleFilterModeChange = (mode: EMode) => {
    if (!fullDataReady.value) return;
    filterMode.value = mode;
  };
  const handleSearch = () => {
    if (!fullDataReady.value) return;
    resetPage();
  };
  const toggleFilterExpand = () => {
    filterExpanded.value = !filterExpanded.value;
  };
  const handleCategoryClick = (key: EHostQuickCategory) => {
    if (!fullDataReady.value) return;
    activeCategory.value = activeCategory.value === key ? '' : key;
    resetPage();
  };
  const handleSortChange = (sort: string | string[]) => {
    if (!fullDataReady.value) return;
    sortInfo.value = Array.isArray(sort) ? sort[0] || '' : sort;
    // 排序后 page / none 模式清空选择（对齐旧版 current 模式行为）
    // across 模式保持选择（跨页全选语义不受排序影响）
    if (selectAllMode.value !== HostSelectAllModeEnum.ACROSS) {
      selectAllMode.value = HostSelectAllModeEnum.NONE;
      selectedRowKeys.value = new Set();
    }
  };
  const handlePageChange = (value: number) => {
    if (page.value === value) return;
    page.value = value;
    // 非跨页全选模式下切页重置选择（对齐旧版 current 模式行为）
    if (selectAllMode.value !== HostSelectAllModeEnum.ACROSS) {
      selectAllMode.value = HostSelectAllModeEnum.NONE;
      selectedRowKeys.value = new Set();
    }
  };
  const handlePageSizeChange = async (value: number) => {
    if (pageSize.value === value) return;
    pageSize.value = value;
    /** 持久化到全局统一页码配置，与其他模块保持一致 */
    commonPageSizeSet(value);
    resetPage();
    const requestGeneration = ++selectionRequestGeneration;
    // 跨页全选模式下保持全量选中并排除用户手动取消的行
    if (selectAllMode.value === HostSelectAllModeEnum.ACROSS) {
      const { rowKeys } = await hostListWorker.getFilteredRowKeys(getComputeParams());
      if (requestGeneration !== selectionRequestGeneration || selectAllMode.value !== HostSelectAllModeEnum.ACROSS) {
        return;
      }
      const allKeys = rowKeys.map(String);
      selectedRowKeys.value = new Set(allKeys.filter(k => !excludedRowKeys.value.has(k)));
      return;
    }
    // 本页全选 / 手动选择模式下清空（对齐旧版 current 模式行为）
    selectAllMode.value = HostSelectAllModeEnum.NONE;
    selectedRowKeys.value = new Set();
    excludedRowKeys.value = new Set();
  };
  /**
   * 表头全选框变化（对齐 performance-table 的 check-change）
   * - ALL_SELECTED：跨页全选，选中当前过滤条件全量行
   * - SELECTED：本页全选，仅选中当前页
   * - UN_SELECTED：清空
   */
  const handleHeaderSelect = async (type: SelectTypeEnum) => {
    const requestGeneration = ++selectionRequestGeneration;
    if (type === SelectType.ALL_SELECTED) {
      if (!fullDataReady.value) return;
      selectAllMode.value = HostSelectAllModeEnum.ACROSS;
      excludedRowKeys.value = new Set();
      const { rowKeys } = await hostListWorker.getFilteredRowKeys(getComputeParams());
      if (requestGeneration !== selectionRequestGeneration || selectAllMode.value !== HostSelectAllModeEnum.ACROSS) {
        return;
      }
      selectedRowKeys.value = new Set(rowKeys.map(String));
      return;
    }
    if (type === SelectType.SELECTED) {
      selectAllMode.value = HostSelectAllModeEnum.PAGE;
      excludedRowKeys.value = new Set();
      selectedRowKeys.value = new Set(pagedRows.value.map(row => String(row.id)));
      return;
    }
    selectAllMode.value = HostSelectAllModeEnum.NONE;
    excludedRowKeys.value = new Set();
    selectedRowKeys.value = new Set();
  };

  /**
   * 单行勾选变化（对齐 performance-table 的 row-check）
   * selectedRowKeys 是唯一实际选中集合，跨页 / 非跨页均直接增减
   * page 模式下手动取消某行即退出全选模式，转为手动选择（避免后续过滤重算把它覆盖）
   * across 模式下取消单行保持 across 语义（跨页全选但排除若干行）
   */
  const handleRowCheck = (id: string, checked: boolean) => {
    const key = String(id);
    if (selectAllMode.value === HostSelectAllModeEnum.PAGE && !checked) {
      selectAllMode.value = HostSelectAllModeEnum.NONE;
    }

    // across 模式下同步维护 excludedRowKeys，保证后续筛选/分页/置顶变化时排除语义不丢失
    if (selectAllMode.value === HostSelectAllModeEnum.ACROSS) {
      const nextExcluded = new Set(excludedRowKeys.value);
      if (checked) {
        nextExcluded.delete(key);
      } else {
        nextExcluded.add(key);
      }
      excludedRowKeys.value = nextExcluded;
    }

    const next = new Set(selectedRowKeys.value);
    if (checked) {
      next.add(key);
    } else {
      next.delete(key);
    }
    selectedRowKeys.value = next;
  };

  /**
   * 表头全选框状态（对齐 performance-table 的 allCheckValue）：
   * 跨页全选（across）：以全量匹配 total 为基准，size 0 / ===total / 其余 → 未选 / 全选 / 半选
   * 本页全选 / 手动（page / none）：以当前页为基准，当前页选中数 0 / ===页大小 / 其余 → 未选 / 本页全选 / 半选
   */
  const selectType = computed<SelectTypeEnum>(() => {
    const sel = selectedRowKeys.value;
    if (selectAllMode.value === HostSelectAllModeEnum.ACROSS) {
      if (sel.size === 0) {
        return SelectType.UN_SELECTED;
      }
      if (sel.size === total.value) {
        return SelectType.ALL_SELECTED;
      }
      return SelectType.HALF_ALL_SELECTED;
    }
    const pageIds = new Set(pagedRows.value.map(row => String(row.id)));
    const selectedCount = [...sel].filter(k => pageIds.has(k)).length;
    if (selectedCount === 0) {
      return SelectType.UN_SELECTED;
    }
    if (selectedCount === pageIds.size) {
      return SelectType.SELECTED;
    }
    return SelectType.HALF_SELECTED;
  });
  const handleColumnsChange = (columns: string[]) => {
    visibleColumns.value = columns;
  };

  /** 清空检索条件（关键字、过滤条件、快捷分类） */
  const handleClearFilter = () => {
    if (!fullDataReady.value) return;
    keyword.value = '';
    where.value = [];
    activeCategory.value = '';
    resetPage();
  };

  /** 复制选中主机的指定 IP 字段（每行一个，换行分隔） */
  const handleCopyIp = async (field?: TCopyIpField) => {
    if (!selectedRowKeys.value.size || !field) {
      return;
    }
    const selected = [...selectedRowKeys.value];
    const rows = fullDataReady.value
      ? (await hostListWorker.getSelectedRows(selected)).rows
      : pagedRows.value.filter(row => selectedRowKeys.value.has(String(row.id)));
    const ipList = rows.map(item => item[field]).filter(Boolean);
    const ipText = ipList.join('\n');
    copyText(ipText, (msg: string) => {
      Message({ message: msg, theme: 'error' });
    });
    Message({ message: window.i18n.t('复制成功 {num} 个IP', { num: ipList.length }), theme: 'success' });
  };

  onMounted(() => {
    void loadStickyConfig();
    void loadData();
  });

  return {
    ...data,
    // 状态
    loading,
    loadError,
    metricLoading,
    metricLoadError,
    rawRowCount,
    keyword,
    where,
    queryString,
    filterMode,
    filterExpanded,
    activeCategory,
    sortInfo,
    page,
    pageSize,
    selectedRowKeys,
    visibleColumns,
    // 派生
    categoryStats,
    pagedRows,
    total,
    filterFields,
    filterOptionsMap,
    stickyValue,
    fieldsWidthConfig,
    // 方法
    getValueFn,
    loadData,
    loadMetricData,
    handleKeywordChange,
    handleWhereChange,
    handleQueryStringChange,
    handleFilterModeChange,
    handleSearch,
    toggleFilterExpand,
    handleCategoryClick,
    handleSortChange,
    handlePageChange,
    handlePageSizeChange,
    handleHeaderSelect,
    handleRowCheck,
    selectType,
    handleColumnsChange,
    handleCopyIp,
    handleIpMark,
    handleClearFilter,
  };
};

export type HostListContext = ReturnType<typeof useHostList>;
