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

import { type Ref, type ShallowRef, shallowRef, watch, onMounted, onBeforeUnmount } from 'vue';
import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';

import { EMode } from '../../../components/retrieval-filter/typing';
import {
  HOST_AGG_METHOD_LIST,
  HOST_FILTER_FIELDS,
  HOST_LIST_COLUMNS,
  HOST_LIST_DEFAULT_PAGE_SIZE,
} from '../constants/host-list';
import { getHostInfoList, getHostMetricInfoList } from '../services/host-service';
import { useHostListWorker } from './use-host-list-worker';
import { storeToRefs } from 'pinia';
import { useHostStore } from '../../../store/modules/host';
import { useHostUrlParams } from './use-host-url-params';

import type {
  IGetValueFnParams,
  IWhereItem,
  IWhereValueOptionsItem,
} from '../../../components/retrieval-filter/typing';
import type { EHostAggMethod, EHostQuickCategory, IHostListRow, IHostQuickCardStats } from '../types/host-list';
import type { IHostTopoTreeNode } from '../types/topo';

interface IUseHostListOptions {
  activeCategory: ShallowRef<'' | EHostQuickCategory>;
  filterExpanded: ShallowRef<boolean>;
  keyword: ShallowRef<string>;
  /** 当前选中的拓扑节点（页面层注入），用于联动过滤主机列表 */
  selectedNode: Ref<IHostTopoTreeNode | null>;
  where: ShallowRef<IWhereItem[]>;
}

/** 指标列聚合方式默认值（全部默认 avg） */
const getDefaultAggMethodMap = (): Record<string, EHostAggMethod> => {
  const map: Record<string, EHostAggMethod> = {};
  for (const column of HOST_LIST_COLUMNS) {
    if (column.type === 'metric') {
      map[column.id] = 'avg';
    }
  }
  return map;
};

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
  /** 每页条数 */
  const pageSize = shallowRef(HOST_LIST_DEFAULT_PAGE_SIZE);
  /** 选中行 rowId 集合 */
  const selectedRowKeys = shallowRef<(number | string)[]>([]);
  /** 当前展示列 */
  const visibleColumns = shallowRef<string[]>(HOST_LIST_COLUMNS.filter(c => c.checked).map(c => c.id));
  /** 指标列聚合方式 */
  const aggMethodMap = shallowRef<Record<string, EHostAggMethod>>(getDefaultAggMethodMap());

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

  let intervalTimer: ReturnType<typeof setTimeout> | null = null;

  watch([timeRange, timezone, refreshImmediate], () => {
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

  // 切换拓扑节点：回到第一页并清空跨节点的勾选
  watch(selectedNode, () => {
    resetPage();
    selectedRowKeys.value = [];
  });

  const getComputeParams = () => ({
    activeCategory: activeCategory.value,
    keyword: keyword.value,
    page: page.value,
    pageSize: pageSize.value,
    selectedNode: selectedNode.value,
    sortInfo: sortInfo.value,
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

  /** 加载数据：基础数据先渲染，指标数据后补充 */
  const loadData = async () => {
    loading.value = true;
    metricLoading.value = true;
    let baseList: Awaited<ReturnType<typeof getHostInfoList>> = [];
    try {
      baseList = await getHostInfoList();
      const initResult = await hostListWorker.initBaseData(baseList);
      rawRowCount.value = initResult.rawRowCount;
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
      const metricListMap = await getHostMetricInfoList({ bk_host_ids });
      await hostListWorker.mergeMetrics(metricListMap);
      refreshList(true);
    } finally {
      metricLoading.value = false;
    }
  };

  /** 过滤条件变化后统一回到第一页 */
  const resetPage = () => {
    page.value = 1;
  };

  const handleKeywordChange = (value: string) => {
    keyword.value = value;
    resetPage();
  };
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
  };
  const handlePageChange = (value: number) => {
    page.value = value;
  };
  const handlePageSizeChange = (value: number) => {
    pageSize.value = value;
    resetPage();
  };
  const handleSelectChange = async (keys: (number | string)[], isAcrossPage: boolean) => {
    if (isAcrossPage) {
      // 跨页全选：从 Worker 取当前过滤条件下的全量行 key（表格 rowKey=id）
      const response = await hostListWorker.getFilteredRowKeys(getComputeParams());
      selectedRowKeys.value = response.rowKeys;
      return;
    }
    selectedRowKeys.value = keys.map(String);
  };
  const handleColumnsChange = (columns: string[]) => {
    visibleColumns.value = columns;
  };
  const handleAggMethodChange = (metricKey: string, method: EHostAggMethod) => {
    aggMethodMap.value = { ...aggMethodMap.value, [metricKey]: method };
  };

  /** 复制选中主机的内网 IP（每行一个，换行分隔） */
  const handleCopyIp = async () => {
    if (!selectedRowKeys.value.length) {
      return;
    }
    const response = await hostListWorker.getSelectedIps(selectedRowKeys.value.map(String));
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
    aggMethodMap,
    // 派生
    categoryStats,
    pagedRows,
    total,
    filterFields,
    aggMethodList: HOST_AGG_METHOD_LIST,
    filterOptionsMap,
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
    handleSelectChange,
    handleColumnsChange,
    handleAggMethodChange,
    handleCopyIp,
  };
};

export type HostListContext = ReturnType<typeof useHostList>;
