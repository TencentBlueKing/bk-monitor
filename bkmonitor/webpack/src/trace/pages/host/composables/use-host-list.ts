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

import { type Ref, type ShallowRef, computed, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Message } from 'bkui-vue';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';
import { copyText } from 'monitor-common/utils/utils';
import { storeToRefs } from 'pinia';

import { type SelectTypeEnum, SelectType } from '../../../components/across-page-selection/across-page-selection';
import { EMode } from '../../../components/retrieval-filter/typing';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import useUserConfig from '../../../hooks/useUserConfig';
import { useHostStore } from '../../../store/modules/host';
import { HostSelectAllModeEnum } from '../constants/enum';
import { HOST_FILTER_FIELDS, HOST_LIST_COLUMNS, HOST_LIST_DEFAULT_PAGE_SIZE } from '../constants/host-list';
import { getHostInfoList, getHostMetricInfoList } from '../services/host-service';
import { useHostListWorker } from './use-host-list-worker';
import { useHostUrlParams } from './use-host-url-params';

import type {
  IGetValueFnParams,
  IWhereItem,
  IWhereValueOptionsItem,
} from '../../../components/retrieval-filter/typing';
import type { EHostQuickCategory, HostSelectAllModeType, IHostListRow, IHostQuickCardStats } from '../types';
import type { IHostTopoTreeNode } from '../types/topo';

interface IUseHostListOptions {
  activeCategory: ShallowRef<'' | EHostQuickCategory>;
  filterExpanded: ShallowRef<boolean>;
  keyword: ShallowRef<string>;
  /** 当前选中的拓扑节点（页面层注入），用于联动过滤主机列表 */
  selectedNode: Ref<IHostTopoTreeNode | null>;
  where: ShallowRef<IWhereItem[]>;
}

const EMPTY_CATEGORY_STATS: IHostQuickCardStats = { alarm: 0, cpu: 0, disk: 0, mem: 0 };

/**
 * @description 主机列表业务编排（Controller）：数据加载、拓扑联动、快捷过滤、检索过滤、
 * 关键字搜索、排序、分页、行勾选、列设置、指标聚合方式切换、复制 IP。
 * 视图层只消费这里暴露的状态与方法，保证 MVC 分层。
 * 全量数据的行转换、过滤、排序、分页切片在 Web Worker 中执行，避免超大数据阻塞主线程。
 */
