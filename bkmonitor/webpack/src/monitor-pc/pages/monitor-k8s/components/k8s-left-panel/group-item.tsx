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

import K8sDimensionDrillDown from 'monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-dimension-drilldown';

import type { GroupListItem } from '../../typings/k8s-new';

import './group-item.scss';

interface GroupItemEvent {
  onClear: () => void;
  onFirstExpand: (id: string) => void;
  onHandleDrillDown: (val: { drillDownDimension: string; id: string }) => void;
  onHandleGroupByChange: (val: boolean) => void;
  onHandleHiddenChange: (ids: string[]) => void;
  onHandleItemClick: (id: string) => void;
  onHandleMoreClick: (dimension: string) => void;
  onHandleSearch: (val: { id: string; isSelect: boolean }) => void;
}

interface GroupItemProps {
  activeMetric?: string;
  defaultExpand?: boolean | { [key: string]: boolean };
  disabledList?: { id: string; tooltips: string }[];
  drillDownList?: string[];
  expandLoading?: Record<string, boolean>;
  hiddenList?: string[];
  isGroupBy?: boolean;
  keyword?: string;
  list: GroupListItem;
  loadMoreLoading?: Record<string, boolean>;
  tools?: Tools[];
  value?: string[];
}

type Tools = '' | 'clear' | 'drillDown' | 'groupBy' | 'search' | 'view';

@Component
export default class GroupItem extends tsc<GroupItemProps, GroupItemEvent> {
  @Prop({ default: () => ({}) }) list: GroupListItem;
  /** 检索 */
  @Prop({ default: () => [] }) value: string[];
  /** 是否选择group By */
  @Prop({ default: false }) isGroupBy: boolean;
  /** 隐藏项列表 */
  @Prop({ default: () => [] }) hiddenList: string[];
  @Prop({ default: () => [] }) disabledList: GroupItemProps['disabledList'];
  @Prop({ default: () => ['clear', 'drillDown', 'groupBy', 'search'] }) tools: Tools[];
  @Prop({ default: false }) defaultExpand: GroupItemProps['defaultExpand'];
  @Prop({ default: () => [] }) drillDownList: string[];
  @Prop({ default: () => ({}) }) expandLoading: Record<string, boolean>;
  @Prop({ default: () => ({}) }) loadMoreLoading: Record<string, boolean>;
  @Prop({ default: '' }) activeMetric: string;
  @Prop({ default: '' }) keyword: string;

  /** 展开的组  */
  expand = {};

  drillDown = '';

  @Watch('defaultExpand', { immediate: true })
  handleDefaultExpandChange(val: GroupItemProps['defaultExpand']) {
    if (typeof val === 'boolean') {
      if (val === this.expand[this.list.id]) return;
      this.expand = {
        [this.list.id]: val,
      };
    } else {
      this.expand = val;
    }
  }

  collapseChange(id: string, hasData: boolean) {
    if (!Object.hasOwn(id) && !hasData) {
      this.firstExpand(id);
    }
    this.$set(this.expand, id, !this.expand[id]);
  }

  @Emit('firstExpand')
  firstExpand(id: string) {
    return id;
  }

  @Emit('clear')
  handleClear(e: Event) {
    e.stopPropagation();
  }

  @Emit('handleSearch')
  handleSearch(id: string, isSelect: boolean, e: Event) {
    e.stopPropagation();
    return {
      id,
      isSelect,
    };
  }

  /** 下钻 */
  @Emit('handleDrillDown')
  handleDrillDownChange(val) {
    return {
      id: val.id,
      drillDownDimension: val.dimension,
    };
  }

  @Emit('handleGroupByChange')
  handleGroupByChange(e: Event) {
    e.stopPropagation();
    return !this.isGroupBy;
  }

  @Emit('handleMoreClick')
  handleShowMore(dimension: string) {
    return dimension;
  }

  @Emit('handleHiddenChange')
  handleHiddenChange(id: string) {
    const res = this.hiddenList.includes(id);
    return res ? this.hiddenList.filter(item => item !== id) : [...this.hiddenList, id];
  }

  @Emit('handleItemClick')
  handleItemClick(id: string) {
    return id;
  }

  /** 渲染骨架屏 */
  renderGroupSkeleton() {
    return (
      <div class='skeleton-element-group'>
        <div class='skeleton-element group-content' />
        <div class='skeleton-element group-content' />
        <div class='skeleton-element group-content' />
      </div>
    );
  }

  renderLoadMore(id: string) {
    return (
      <div class='show-more'>
        <bk-spin
          style={{ display: this.loadMoreLoading[id] ? 'inline-block' : 'none' }}
          size='mini'
        />
        <div
          style={{ display: !this.loadMoreLoading[id] ? 'flex' : 'none' }}
          class='content'
          onClick={() => this.handleShowMore(id)}
        >
          <span class='dot' />
          <span class='dot' />
          <span class='dot' />
          <span class='text'>{this.$t('点击加载更多')}</span>
        </div>
      </div>
    );
  }

