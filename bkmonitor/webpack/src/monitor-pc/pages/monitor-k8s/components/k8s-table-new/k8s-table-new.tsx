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

import EmptyStatus from '../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { K8sNewTabEnum } from '../../typings/k8s-new';
import CommonTable from '../common-table';

import type { ITableColumn, TableRow } from '../../typings/table';
import type { IFilterByItem } from '../filter-by-condition/utils';
import type { IGroupByChangeEvent } from '../group-by-condition/group-by-condition';

import './k8s-table-new.scss';

export interface K8sTableColumn extends ITableColumn {
  id: K8sTableColumnKeysEnum;
  k8s_filter?: boolean;
  k8s_group?: boolean;
}

export type K8sTableRow = TableRow & Record<string, { id: number | string; name: string }>;

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
  activeTab: K8sNewTabEnum;
  tableData: any[];
  groupFilters: Array<number | string>;
  filterBy: IFilterByItem[];
  loading: boolean;
  scrollLoading: boolean;
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
 * @description: k8s table column keys 枚举 (方便后期字段名维护)
 */
export enum K8sTableColumnKeysEnum {
  /**
   * @description: cluster - 集群
   */
  CLUSTER = 'cluster',
  /**
   * @description: container - 容器
   */
  CONTAINER = 'container',
  /**
   * @description: cpu - CPU使用率
   */
  CPU = 'cpu',
  /**
   * @description: internal_memory - 内存使用率
   */
  INTERNAL_MEMORY = 'internal_memory',
  /**
   * @description: namespace - namespace
   */
  NAMESPACE = 'namespace',
  /**
   * @description: pod - pod
   */
  POD = 'pod',
  /**
   * @description: workload - workload
   */
  WORKLOAD = 'workload',
  /**
   * @description: workload_type - workload_type
   */
  WORKLOAD_TYPE = 'workload_type',
}

const tabToTableColumnsMap = {
  [K8sNewTabEnum.LIST]: [
    K8sTableColumnKeysEnum.POD,
    K8sTableColumnKeysEnum.WORKLOAD,
    K8sTableColumnKeysEnum.NAMESPACE,
    K8sTableColumnKeysEnum.CPU,
    K8sTableColumnKeysEnum.INTERNAL_MEMORY,
  ],
  [K8sNewTabEnum.DETAIL]: [
    K8sTableColumnKeysEnum.CLUSTER,
    K8sTableColumnKeysEnum.NAMESPACE,
    K8sTableColumnKeysEnum.WORKLOAD,
    K8sTableColumnKeysEnum.WORKLOAD_TYPE,
    K8sTableColumnKeysEnum.POD,
    K8sTableColumnKeysEnum.CONTAINER,
    K8sTableColumnKeysEnum.CPU,
    K8sTableColumnKeysEnum.INTERNAL_MEMORY,
  ],
};

@Component
export default class K8sTableNew extends tsc<K8sTableNewProps, K8sTableNewEvent> {
  static getScopedSlotRowId(row: K8sTableRow, columnKey: K8sTableColumnKeysEnum) {
    return row?.[columnKey]?.id;
  }

