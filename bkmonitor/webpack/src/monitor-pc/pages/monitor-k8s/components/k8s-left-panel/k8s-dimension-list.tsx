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
import { K8sPerformanceDimension } from '../../k8s-dimension';
import { EDimensionKey, type ICommonParams, type GroupListItem } from '../../typings/k8s-new';
import GroupItem from './group-item';

import type { EmptyStatusOperationType } from '../../../../components/empty-status/types';

import './k8s-dimension-list.scss';

interface K8sDimensionListProps {
  groupBy: string[];
  filterBy: Record<string, string[]>;
  commonParams: ICommonParams;
}

interface K8sDimensionListEvents {
  onFilterByChange: (id: string, dimensionId: string, isSelect: boolean) => void;
  onDrillDown: (filterById: string, filterByDimension: string, drillDownDimension: string) => void;
  onGroupByChange: (groupId: string, isSelect: boolean) => void;
  onClearFilterBy: (dimensionId: string) => void;
  onDimensionTotal: (val: Record<string, number>) => void;
}

@Component
export default class K8sDimensionList extends tsc<K8sDimensionListProps, K8sDimensionListEvents> {
  @Prop({ type: Object, required: true }) commonParams: ICommonParams;
  @Prop({ type: Array, default: () => [] }) groupBy: string[];
  @Prop({ type: Array, default: () => ({}) }) filterBy: string[];
  @InjectReactive('timezone') readonly timezone!: string;
  @InjectReactive('refleshInterval') readonly refreshInterval!: number;
  @InjectReactive('refleshImmediate') readonly refreshImmediate!: string;

  dimensionList = [];
  /** 搜索 */
  searchValue = '';
  /** 已选择filterBy列表 */
  showDimensionList: GroupListItem[] = [];
  /** 下钻弹窗列表 */
  drillDownList = [];

  /** 一级维度列表初始化loading */
  loading = false;
  /** 展开loading */
  expandLoading = {};
  /** 加载更多loading */
  loadMoreLoading = {};

  get localCommonParams() {
    return {
      ...this.commonParams,
      filter_dict: {},
    };
  }

  get dimensionTotal() {
    return this.showDimensionList.reduce((pre, cur) => {
      pre[cur.id] = cur.count;
      return pre;
    }, {});
  }

  @Watch('localCommonParams')
  handleCommonParamsChange() {
    this.init();
  }

  @Watch('refreshImmediate')
  handleRefreshImmediateChange() {
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
    const dimension = new K8sPerformanceDimension({
      ...this.localCommonParams,
      keyword: this.searchValue,
      pageSize: 5,
      page_type: 'scrolling',
    });
    (this as any).dimension = dimension;
    this.loading = true;
    await dimension.init();
    this.loading = false;
    this.showDimensionList = dimension.showDimensionData;
    this.initLoading(this.showDimensionList);
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
  }

  /** 检索 */
  @Emit('filterByChange')
  handleGroupSearch({ id, isSelect }, dimension: EDimensionKey) {
    if (dimension === EDimensionKey.workload) {
      this.handleClear(dimension);
    }
    this.$emit('filterByChange', id, dimension, isSelect);
  }

  /**
   * 下钻
   * @param param0  下钻id 和下钻维度
   * @param drillDownId
   */
  handleDrillDown({ id, drillDownDimension }, dimension: string) {
    this.$emit('drillDown', id, dimension, drillDownDimension);
  }

  /** 修改groupBy */
  handleGroupByChange(isSelect: boolean, groupId: string) {
    this.$emit('groupByChange', groupId, isSelect);
  }

  /** 首次展开workload的二级菜单后，请求数据 */
  async handleFirstExpand(dimension, parentDimension) {
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
  async handleMoreClick(dimension, parentDimension) {
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

  render() {
    return (
      <div class='k8s-dimension-list'>
        <div class='panel-title'>{this.$t('K8s对象')}</div>
        <bk-input
          class='left-panel-search'
          v-model={this.searchValue}
          right-icon='bk-icon icon-search'
          show-clear-only-hover={true}
          clearable
          on-enter={this.handleSearch}
          on-right-icon-click={this.handleSearch}
        />

        <div class='object-group'>
          {this.loading
            ? [this.renderGroupSkeleton(), this.renderGroupSkeleton()]
            : this.showDimensionList.map((group, index) => (
                <GroupItem
                  key={group.id}
                  defaultExpand={index === 0}
                  drillDownList={this.drillDownList}
                  expandLoading={this.expandLoading}
                  isGroupBy={this.groupBy.includes(group.id)}
                  list={group}
                  loadMoreLoading={this.loadMoreLoading}
                  tools={['clear', 'drillDown', 'search', group.id !== EDimensionKey.namespace ? 'groupBy' : '']}
                  value={this.filterBy[group.id]}
                  onClear={() => this.handleClear(group.id)}
                  onFirstExpand={dimension => this.handleFirstExpand(dimension, group.id)}
                  onHandleDrillDown={val => this.handleDrillDown(val, group.id)}
                  onHandleGroupByChange={val => this.handleGroupByChange(val, group.id)}
                  onHandleMoreClick={dimension => this.handleMoreClick(dimension, group.id)}
                  onHandleSearch={val => this.handleGroupSearch(val, group.id)}
                >
                  <EmptyStatus
                    slot='empty'
                    type={this.searchValue ? 'search-empty' : 'empty'}
                    onOperation={this.handleEmptyOperation}
                  />
                </GroupItem>
              ))}
        </div>
      </div>
    );
  }
}