export const useHostList = (options: IUseHostListOptions) => {
  const { selectedNode, where, filterExpanded, activeCategory, keyword } = options;
  const { setUrlParams } = useHostUrlParams();
  const hostListWorker = useHostListWorker();
  const { timeRange, timezone, refreshImmediate, refreshInterval } = storeToRefs(useHostStore());
  const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();

  /** 基础数据加载中（第一屏） */
  const loading = shallowRef(false);
  /** 指标数据加载中（指标列展示骨架） */
  const metricLoading = shallowRef(false);
  /** 全量主机行数（主线程不持有全量行对象） */
  const rawRowCount = shallowRef(0);
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
  /** 当前展示列 */
  const visibleColumns = shallowRef<string[]>(HOST_LIST_COLUMNS.filter(c => c.checked).map(c => c.id));
  /** 置顶配置映射（rowId -> 1），与旧版 performance-table 数据结构一致 */
  const stickyValue = shallowRef<Record<string, 1>>({});

  /** 快捷过滤卡片统计（Worker 计算结果） */
  const categoryStats = shallowRef<IHostQuickCardStats>({ ...EMPTY_CATEGORY_STATS });
  /** 过滤排序后的总条数 */
  const total = shallowRef(0);
  /** 当前页数据（Worker 仅回传一页，避免主线程持有全量） */
  const pagedRows = shallowRef<IHostListRow[]>([]);

  /** retrieval-filter 字段列表（静态定义） */
  const filterFields = HOST_FILTER_FIELDS;

  /** 集群模块等字段的完整选项映射（字段 -> 选项树），用于已选条件 tag 的名称还原 */
  const filterOptionsMap = shallowRef<Record<string, unknown>>({});

  let intervalTimer: null | ReturnType<typeof setTimeout> = null;
  let baseList: Awaited<ReturnType<typeof getHostInfoList>> = [];

  watch([timeRange, timezone], () => {
    setUrlParams();
    loadMetricData();
  });

  watch(refreshImmediate, () => {
    setUrlParams();
    loadData();
  });

  watch(refreshInterval, () => {
    setUrlParams();
    handleIntervalQuery();
  });

  watch(
    [selectedNode, activeCategory, where, keyword, sortInfo, page, pageSize],
    () => {
      if (!rawRowCount.value) {
        return;
      }
      refreshList();
    },
    { deep: true }
  );

  // 切换拓扑节点：回到第一页并清空跨节点的勾选（含全选模式）
  watch(selectedNode, () => {
    resetPage();
    selectAllMode.value = HostSelectAllModeEnum.NONE;
    selectedRowKeys.value = new Set();
    excludedRowKeys.value = new Set();
  });

  // 过滤条件（分类 / where / keyword）变化：
  // - 跨页全选：重算全量匹配并排除用户手动取消的行
  // - 本页全选 / 手动选择：清空已选（对齐旧版 current 模式 handleResetCheck 行为）
  watch(
    [activeCategory, where, keyword],
    async () => {
      if (selectAllMode.value === HostSelectAllModeEnum.ACROSS) {
        const { rowKeys } = await hostListWorker.getFilteredRowKeys(getComputeParams());
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

  const refreshList = (immediate = false) => {
    const params = getComputeParams();
    if (immediate) {
      hostListWorker.computeNow(params);
      return;
    }
    hostListWorker.scheduleCompute(params);
  };

  hostListWorker.setComputeHandler(data => {
    categoryStats.value = data.categoryStats;
    total.value = data.total;
    pagedRows.value = data.pagedRows;
  });

  /** 检索候选项获取函数（Worker 内基于全量数据构建的候选项映射） */
  const getValueFn = async (params: IGetValueFnParams): Promise<IWhereValueOptionsItem> => {
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

  /** 加载数据：基础数据先渲染，指标数据后补充 */
  const loadData = async () => {
    loading.value = true;
    metricLoading.value = true;
    // 手动/定时刷新时重置选择（对标旧版 handleResetCheck）
    selectAllMode.value = HostSelectAllModeEnum.NONE;
    selectedRowKeys.value = new Set();
    excludedRowKeys.value = new Set();
    try {
      baseList = await getHostInfoList();
      const initResult = await hostListWorker.initBaseData(baseList);
      rawRowCount.value = initResult.rawRowCount;
      await loadStickyConfig();
      refreshList(true);
      // 拉取 filterOptionsMap 供集群模块字段展示名称映射
      const filterOptionsMapResult = (await hostListWorker.getFilterOptionsMap()) as Record<
        string,
        Record<string, unknown>
      >;
      filterOptionsMap.value = filterOptionsMapResult.filterOptionsMap;
    } finally {
      loading.value = false;
    }
    try {
      const bk_host_ids = baseList.map(row => row.bk_host_id);
      const [start_time, end_time] = handleTransformToTimestamp(timeRange.value);
      const metricListMap = await getHostMetricInfoList({
        bk_host_ids,
        start_time,
        end_time,
      });
      await hostListWorker.mergeMetrics(metricListMap);
      refreshList(true);
    } finally {
      metricLoading.value = false;
    }
  };

  const loadMetricData = async () => {
    if (!baseList.length) {
      return;
    }

    try {
      metricLoading.value = true;
      const bk_host_ids = baseList.map(row => row.bk_host_id);
      const [start_time, end_time] = handleTransformToTimestamp(timeRange.value);
      const metricListMap = await getHostMetricInfoList({
        bk_host_ids,
        start_time,
        end_time,
      });
      await hostListWorker.mergeMetrics(metricListMap);
    } finally {
      metricLoading.value = false;
    }
  };

  /** 过滤条件变化后统一回到第一页 */
  const resetPage = () => {
    page.value = 1;
  };

  const handleKeywordChange = useDebounceFn((value: string) => {
    keyword.value = value;
    resetPage();
  }, 500);
  const handleWhereChange = (value: IWhereItem[]) => {
    where.value = value;
    resetPage();
  };
  const handleQueryStringChange = (value: string) => {
    queryString.value = value;
  };
  const handleFilterModeChange = (mode: EMode) => {
    filterMode.value = mode;
  };
  const handleSearch = () => {
    resetPage();
  };
  const toggleFilterExpand = () => {
    filterExpanded.value = !filterExpanded.value;
  };
  const handleCategoryClick = (key: EHostQuickCategory) => {
    activeCategory.value = activeCategory.value === key ? '' : key;
    resetPage();
  };
  const handleSortChange = (sort: string | string[]) => {
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
    // 跨页全选模式下保持全量选中并排除用户手动取消的行
    if (selectAllMode.value === HostSelectAllModeEnum.ACROSS) {
      const { rowKeys } = await hostListWorker.getFilteredRowKeys(getComputeParams());
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
    if (type === SelectType.ALL_SELECTED) {
      selectAllMode.value = HostSelectAllModeEnum.ACROSS;
      excludedRowKeys.value = new Set();
      const { rowKeys } = await hostListWorker.getFilteredRowKeys(getComputeParams());
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
    keyword.value = '';
    where.value = [];
    activeCategory.value = '';
    resetPage();
  };

  /** 复制选中主机的内网 IP（每行一个，换行分隔） */
  const handleCopyIp = async () => {
    if (!selectedRowKeys.value.size) {
      return;
    }
    const response = await hostListWorker.getSelectedIps([...selectedRowKeys.value]);
    const ipText = response.ips.join('\n');
    if (!ipText) {
      return;
    }
    copyText(ipText, (msg: string) => {
      Message({ message: msg, theme: 'error' });
    });
    Message({ message: window.i18n.t('复制成功'), theme: 'success' });
  };

  const handleIntervalQuery = () => {
    clearTimeout(intervalTimer);
    if (refreshInterval.value < 0) {
      return;
    }

    intervalTimer = setInterval(() => {
      loadData();
    }, refreshInterval.value);
  };

  onMounted(() => {
    loadData();
    handleIntervalQuery();
  });

  onBeforeUnmount(() => {
    if (intervalTimer) {
      clearTimeout(intervalTimer);
    }
  });

  return {
    // 状态
    loading,
    metricLoading,
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
    // 方法
    getValueFn,
    loadData,
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