  renderGroupContent(item: GroupListItem) {
    if (!item.children?.length) return;
    return [
      item.children.map((child, ind) => {
        const isSelectSearch = this.value.includes(child.id);
        const isDisabled = this.disabledList.find(item => item.id === child.id);
        const isHidden = this.hiddenList.includes(child.id) || isDisabled;

        if (child.children) {
          return (
            <div class='child-item'>
              <div
                class='child-header'
                onClick={() => this.collapseChange(child.id, Boolean(child.children.length))}
              >
                <i class={`icon-monitor arrow-icon icon-mc-arrow-right ${this.expand[child.id] ? 'expand' : ''}`} />
                <span class='group-name'>{child.name}</span>
                <div class='group-count'>{child.count}</div>
              </div>
              <div
                style={{ display: this.expand[child.id] ? 'block' : 'none' }}
                class='group-content'
              >
                {this.expandLoading[child.id] ? this.renderGroupSkeleton() : this.renderGroupContent(child)}
              </div>
            </div>
          );
        }

        const keywordPick = this.keyword ? child.name.indexOf(this.keyword) : -1;
        return (
          <div
            key={`${child.id}-${ind}`}
            class={{
              'group-content-item': true,
              active: this.activeMetric === child.id,
              disabled: isDisabled,
            }}
            v-bk-tooltips={{
              content: isDisabled?.tooltips,
              disabled: !isDisabled,
              placements: ['top'],
              interactive: false,
            }}
          >
            <div
              class='content-name'
              onClick={() => !isDisabled && this.handleItemClick(child.id)}
            >
              <span
                class='name'
                v-bk-overflow-tips
              >
                {keywordPick > -1 ? (
                  <span>
                    <span>{child.name.slice(0, keywordPick)}</span>
                    <span class='pick-name'>{this.keyword}</span>
                    <span>{child.name.slice(keywordPick + this.keyword.length)}</span>
                  </span>
                ) : (
                  child.name
                )}
              </span>
            </div>
            <div class='tools'>
              {this.tools.includes('search') && (
                <i
                  class={`search-tools  ${isSelectSearch ? 'selected' : 'icon-monitor icon-a-sousuo'}`}
                  v-bk-tooltips={{
                    content: this.$t(isSelectSearch ? '移除该筛选项' : '添加为筛选项'),
                  }}
                  onClick={e => this.handleSearch(child.id, !isSelectSearch, e)}
                />
              )}
              {this.tools.includes('drillDown') && (
                <K8sDimensionDrillDown
                  dimension={this.list.id}
                  value={child.id}
                  onHandleDrillDown={this.handleDrillDownChange}
                />
              )}
              {this.tools.includes('view') && (
                <i
                  class={`icon-monitor view-icon ${isHidden ? 'icon-mc-invisible' : 'icon-mc-visual'}`}
                  v-bk-tooltips={{
                    content: this.$t(isHidden ? '点击显示该指标' : '点击隐藏该指标'),
                    disabled: isDisabled,
                  }}
                  onClick={() => !isDisabled && this.handleHiddenChange(child.id)}
                />
              )}
            </div>
          </div>
        );
      }),
      item.showMore && this.renderLoadMore(item.id),
    ];
  }

  render() {
    return (
      <div class={{ 'k8s-new___group-item': true, expand: this.expand[this.list.id] }}>
        <div
          class='group-header'
          onClick={() => this.collapseChange(this.list.id, Boolean(this.list.children))}
        >
          <div class='group-header-left'>
            <i class={`icon-monitor arrow-icon icon-mc-arrow-right ${this.expand[this.list.id] ? 'expand' : ''}`} />
            <span class='group-name'>{this.list.name}</span>
            <div class='group-count'>{this.list.count}</div>
            {this.value.length > 0 && this.tools.includes('clear') && (
              <div
                class='clear-filter'
                v-bk-tooltips={{ content: this.$t('清空整组筛选项') }}
                onClick={this.handleClear}
              >
                <div class='clear-filter-icon' />
              </div>
            )}
          </div>
          {this.tools.includes('groupBy') && (
            <div
              class='group-select'
              onClick={this.handleGroupByChange}
            >
              {this.isGroupBy ? this.$t('取消聚合') : this.$t('聚合')}
            </div>
          )}
        </div>
        <div
          style={{ display: this.expand[this.list.id] ? 'block' : 'none' }}
          class='group-content'
        >
          {this.renderGroupContent(this.list)}
        </div>
      </div>
    );
  }
}
