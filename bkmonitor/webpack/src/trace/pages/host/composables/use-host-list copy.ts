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

import { type Ref, computed, shallowRef, watch } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';

import { EMode } from '../../../components/retrieval-filter/typing';
import {
  HOST_AGG_METHOD_LIST,
  HOST_FILTER_FIELDS,
  HOST_LIST_COLUMNS,
  HOST_LIST_DEFAULT_PAGE_SIZE,
} from '../constants/host-list';
import { getMockHostInfoList, getMockHostMetricInfoList } from '../services/host-service';
import {
  buildFilterOptionsMap,
  computeCategoryStats,
  createHostListRow,
  matchKeyword,
  matchQuickCategory,
  matchTopoNode,
  matchWhere,
  sortRows,
} from '../utils/host-list';

import type {
  IGetValueFnParams,
  IWhereItem,
  IWhereValueOptionsItem,
} from '../../../components/retrieval-filter/typing';
import type { EHostAggMethod, EHostQuickCategory, IHostListRow } from '../types/host-list';
import type { IHostTopoTreeNode } from '../types/topo';

interface IUseHostListOptions {
  /** 当前选中的拓扑节点（页面层注入），用于联动过滤主机列表 */
  selectedNode: Ref<IHostTopoTreeNode | null>;
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

/**
 * @description 主机列表业务编排（Controller）：数据加载、拓扑联动、快捷过滤、检索过滤、
 * 关键字搜索、排序、分页、行勾选、列设置、指标聚合方式切换、复制 IP。
 * 视图层只消费这里暴露的状态与方法，保证 MVC 分层。
 */
export const useHostList = (options: IUseHostListOptions) => {
  const { selectedNode } = options;

  /** 基础数据加载中（第一屏） */
  const loading = shallowRef(false);
  /** 指标数据加载中（指标列展示骨架） */
  const metricLoading = shallowRef(false);
  /** 全量主机行数据（含派生字段） */
  const rawRows = shallowRef<IHostListRow[]>([]);

  /** 关键字模糊搜索 */
  const keyword = shallowRef('');
  /** retrieval-filter ui 模式 where 条件 */
  const where = shallowRef<IWhereItem[]>([]);
  /** retrieval-filter 语句模式 */
  const queryString = shallowRef('');
  /** retrieval-filter 模式 */
  const filterMode = shallowRef<EMode>(EMode.ui);
  /** 高级过滤是否展开 */
  const filterExpanded = shallowRef(false);

  /** 当前激活的快捷过滤分类（空为不过滤） */
  const activeCategory = shallowRef<'' | EHostQuickCategory>('');
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

  /** 过滤候选项映射（由全量数据组合生成） */
  const optionsMap = computed(() => buildFilterOptionsMap(rawRows.value));
  /** 拓扑节点范围内的主机（卡片统计与后续过滤的基准集） */
  const nodeScopedRows = computed(() => rawRows.value.filter(row => matchTopoNode(row, selectedNode.value)));
  /** 快捷过滤卡片统计 */
  const categoryStats = computed(() => computeCategoryStats(nodeScopedRows.value));
  /** 过滤后的数据（快捷分类 + 检索条件 + 关键字） */
  const filteredRows = computed(() =>
    nodeScopedRows.value.filter(
      row =>
        matchQuickCategory(row, activeCategory.value) &&
        matchWhere(row, where.value) &&
        matchKeyword(row, keyword.value)
    )
  );
  /** 排序后的数据 */
  const sortedRows = computed(() => sortRows(filteredRows.value, sortInfo.value));
  /** 总条数 */
  const total = computed(() => sortedRows.value.length);
  /** 当前页数据 */
  const pagedRows = computed(() => {
    const start = (page.value - 1) * pageSize.value;
    return sortedRows.value.slice(start, start + pageSize.value);
  });
  /** 选中的主机行 */
  const selectedRows = computed(() => {
    const keySet = new Set(selectedRowKeys.value.map(String));
    return rawRows.value.filter(row => keySet.has(row.rowId));
  });

  /** retrieval-filter 字段列表（静态定义） */
  const filterFields = HOST_FILTER_FIELDS;

  /** 检索候选项获取函数（适配 retrieval-filter v2 接口：fields 数组 + where 结构） */
  const getValueFn = async (params: IGetValueFnParams): Promise<IWhereValueOptionsItem> => {
    // fields[0]: 当前筛选字段的 snake_case 名；where[0].value[0]: 用户输入的搜索关键词
    const field = params.fields?.[0] || '';
    const list = optionsMap.value.get(field) || [];
    const search = String(params.where?.[0]?.value?.[0] || '').toLowerCase();
    const filtered = search ? list.filter(item => String(item.name).toLowerCase().includes(search)) : list;
    return {
      count: filtered.length,
      list: filtered.slice(0, params.limit || 200),
    };
  };

  /** 加载数据：基础数据先渲染，指标数据后补充 */
  const loadData = async () => {
    loading.value = true;
    metricLoading.value = true;
    try {
      const baseList = await getMockHostInfoList();
      rawRows.value = baseList.map(createHostListRow);
    } finally {
      loading.value = false;
    }
    try {
      const metricList = await getMockHostMetricInfoList();
      rawRows.value = metricList.map(createHostListRow);
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
  const handleSelectChange = (keys: (number | string)[]) => {
    selectedRowKeys.value = keys;
  };
  const handleColumnsChange = (columns: string[]) => {
    visibleColumns.value = columns;
  };
  const handleAggMethodChange = (metricKey: string, method: EHostAggMethod) => {
    aggMethodMap.value = { ...aggMethodMap.value, [metricKey]: method };
  };

  /** 复制选中主机的内网 IP（每行一个，换行分隔） */
  const handleCopyIp = () => {
    if (!selectedRows.value.length) {
      return;
    }
    const ipText = selectedRows.value
      .map(row => row.bk_host_innerip)
      .filter(Boolean)
      .join('\n');
    copyText(ipText, (msg: string) => {
      Message({ message: msg, theme: 'error' });
    });
    Message({ message: window.i18n.t('复制成功'), theme: 'success' });
  };

  // 切换拓扑节点：回到第一页并清空跨节点的勾选
  watch(selectedNode, () => {
    resetPage();
    selectedRowKeys.value = [];
  });

  return {
    // 状态
    loading,
    metricLoading,
    rawRows,
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
    selectedRows,
    filterFields,
    aggMethodList: HOST_AGG_METHOD_LIST,
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
