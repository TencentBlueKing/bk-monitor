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

import type { GroupListItem, SceneType } from '../../typings/k8s-new';

import './k8s-dimension-list.scss';

interface K8sDimensionListProps {
  scene: SceneType;
  filterBy: any;
  groupBy: string[];
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
  /** 需要加载更多按钮的组 */
  showMoreGroup = [];

  async created() {
    const dimension = new K8sDimension({
      scene: this.scene,
      keyword: this.searchValue,
    });
    (this as any).dimension = dimension;
    await dimension.init();
    this.showDimensionList = dimension.showDimensionData;
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

  // handleSearch(val: string) {
  //   this.searchValue = val;
  //   const groupList = JSON.parse(JSON.stringify(this.groupList));
  //   if (!val) {
  //     this.showDimensionList = groupList;
  //     return;
  //   }
  //   this.showDimensionList = groupList.filter(item => {
  //     item.children = item.children.filter(child => {
  //       if (child.title.toLowerCase().includes(this.searchValue.toLowerCase())) {
  //         return true;
  //       }
  //       if (child.children) {
  //         child.children = child.children.filter(grandChild => {
  //           const title = grandChild.title.toLowerCase();
  //           return title.includes(this.searchValue.toLowerCase());
  //         });
  //         return child.children.length;
  //       }
  //     });
  //     return item.children.length;
  //   });
  // }

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
  // handleMoreClick(id: string) {
  //   const filterGroup = this.showDimensionList.find(item => item.id === id);
  //   const group = this.groupList.find(item => item.id === id);
  //   filterGroup.children = group.children.slice(0, filterGroup.children.length + 5);
  //   this.showDimensionList = [...this.showDimensionList];
  //   if (group.children.length === filterGroup.children.length) {
  //     this.showMoreGroup = this.showMoreGroup.filter(item => item !== id);
  //   }
  // }

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
          // onChange={this.handleSearch}
        />

        <div class='object-group'>
          {this.showDimensionList.map((group, index) => (
            <GroupItem
              key={group.id}
              defaultExpand={index === 0}
              drillDownList={this.drillDownList}
              isGroupBy={this.groupByList.includes(group.id)}
              list={group}
              showMore={!this.searchValue && this.showMoreGroup.includes(group.id)}
              value={this.selectData[group.id]}
              onHandleDrillDown={val => this.handleDrillDown(val, group.id)}
              onHandleGroupByChange={val => this.handleGroupByChange(val, group.id)}
              onHandleSearch={val => this.handleGroupSearch(val, group.id)}
            />
          ))}
        </div>
      </div>
    );
  }
}
