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

import EmptyStatus from '../../../../components/empty-status/empty-status';
import K8sDimensionDrillDown from './k8s-dimension-drilldown';

import type { GroupListItem } from '../../typings/k8s-new';

import './group-item.scss';

type Tools = 'clear' | 'drillDown' | 'groupBy' | 'search' | 'view';

interface GroupItemProps {
  list: GroupListItem;
  value?: string[];
  isGroupBy?: boolean;
  tools?: Tools[];
  hiddenList?: string[];
  defaultExpand?: { [key: string]: boolean } | boolean;
  drillDownList?: string[];
}

interface GroupItemEvent {
  onHandleSearch: (ids: string[]) => void;
  onHandleDrillDown: (val: { id: number | string; dimension: string }) => void;
  onHandleGroupByChange: (val: boolean) => void;
  onHandleMoreClick: () => void;
  onHandleHiddenChange: (ids: string[]) => void;
}

@Component
export default class GroupItem extends tsc<GroupItemProps, GroupItemEvent> {
  @Prop({ default: () => ({}) }) list: GroupListItem;
  /** 检索 */
  @Prop({ default: () => [] }) value: string[];
  /** 是否选择group By */
  @Prop({ default: false }) isGroupBy: boolean;
  /** 隐藏项列表 */
  @Prop({ default: () => [] }) hiddenList: string[];
  @Prop({ default: () => ['clear', 'drillDown', 'groupBy', 'search'] }) tools: Tools[];
  @Prop({ default: false }) defaultExpand: GroupItemProps['defaultExpand'];
  @Prop({ default: () => [] }) drillDownList: string[];

  /** 展开的组  */
  expand = {};

  drillDown = '';

  get showMoreGroup() {
    const group = [];
    if (this.list.children.length) {
      if (this.list.children[0].children) {
        for (const item of this.list.children) {
          if (item.children?.length && item.count > item.children.length) group.push(item.id);
        }
      } else {
        if (this.list.count > this.list.children.length) group.push(this.list.id);
      }
    }
    return group;
  }

  @Watch('defaultExpand', { immediate: true })
  handleDefaultExpandChange(val: GroupItemProps['defaultExpand']) {
    if (typeof val === 'boolean') {
      this.expand = {
        [this.list.id]: val,
      };
    } else {
      this.expand = val;
    }
  }

  collapseChange(id: string) {
    this.$set(this.expand, id, !this.expand[id]);
  }

  handleClear(e: Event) {
    e.stopPropagation();
    this.handleSearch();
  }

  @Emit('handleSearch')
  handleSearch(id?: string) {
    if (id) {
      const res = this.value.includes(id);
      return res ? this.value.filter(item => item !== id) : [...this.value, id];
    }
    return [];
  }

  /** 下钻 */
  @Emit('handleDrillDown')
  handleDrillDownChange(val) {
    return val;
  }

  @Emit('handleGroupByChange')
  handleGroupByChange(e: Event) {
    e.stopPropagation();
    return !this.isGroupBy;
  }

  @Emit('handleMoreClick')
  handleShowMore() {}

  @Emit('handleHiddenChange')
  handleHiddenChange(id: string) {
    const res = this.hiddenList.includes(id);
    return res ? this.hiddenList.filter(item => item !== id) : [...this.hiddenList, id];
  }

  renderGroupContent(item: GroupListItem) {
    const isSelectSearch = this.value.includes(item.id);
    const isHidden = this.hiddenList.includes(item.id);

    if (item.children) {
      return (
        <div class='child-content'>
          <div
            class='child-header'
            onClick={() => this.collapseChange(item.id)}
          >
            <i class={`icon-monitor arrow-icon icon-arrow-right ${this.expand[item.id] ? 'expand' : ''}`} />
            <span class='group-name'>{item.name}</span>
            <div class='group-count'>{item.count}</div>
          </div>

          {this.expand[item.id] && item.children.map(child => this.renderGroupContent(child))}
          {this.showMoreGroup.includes(item.id) && this.expand[item.id] && (
            <div class='show-more'>
              <span
                class='text'
                onClick={this.handleShowMore}
              >
                {this.$t('点击加载更多')}
              </span>
            </div>
          )}
        </div>
      );
    }

    return (
      <div
        key={item.id}
        class='group-content-item'
      >
        <span
          class='content-name'
          v-bk-overflow-tips
        >
          {item.name}
        </span>
        <div class='tools'>
          {this.tools.includes('search') && (
            <i
              class={`icon-monitor ${isSelectSearch ? 'icon-sousuo-' : 'icon-a-sousuo'}`}
              v-bk-tooltips={{ content: this.$t(isSelectSearch ? '移除该筛选项' : '添加为筛选项') }}
              onClick={() => this.handleSearch(item.id)}
            />
          )}
          {this.tools.includes('drillDown') && (
            <K8sDimensionDrillDown
              dimension={this.list.id}
              value={item.id}
              onHandleDrillDown={this.handleDrillDownChange}
            />
          )}
          {this.tools.includes('view') && (
            <i
              class={`icon-monitor view-icon ${isHidden ? 'icon-mc-invisible' : 'icon-mc-visual'}`}
              v-bk-tooltips={{ content: this.$t(isHidden ? '点击显示该指标' : '点击隐藏该指标') }}
              onClick={() => this.handleHiddenChange(item.id)}
            />
          )}
        </div>
      </div>
    );
  }

  render() {
    return (
      <div class='k8s-new___group-item'>
        <div
          class='group-header'
          onClick={() => this.collapseChange(this.list.id)}
        >
          <div class='group-header-left'>
            <i class={`icon-monitor arrow-icon icon-arrow-right ${this.expand[this.list.id] ? 'expand' : ''}`} />
            <span class='group-name'>{this.list.name}</span>
            <div class='group-count'>{this.list.count}</div>
            {this.value.length > 0 && this.tools.includes('clear') && (
              <div
                class='clear-filter-icon'
                v-bk-tooltips={{ content: this.$t('清空整组筛选项') }}
                onClick={this.handleClear}
              />
            )}
          </div>
          {this.tools.includes('groupBy') && (
            <div
              class='group-select'
              onClick={this.handleGroupByChange}
            >
              {this.isGroupBy ? 'ungroup' : 'Group'}
            </div>
          )}
        </div>
        <div
          style={{ display: this.expand[this.list.id] ? 'block' : 'none' }}
          class='group-content'
        >
          {this.list.children.length > 0 ? (
            this.list.children.map(child => this.renderGroupContent(child))
          ) : (
            <EmptyStatus type='empty' />
          )}

          {this.showMoreGroup.includes(this.list.id) && (
            <div class='show-more'>
              <span
                class='text'
                onClick={this.handleShowMore}
              >
                {this.$t('点击加载更多')}
              </span>
            </div>
          )}
        </div>
      </div>
    );
  }
}
