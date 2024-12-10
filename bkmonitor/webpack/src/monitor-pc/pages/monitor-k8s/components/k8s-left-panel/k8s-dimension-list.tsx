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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import GroupItem from './group-item';

// import type { GroupListItem } from '../../typings/k8s-new';

import { K8sDimension } from '../../k8s-dimension';

import type { EDimensionKey, GroupListItem, SceneType } from '../../typings/k8s-new';

import './k8s-dimension-list.scss';

interface K8sDimensionListProps {
  scene: SceneType;
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
  @Prop({ type: String }) scene: SceneType;
  @Prop({ type: String, required: true }) clusterId: string;
  @Prop({ type: Array, default: () => [] }) groupBy: string[];

  dimensionList = [];
  /** 搜索 */
  searchValue = '';
  /** 已选择filterBy列表 */
  showDimensionList: GroupListItem[] = [];
  /** 已选择的groupBy列表 */
  groupByList = [];
  /** 已选择的检索 */
  selectData = {};
  /** 下钻弹窗列表 */
  drillDownList = [];

  loading = true;

  @Watch('scene')
  handleSceneChange() {
    this.init();
  }

  @Watch('clusterId')
  handleClusterIdChange() {
    this.init();
  }

  async init() {
    const dimension = new K8sDimension({
      scene: this.scene,
      keyword: this.searchValue,
      bcsClusterId: this.clusterId,
      pageType: 'scrolling',
    });
    (this as any).dimension = dimension;
    this.loading = true;
    await dimension.init();
    this.loading = false;
    this.showDimensionList = dimension.showDimensionData;
    this.selectData = dimension.currentDimension.reduce((pre, cur) => {
      pre[cur] = [];
      return pre;
    }, {});
    console.log(dimension);
  }

  @Watch('filterBy', { immediate: true })
  handleFilterByChange(val: K8sDimensionListProps['filterBy']) {
    if (val.length) {
      val.map(item => {
        this.selectData[item.key] = item.value;
      });
    } else {
      Object.keys(this.selectData).map(key => {
        this.selectData[key] = [];
      });
    }
  }

  @Watch('groupBy', { immediate: true })
  watchGroupByChange(val: string[]) {
    this.groupByList = val;
  }

  handleSearch(val: string) {
    this.searchValue = val;
    (this as any).dimension.search(val);
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
    const ids = [...(this.selectData[groupId] || [])];
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

  /** 加载更多 */
  handleMoreClick(dimension: EDimensionKey) {
    (this as any).dimension.loadMore(dimension);
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
          right-icon='bk-icon icon-search'
          show-clear-only-hover={true}
          value={this.searchValue}
          clearable
          onChange={this.handleSearch}
        />

        <div class='object-group'>
          {this.loading
            ? [this.renderGroupSkeleton(), this.renderGroupSkeleton()]
            : this.showDimensionList.map((group, index) => (
                <GroupItem
                  key={group.id}
                  defaultExpand={index === 0}
                  drillDownList={this.drillDownList}
                  isGroupBy={this.groupByList.includes(group.id)}
                  list={group}
                  value={this.selectData[group.id]}
                  onHandleDrillDown={val => this.handleDrillDown(val, group.id)}
                  onHandleGroupByChange={val => this.handleGroupByChange(val, group.id)}
                  onHandleMoreClick={() => this.handleMoreClick(group.id)}
                  onHandleSearch={val => this.handleGroupSearch(val, group.id)}
                />
              ))}
        </div>
      </div>
    );
  }
}
