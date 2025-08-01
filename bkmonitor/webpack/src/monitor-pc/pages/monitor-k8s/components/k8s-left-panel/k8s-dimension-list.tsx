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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import { K8sDimension } from '../../k8s-dimension';
import { type GroupListItem, type ICommonParams, EDimensionKey } from '../../typings/k8s-new';
import GroupItem from './group-item';

import type { EmptyStatusOperationType } from '../../../../components/empty-status/types';
import type { K8sTableGroupByEvent } from '../k8s-table-new/k8s-table-new';

import './k8s-dimension-list.scss';

interface K8sDimensionListEvents {
  onClearFilterBy: (dimensionId: string) => void;
  onDimensionTotal: (val: Record<string, number>) => void;
  onDrillDown: (item: K8sTableGroupByEvent, showCancelDrill?: boolean) => void;
  onFilterByChange: (id: string, dimensionId: string, isSelect: boolean) => void;
  onGroupByChange: (groupId: string, isSelect: boolean) => void;
}

interface K8sDimensionListProps {
  commonParams: ICommonParams;
  filterBy: Record<string, string[]>;
  groupBy: string[];
}

@Component
export default class K8sDimensionList extends tsc<K8sDimensionListProps, K8sDimensionListEvents> {
  @InjectReactive('refleshImmediate') refreshImmediate;

  @Prop({ type: Object, required: true }) commonParams: ICommonParams;
  @Prop({ type: Array, default: () => [] }) groupBy: string[];
  @Prop({ type: Object, default: () => ({}) }) filterBy: Record<string, string[]>;
  // 数据时间间隔

  dimensionList = [];
  cacheSearchValue = '';
  /** 搜索 */
  searchValue = '';
  /** 已选择filterBy列表 */
  showDimensionList: GroupListItem<EDimensionKey>[] = [];
  /** 下钻弹窗列表 */
  drillDownList = [];

  /** 一级维度列表初始化loading */
  loading = false;
  /** 展开loading */
  expandLoading = {};
  /** 加载更多loading */
  loadMoreLoading = {};

  initCount = 0;

  get localCommonParams() {
    return {
      ...this.commonParams,
      filter_dict: {},
    };
  }

  /** 各维度总数据 */
  get dimensionTotal() {
    return this.showDimensionList.reduce((pre, cur) => {
      pre[cur.id] = cur.count;
      return pre;
    }, {});
  }

  get groupItemDefaultExpandIndexSet() {
    const set = new Set();
    for (const item of this.showDimensionList) {
      if (item.count && this.searchValue) {
        set.add(item.id);
      } else if (this.groupBy.includes(item.id)) {
        set.add(item.id);
      }
    }
    return set;
  }

  @Watch('refreshImmediate')
  handleRefreshImmediateChange() {
    this.init();
  }

  @Watch('localCommonParams')
  handleCommonParamsChange() {
    this.init();
  }

  @Watch('dimensionTotal')
  handleDimensionTotalChange() {
    this.$emit('dimensionTotal', this.dimensionTotal);
  }

  mounted() {
    this.init();
  }

  async init() {
    if (!this.localCommonParams.bcs_cluster_id) return;
    this.initCount += 1;
    const cacheInitCount = this.initCount;
    const dimension = new K8sDimension({
      ...this.localCommonParams,
      query_string: this.searchValue,
      page_size: 5,
      page_type: 'scrolling',
    });
    (this as any).dimension = dimension;
    this.loading = true;
    await dimension.init();
    this.loading = false;
    // 因为这里接口会比较多，且请求时间不一致，需要通过变量确保接口顺序一致
    if (cacheInitCount === this.initCount) {
      this.showDimensionList = dimension.showDimensionData;
      this.initLoading(this.showDimensionList);
    }
  }

  initLoading(data: GroupListItem[]) {
    for (const item of data) {
      if (item.children) {
        this.$set(this.expandLoading, item.id, false);
        this.$set(this.loadMoreLoading, item.id, false);
        this.initLoading(item.children);
      }
    }
  }

  /** 搜索 */
  async handleSearch(val: string) {
    this.searchValue = val;
    this.loading = true;
    await (this as any).dimension.search(val);
    this.showDimensionList = (this as any).dimension.showDimensionData;
    this.loading = false;
    this.cacheSearchValue = this.searchValue;
  }

  handleBlur(val: string) {
    if (val === this.cacheSearchValue) return;
    this.handleSearch(val);
  }

  /** 检索 */
  handleGroupSearch({ id, isSelect }, dimension: EDimensionKey) {
    this.$emit('filterByChange', id, dimension, isSelect);
  }

