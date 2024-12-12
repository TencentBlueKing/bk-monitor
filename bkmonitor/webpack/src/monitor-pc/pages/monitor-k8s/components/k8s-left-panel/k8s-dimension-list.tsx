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

import { K8sDimension } from '../../k8s-dimension';
import { EDimensionKey, type GroupListItem, type SceneEnum } from '../../typings/k8s-new';
import GroupItem from './group-item';

// import type { GroupListItem } from '../../typings/k8s-new';
import type { TimeRangeType } from '../../../../components/time-range/time-range';

import './k8s-dimension-list.scss';

interface K8sDimensionListProps {
  scene: SceneEnum;
  filterBy: any;
  groupBy: string[];
  clusterId: string;
}

interface K8sDimensionListEvents {
  onFilterByChange: (val: { ids: string[]; groupId: string }) => void;
  onDrillDown: (val: { filterBy: { key: string; value: string[] }; groupId: string }) => void;
  onGroupByChange: (val: { groupId: string; isSelect: boolean }) => void;
}

@Component
export default class K8sDimensionList extends tsc<K8sDimensionListProps, K8sDimensionListEvents> {
  @Prop({ type: Array, default: () => [] }) filterBy: any;
  @Prop({ type: String }) scene: SceneEnum;
  @Prop({ type: String, required: true }) clusterId: string;
  @Prop({ type: Array, default: () => [] }) groupBy: string[];
  @InjectReactive('formatTimeRange') readonly formatTimeRange!: TimeRangeType;
  @InjectReactive('timezone') readonly timezone!: string;
  @InjectReactive('refleshInterval') readonly refreshInterval!: number;
  @InjectReactive('refleshImmediate') readonly refreshImmediate!: string;

  dimensionList = [];
  /** 搜索 */
  searchValue = '';
  /** 已选择filterBy列表 */
  showDimensionList: GroupListItem[] = [];
  /** 已选择的groupBy列表 */
  groupByList = [];
  /** 已选择的检索 */
  localFilterBy = {};
  /** 下钻弹窗列表 */
  drillDownList = [];

  /** 一级维度列表初始化loading */
  loading = true;
  /** 展开loading */
  expandLoading = {};
  /** 加载更多loading */
  loadMoreLoading = {};

  @Watch('scene')
  handleSceneChange() {
    this.init();
  }

  @Watch('clusterId')
  handleClusterIdChange() {
    this.init();
  }

  @Watch('refreshInterval')
  handleRefleshIntervalChange() {
    this.init();
  }

  @Watch('refreshImmediate')
  handleRefleshImmediateChange() {
    this.init();
  }

  @Watch('formatTimeRange')
  handleFormatTimeRangeChange() {
    this.init();
  }

  async init() {
    if (!this.clusterId) return;
    const dimension = new K8sDimension({
      scene: this.scene,
      keyword: this.searchValue,
      bcsClusterId: this.clusterId,
      pageType: 'scrolling',
    });
    (this as any).dimension = dimension;
    this.loading = true;
    await dimension.init({
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    });
    this.loading = false;
    this.showDimensionList = dimension.showDimensionData;
    this.initLoading(this.showDimensionList);
    this.localFilterBy = dimension.currentDimension.reduce((pre, cur) => {
      pre[cur] = [];
      return pre;
    }, {});
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

  @Watch('filterBy', { immediate: true })
  handleFilterByChange(val: K8sDimensionListProps['filterBy']) {
    if (val.length) {
      val.map(item => {
        this.localFilterBy[item.key] = item.value;
      });
    } else {
      Object.keys(this.localFilterBy).map(key => {
        this.localFilterBy[key] = [];
      });
    }
  }

  @Watch('groupBy', { immediate: true })
  watchGroupByChange(val: string[]) {
    this.groupByList = val;
  }

  /** 搜索 */
  async handleSearch(val: string) {
    this.searchValue = val;
    this.loading = true;
    await (this as any).dimension.search(val, {
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    });
    this.showDimensionList = (this as any).dimension.showDimensionData;
    this.loading = false;
  }

  /** 检索 */
  @Emit('filterByChange')
  handleGroupSearch(ids: string[], groupId: string) {
    return {
      ids,
      groupId,
    };
  }

  /** 下钻 */
  @Emit('drillDown')
  handleDrillDown({ id, dimension }, groupId: string) {
    const ids = [...(this.localFilterBy[groupId] || [])];
    if (!ids.includes(id)) {
      ids.push(id);
    }
    return {
      filterBy: {
        key: groupId,
        value: ids,
      },
      groupId: dimension,
    };
  }

  /** 修改groupBy */
  @Emit('groupByChange')
  handleGroupByChange(val: boolean, groupId: string) {
    return {
      groupId,
      isSelect: val,
    };
  }

  /** 首次展开workload的二级菜单后，请求数据 */
  async handleFirstExpand(dimension, fatherDimension) {
    if (fatherDimension === EDimensionKey.workload && dimension !== fatherDimension) {
      this.expandLoading[dimension] = true;
      await (this as any).dimension.getWorkloadChildrenData({
        filter_dict: {
          workload: `${dimension}:`,
        },
        start_time: this.formatTimeRange[0],
        end_time: this.formatTimeRange[1],
      });
      this.showDimensionList = (this as any).dimension.showDimensionData;
      this.expandLoading[dimension] = false;
    }
  }

  /** 加载更多 */
  async handleMoreClick(dimension, fatherDimension) {
    this.loadMoreLoading[dimension] = true;
    await (this as any).dimension.loadNextPageData(
      dimension,
      {
        start_time: this.formatTimeRange[0],
        end_time: this.formatTimeRange[1],
      },
      fatherDimension
    );
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
                  isGroupBy={this.groupByList.includes(group.id)}
                  list={group}
                  loadMoreLoading={this.loadMoreLoading}
                  value={this.localFilterBy[group.id]}
                  onFirstExpand={dimension => this.handleFirstExpand(dimension, group.id)}
                  onHandleDrillDown={val => this.handleDrillDown(val, group.id)}
                  onHandleGroupByChange={val => this.handleGroupByChange(val, group.id)}
                  onHandleMoreClick={dimension => this.handleMoreClick(dimension, group.id)}
                  onHandleSearch={val => this.handleGroupSearch(val, group.id)}
                />
              ))}
        </div>
      </div>
    );
  }
}
