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
import { Prop, Component, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { connect, disconnect } from 'echarts/core';
import { random } from 'monitor-common/utils/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import MiniTimeSeries from 'monitor-ui/chart-plugins/plugins/mini-time-series/mini-time-series';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { K8sNewTabEnum, K8sTableColumnKeysEnum } from '../../typings/k8s-new';

import type { ITableItemMap } from '../../typings/table';
import type { IFilterByItem } from '../filter-by-condition/utils';
import type { IGroupByChangeEvent } from '../group-by-condition/group-by-condition';
import type { TranslateResult } from 'vue-i18n';

import './k8s-table-new.scss';

/**
 * @description k8s 表格列配置类型
 */
export interface K8sTableColumn {
  /** 字段类型 */
  type: K8sTableColumnTypeEnum;
  /** 字段id */
  id: K8sTableColumnKeysEnum;
  /** 字段名称 */
  name: TranslateResult;
  /** 是否伸缩大小 */
  resizable?: boolean;
  /** 是否可以排序 */
  sortable?: 'custom' | boolean;
  /** 列宽 */
  width?: number;
  /** 最小列宽 */
  min_width?: number;
  /** 是否需要异步加载 */
  asyncable?: boolean;
  /** 是否开启 添加/移除 筛选项 icon */
  k8s_filter?: boolean;
  /** 是否开启 下钻 icon */
  k8s_group?: boolean;
  /** 自定义获取值逻辑函数 */
  getValue?: (row: K8sTableRow) => unknown;
}

export type K8sTableRow = Pick<ITableItemMap, 'datapoints'>['datapoints'] | Record<string, string>;

export interface K8sTableSort {
  prop: K8sTableColumnKeysEnum.CPU | K8sTableColumnKeysEnum.INTERNAL_MEMORY | null;
  sort: 'ascending' | 'descending' | null;
}

export interface K8sTableClickEvent {
  column: K8sTableColumn;
  row: K8sTableRow;
}

export type K8sTableFilterByEvent = K8sTableClickEvent & { checked: boolean; ids: Array<number | string> };
export type K8sTableGroupByEvent = Pick<IGroupByChangeEvent, 'checked' | 'id'>;

interface K8sTableNewProps {
  /** 当前选中的 tab 项 */
  activeTab: K8sNewTabEnum;
  /** 表格数据 */
  tableData: any[];
  /** 下钻 Group By 过滤项 */
  groupFilters: Array<number | string>;
  /** 筛选 Filter By 过滤项 */
  filterBy: IFilterByItem[];
  /** 骨架屏loading */
  loading: boolean;
  /** 触底加载 loading */
  scrollLoading: boolean;
  /** 是否重新渲染 table 组件消除状态 */
  refreshKey: string;
}
interface K8sTableNewEvent {
  onTextClick: (item: K8sTableClickEvent) => void;
  onFilterChange: (item: K8sTableFilterByEvent) => void;
  onGroupChange: (item: K8sTableGroupByEvent) => void;
  onSortChange: (sort: K8sTableSort) => void;
  onScrollEnd: () => void;
  onClearSearch: () => void;
}

/**
 * @enum k8s 表格列类型枚举
 */
export enum K8sTableColumnTypeEnum {
  DATA_CHART = 'data_chart',
  RESOURCES_TEXT = 'resources_text',
}

/**
 * @description: k8s table 数据明细 table 动态列 keys
 */
const tabToTableDetailColumnDynamicKeys = [
  K8sTableColumnKeysEnum.CLUSTER,
  K8sTableColumnKeysEnum.NAMESPACE,
  K8sTableColumnKeysEnum.WORKLOAD,
  K8sTableColumnKeysEnum.WORKLOAD_TYPE,
  K8sTableColumnKeysEnum.POD,
  K8sTableColumnKeysEnum.CONTAINER,
];

/**
 * @description: k8s table 数据明细 table 静态列（必有） keys
 */
const tabToTableDetailColumnFixedKeys = [K8sTableColumnKeysEnum.CPU, K8sTableColumnKeysEnum.INTERNAL_MEMORY];

@Component
export default class K8sTableNew extends tsc<K8sTableNewProps, K8sTableNewEvent> {
  /** k8s table ResourcesText 类型列 获取值静态方法  */
  static getResourcesTextRowValue(row: K8sTableRow, column: K8sTableColumn) {
    if (column?.getValue) {
      return column.getValue(row) || '--';
    }
    return row?.[column.id] || '--';
  }

  /** workload / workload_type 不同场景下的获取值逻辑  */
  static getWorkloadValue(columnKey: K8sTableColumnKeysEnum, index: 0 | 1) {
    return row => (row?.[columnKey] as string)?.split(':')?.[index] || '--';
  }

  /** 当前页面 tab */
  @Prop({ type: String, default: K8sNewTabEnum.LIST }) activeTab: K8sNewTabEnum;
  /** 表格数据 */
  @Prop({ type: Array }) tableData: any[];
  /** GroupBy 选择器选中数据 */
  @Prop({ type: Array, default: () => [] }) groupFilters: Array<number | string>;
  /** FilterBu 选择器选中数据 */
  @Prop({ type: Array, default: () => [] }) filterBy: IFilterByItem[];
  /** 表格骨架屏 loading  */
  @Prop({ type: Boolean, default: false }) loading: boolean;
  /** 表格触底加载更多 loading  */
  @Prop({ type: Boolean, default: false }) scrollLoading: boolean;
  /** 是否重新渲染 table 组件消除状态 */
  @Prop({ type: String }) refreshKey: boolean;

  get isListTab() {
    return this.activeTab === K8sNewTabEnum.LIST;
  }

  get tableColumnsConfig() {
    const map = this.getKeyToTableColumnsMap();
    const columns: K8sTableColumn[] = [];
    const iterationTarget = this.isListTab ? this.groupFilters : tabToTableDetailColumnDynamicKeys;
    const addColumn = (arr, targetArr) => {
      for (const key of targetArr) {
        if (map[key]) {
          arr.push(map[key]);
        }
      }
    };
    addColumn(columns, iterationTarget);
    addColumn(columns, tabToTableDetailColumnFixedKeys);
    return { map, columns };
  }

  /** 缩略图分组Id枚举 */
  get chartGroupIdsMap() {
    return this.tableColumnsConfig.columns.reduce((acc, cur, ind) => {
      if (cur.type === K8sTableColumnTypeEnum.DATA_CHART) {
        if (acc[cur.id]) disconnect(acc[cur.id]);
        acc[cur.id] = `${random(8)}_${ind}`;
        connect(acc[cur.id]);
      }
      return acc;
    }, {});
  }

  @Emit('textClick')
  labelClick(column: K8sTableColumn, row: K8sTableRow) {
    return { column, row };
  }

  @Emit('filterChange')
  filterChange(column: K8sTableColumn, row: K8sTableRow, checked: boolean, filterIds: Array<number | string>) {
    return { column, row, checked, ids: filterIds };
  }

  @Emit('groupChange')
  groupChange(item: K8sTableGroupByEvent) {
    return item;
  }

  @Emit('sortChange')
  sortChange(sort: K8sTableSort) {
    return sort;
  }

  @Emit('scrollEnd')
  scrollEnd() {}

  @Emit('clearSearch')
  clearSearch() {
    return {};
  }

  getKeyToTableColumnsMap(): Record<K8sTableColumnKeysEnum, K8sTableColumn> {
    const { CLUSTER, POD, WORKLOAD_TYPE, WORKLOAD, NAMESPACE, CONTAINER, CPU, INTERNAL_MEMORY } =
      K8sTableColumnKeysEnum;

    return {
      [CLUSTER]: {
        id: CLUSTER,
        name: this.$t('cluster'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 90,
      },
      [POD]: {
        id: POD,
        name: this.$t('Pod'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 260,
        k8s_filter: this.isListTab,
      },
      [WORKLOAD_TYPE]: {
        id: WORKLOAD_TYPE,
        name: this.$t('workload_type'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 160,
        getValue: K8sTableNew.getWorkloadValue(K8sTableColumnKeysEnum.WORKLOAD, 1),
      },
      [WORKLOAD]: {
        id: WORKLOAD,
        name: this.$t('workload'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 160,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
        getValue: !this.isListTab ? K8sTableNew.getWorkloadValue(K8sTableColumnKeysEnum.WORKLOAD, 0) : null,
      },
      [NAMESPACE]: {
        id: NAMESPACE,
        name: this.$t('namespace'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 100,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [CONTAINER]: {
        id: CONTAINER,
        name: this.$t('container'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 120,
      },
      [CPU]: {
        id: CPU,
        name: this.$t('CPU使用率'),
        sortable: 'custom',
        type: K8sTableColumnTypeEnum.DATA_CHART,
        min_width: 180,
      },
      [INTERNAL_MEMORY]: {
        id: INTERNAL_MEMORY,
        name: this.$t('内存使用率'),
        sortable: 'custom',
        type: K8sTableColumnTypeEnum.DATA_CHART,
        min_width: 180,
      },
    };
  }

  /**
   * @description 表格排序
   * @param {Object} { prop, order }
   */
  handleSortChange(sortItem: K8sTableSort) {
    this.sortChange(sortItem);
  }

  /**
   * @description 清空搜索条件
   *
   */
  handleClearSearch() {
    this.clearSearch();
  }

  /**
   * @description 表格列 filter icon 渲染配置方法
   * @param {K8sTableRow} row
   * @param {K8sTableColumn} column
   */
  filterIconFormatter(row: K8sTableRow, column: K8sTableColumn) {
    if (!column.k8s_filter) {
      return null;
    }
    const id = K8sTableNew.getResourcesTextRowValue(row, column);
    if (id) {
      const groupItem = this.filterBy?.find?.(v => v.key === column.id);
      const filterIds = (groupItem?.value?.length && groupItem?.value.filter(v => v !== id)) || [];
      const hasFilter = groupItem?.value?.length && filterIds?.length !== groupItem?.value?.length;
      return hasFilter ? (
        <i
          class='icon-monitor icon-sousuo- is-active'
          v-bk-tooltips={{ content: this.$t('移除该筛选项'), interactive: false }}
          onClick={() => this.filterChange(column, row, false, filterIds)}
        />
      ) : (
        <i
          class='icon-monitor icon-a-sousuo'
          v-bk-tooltips={{ content: this.$t('添加为筛选项'), interactive: false }}
          onClick={() => this.filterChange(column, row, true, [...filterIds, id])}
        />
      );
    }
    return null;
  }

  /**
   * @description 表格列 group icon 渲染配置方法
   * @param {K8sTableRow} row
   * @param {K8sTableColumn} column
   */
  groupIconFormatter(row: K8sTableRow, column: K8sTableColumn) {
    if (!column.k8s_group) {
      return null;
    }
    const hasGroup = this.groupFilters.includes(column.id);
    return (
      <i
        class={['icon-monitor', 'icon-xiazuan', { 'is-active': hasGroup }]}
        v-bk-tooltips={{
          content: this.$t(`${hasGroup ? '移除' : ''}下钻`),
          interactive: false,
        }}
        onClick={() => this.groupChange({ id: column.id, checked: !hasGroup })}
      />
    );
  }

  /**
   * @description K8sTableColumnTypeEnum.RESOURCES_TEXT 类型表格列文本渲染方法
   * @param {K8sTableColumnKeysEnum} columnKey
   */
  resourcesTextFormatter(column: K8sTableColumn) {
    return (row: K8sTableRow) => {
      const text = K8sTableNew.getResourcesTextRowValue(row, column);
      if (!text) {
        return '--';
      }
      return (
        <div class='k8s-table-col-item'>
          <span
            class='col-item-label'
            v-bk-overflow-tips={{ interactive: false }}
            onClick={() => this.labelClick(column, row)}
          >
            {text}
          </span>
          <div class='col-item-operate'>
            {this.filterIconFormatter(row, column)}
            {this.groupIconFormatter(row, column)}
          </div>
        </div>
      );
    };
  }

  /**
   * @description K8sTableColumnTypeEnum.DATA_CHART 类型表格列图表渲染方法
   * @param {K8sTableColumnKeysEnum} columnKey
   */
  datapointsFormatter(column: K8sTableColumn) {
    return (row: K8sTableRow) => {
      const value = row[column.id] as Pick<ITableItemMap, 'datapoints'>['datapoints'] & { loading: boolean };
      if (!value?.datapoints?.length) {
        return '--';
      }
      return !(column.asyncable && value.loading) ? (
        <MiniTimeSeries
          data={value.datapoints || []}
          disableHover={true}
          groupId={this.chartGroupIdsMap[column.id]}
          lastValueWidth={80}
          unit={value.unit}
          unitDecimal={value?.unitDecimal}
          valueTitle={value.valueTitle}
        />
      ) : (
        <img
          class='loading-svg'
          alt=''
          src={loadingIcon}
        />
      );
    };
  }

  handleSetFormatter(column: K8sTableColumn) {
    switch (column.type) {
      case K8sTableColumnTypeEnum.RESOURCES_TEXT:
        return this.resourcesTextFormatter(column);
      default:
        return this.datapointsFormatter(column);
    }
  }

  transformColumn(column: K8sTableColumn) {
    return (
      <bk-table-column
        key={`column_${column.id}`}
        width={column.width}
        formatter={this.handleSetFormatter(column)}
        label={column.name}
        minWidth={column.min_width}
        prop={column.id}
        resizable={typeof column.resizable === 'boolean' ? column.resizable : true}
        show-overflow-tooltip={false}
        sortable={column.sortable}
      />
    );
  }

  render() {
    return (
      <div class='k8s-table-new'>
        <bk-table
          key={this.refreshKey}
          ref='table'
          style={{ display: !this.loading ? 'block' : 'none' }}
          height='100%'
          scrollLoading={{
            isLoading: this.scrollLoading,
            size: 'mini',
            theme: 'info',
            icon: 'circle-2-1',
            placement: 'right',
          }}
          data={this.tableData}
          size='small'
          on-scroll-end={this.scrollEnd}
          on-sort-change={val => this.handleSortChange(val as K8sTableSort)}
        >
          {this.tableColumnsConfig.columns.map(column => this.transformColumn(column))}
          <EmptyStatus
            slot='empty'
            textMap={{
              empty: this.$t('暂无数据'),
            }}
            type={this.groupFilters?.length || this.filterBy?.length ? 'search-empty' : 'empty'}
            onOperation={() => this.handleClearSearch()}
          />
        </bk-table>
        {this.loading ? (
          <TableSkeleton
            class='table-skeleton'
            type={5}
          />
        ) : null}
      </div>
    );
  }
}