  static getScopedSlotRowText(row: K8sTableRow, columnKey: K8sTableColumnKeysEnum) {
    return row?.[columnKey]?.name;
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

  get isListTab() {
    return this.activeTab === K8sNewTabEnum.LIST;
  }

  get tableColumns(): K8sTableColumn[] {
    const map = this.getKeyToTableColumnsMap();
    return tabToTableColumnsMap[this.activeTab].map(key => map[key]);
  }
  // k8s 表格作用域插槽
  get tableScopedSlots() {
    return {
      [K8sTableColumnKeysEnum.CLUSTER]: this.scopedSlotFormatter(K8sTableColumnKeysEnum.CLUSTER),
      [K8sTableColumnKeysEnum.POD]: this.scopedSlotFormatter(K8sTableColumnKeysEnum.POD),
      [K8sTableColumnKeysEnum.WORKLOAD_TYPE]: this.scopedSlotFormatter(K8sTableColumnKeysEnum.WORKLOAD_TYPE),
      [K8sTableColumnKeysEnum.WORKLOAD]: this.scopedSlotFormatter(K8sTableColumnKeysEnum.WORKLOAD),
      [K8sTableColumnKeysEnum.NAMESPACE]: this.scopedSlotFormatter(K8sTableColumnKeysEnum.NAMESPACE),
      [K8sTableColumnKeysEnum.CONTAINER]: this.scopedSlotFormatter(K8sTableColumnKeysEnum.CONTAINER),
    };
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

  getKeyToTableColumnsMap() {
    const { CLUSTER, POD, WORKLOAD_TYPE, WORKLOAD, NAMESPACE, CONTAINER, CPU, INTERNAL_MEMORY } =
      K8sTableColumnKeysEnum;
    return {
      [CLUSTER]: {
        id: CLUSTER,
        name: this.$t('cluster'),
        sortable: false,
        type: 'scoped_slots',
        width: null,
        min_width: 90,
        showOverflowTooltip: false,
      },
      [POD]: {
        id: POD,
        name: this.$t('Pod'),
        sortable: false,
        type: 'scoped_slots',
        width: null,
        min_width: 260,
        k8s_filter: this.isListTab,
        showOverflowTooltip: false,
      },
      [WORKLOAD_TYPE]: {
        id: WORKLOAD_TYPE,
        name: this.$t('workload_type'),
        sortable: false,
        type: 'scoped_slots',
        width: null,
        min_width: 120,
        showOverflowTooltip: false,
      },
      [WORKLOAD]: {
        id: WORKLOAD,
        name: this.$t('workload'),
        sortable: false,
        type: 'scoped_slots',
        width: null,
        min_width: 260,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
        showOverflowTooltip: false,
      },
      [NAMESPACE]: {
        id: NAMESPACE,
        name: this.$t('namespace'),
        sortable: false,
        type: 'scoped_slots',
        width: null,
        min_width: 100,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
        showOverflowTooltip: false,
      },
      [CONTAINER]: {
        id: CONTAINER,
        name: this.$t('container'),
        sortable: false,
        type: 'scoped_slots',
        width: null,
        min_width: 120,
        showOverflowTooltip: false,
      },
      [CPU]: {
        id: CPU,
        name: this.$t('CPU使用率'),
        sortable: 'custom',
        type: 'datapoints',
        width: null,
        min_width: 180,
        asyncable: true,
      },
      [INTERNAL_MEMORY]: {
        id: INTERNAL_MEMORY,
        name: this.$t('内存使用率'),
        sortable: 'custom',
        type: 'datapoints',
        width: null,
        min_width: 180,
        asyncable: true,
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
    const id = K8sTableNew.getScopedSlotRowId(row, column.id);
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
   * @description 表格作用域插槽渲染方法
   * @param {K8sTableColumnKeysEnum} columnKey
   */
  scopedSlotFormatter(columnKey: K8sTableColumnKeysEnum) {
    return (row: K8sTableRow, column: K8sTableColumn) => {
      const text = K8sTableNew.getScopedSlotRowText(row, columnKey);
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

  render() {
    return (
      <div class='k8s-table-new'>
        <CommonTable
          style={{ display: !this.loading ? 'block' : 'none' }}
          height='100%'
          checkable={false}
          columns={this.tableColumns}
          data={this.tableData}
          defaultSize='small'
          hasColumnSetting={false}
          pagination={null}
          scopedSlots={this.tableScopedSlots}
          scrollLoading={this.scrollLoading}
          onScrollEnd={this.scrollEnd}
          onSortChange={val => this.handleSortChange(val as K8sTableSort)}
        >
          <EmptyStatus
            slot='empty'
            textMap={{
              empty: this.$t('暂无数据'),
            }}
            type={this.groupFilters?.length || this.filterBy?.length ? 'search-empty' : 'empty'}
            onOperation={() => this.handleClearSearch()}
          />
        </CommonTable>
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