  handleItemClick(id, dimension: EDimensionKey) {
    if (this.filterBy[dimension].includes(id)) return;
    this.handleGroupSearch(
      {
        id,
        isSelect: true,
      },
      dimension
    );
  }

  /**
   * 下钻
   * @param param0  下钻id 和下钻维度
   * @param drillDownId 下钻数据所在维度
   */
  handleDrillDown({ id, drillDownDimension }, dimension: string) {
    this.$emit(
      'drillDown',
      {
        id: dimension,
        filterById: id,
        dimension: drillDownDimension,
      },
      true
    );
  }

  /** 修改groupBy */
  handleGroupByChange(isSelect: boolean, groupId: string) {
    this.$emit('groupByChange', groupId, isSelect);
  }

  /** 首次展开workload的二级菜单后，请求数据 */
  async handleFirstExpand(dimension: string, parentDimension: EDimensionKey) {
    if (parentDimension === EDimensionKey.workload && dimension !== parentDimension) {
      this.expandLoading[dimension] = true;
      await (this as any).dimension.getWorkloadChildrenData({
        filter_dict: {
          workload: `${dimension}:`,
        },
      });
      this.showDimensionList = (this as any).dimension.showDimensionData;
      this.expandLoading[dimension] = false;
    }
  }

  /** 加载更多 */
  async handleMoreClick(dimension: string, parentDimension: EDimensionKey) {
    /** 没有更多数据后，不进行接口请求 */
    let oldDimensionData = this.showDimensionList.find(item => item.id === parentDimension);
    if (parentDimension === EDimensionKey.workload) {
      // workload 需要获取下级类目进行判断
      oldDimensionData = oldDimensionData.children.find(item => item.id === dimension);
    }
    if (!oldDimensionData.showMore) return;
    this.loadMoreLoading[dimension] = true;
    await (this as any).dimension.loadNextPageData([parentDimension, dimension]);
    this.showDimensionList = (this as any).dimension.showDimensionData;
    this.loadMoreLoading[dimension] = false;
  }

  /** 渲染骨架屏 */
  renderGroupSkeleton() {
    return (
      <div class='skeleton-element-group'>
        <div class='skeleton-element group-title' />
        <div class='skeleton-element group-content' />
        <div class='skeleton-element group-content' />
        <div class='skeleton-element group-content' />
      </div>
    );
  }

  handleEmptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.handleSearch('');
    }
  }

  @Emit('clearFilterBy')
  handleClear(dimension: string) {
    return dimension;
  }

  renderContent() {
    if (this.loading) return [this.renderGroupSkeleton(), this.renderGroupSkeleton()];

    const total = Object.keys(this.dimensionTotal).reduce((pre, cur) => {
      return pre + this.dimensionTotal[cur];
    }, 0);

    if (total === 0)
      return (
        <EmptyStatus
          type={this.searchValue ? 'search-empty' : 'empty'}
          onOperation={this.handleEmptyOperation}
        />
      );
    return this.showDimensionList.map(group => (
      <GroupItem
        key={group.id}
        defaultExpand={this.groupItemDefaultExpandIndexSet.has(group.id)}
        drillDownList={this.drillDownList}
        expandLoading={this.expandLoading}
        isGroupBy={this.groupBy.includes(group.id)}
        keyword={this.searchValue}
        list={group}
        loadMoreLoading={this.loadMoreLoading}
        tools={['clear', 'drillDown', 'search', group.id !== EDimensionKey.namespace ? 'groupBy' : '']}
        value={this.filterBy[group.id]}
        onClear={() => this.handleClear(group.id)}
        onFirstExpand={dimension => this.handleFirstExpand(dimension, group.id)}
        onHandleDrillDown={val => this.handleDrillDown(val, group.id)}
        onHandleGroupByChange={val => this.handleGroupByChange(val, group.id)}
        onHandleItemClick={val => this.handleItemClick(val, group.id)}
        onHandleMoreClick={dimension => this.handleMoreClick(dimension, group.id)}
        onHandleSearch={val => this.handleGroupSearch(val, group.id)}
      />
    ));
  }

  render() {
    return (
      <div class='k8s-dimension-list'>
        <div class='panel-title'>{this.$t('K8S对象')}</div>
        <bk-input
          class='left-panel-search'
          placeholder={this.$tc('请输入关键字')}
          right-icon='bk-icon icon-search'
          show-clear-only-hover={true}
          value={this.searchValue}
          clearable
          on-blur={this.handleBlur}
          on-clear={this.handleSearch}
          on-enter={this.handleSearch}
          on-right-icon-click={this.handleSearch}
        />

        <div class='object-group'>{this.renderContent()}</div>
      </div>
    );
  }
}
