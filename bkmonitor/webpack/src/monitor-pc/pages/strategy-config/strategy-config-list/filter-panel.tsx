import type { VNode } from 'vue';

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

import Group, { type IGroupData } from './group';
import FilterListSkeleton from './skeleton/filter-list';

import type { TranslateResult } from 'vue-i18n';

import './filter-panel.scss';

// 勾选的数据（筛选表格）
export interface IFilterData {
  id: number | string; // 所属分组ID
  name: TranslateResult; // 分组名称
  values?: any[]; // 勾选数据
}
// 事件
type FilterPanelEvents = {
  change?: (data: IFilterData[]) => void;
};
// 属性
type FilterPanelProps = {
  checkedData: IFilterData[];
  data: IGroupData[];
  defaultActiveName?: string[];
  show: boolean;
  showSkeleton?: boolean;
  width?: number;
};

// 插槽
type FilterPanelScopedSlots = {
  header?: () => VNode;
};

interface ITreeNode {
  children?: any[];
  data: any;
  id: number | string;
}

/**
 * 策略配置列表左侧筛选面板
 */
@Component({ name: 'FilterPanel' })
export default class FilterPanel extends tsc<FilterPanelProps, FilterPanelEvents, FilterPanelScopedSlots> {
  // 是否显示面板
  @Prop({ default: false, type: Boolean }) readonly show: boolean;
  // 数据源
  @Prop({ default: () => [], type: Array }) readonly data: IGroupData[];
  // 默认宽度
  @Prop({ default: 214, type: Number }) readonly width: number;
  // 默认展开项
  @Prop({ default: () => ['strategy_status', 'data_source_list', 'scenario'], type: Array })
  defaultActiveName!: string[];
  // 勾选节点的数据
  @Prop({ default: () => [], type: Array }) checkedData: IFilterData[];
  /** 是否展示骨架屏 */
  @Prop({ default: false, type: Boolean }) showSkeleton: boolean;

  activeName = this.defaultActiveName;
  filterData: IFilterData[] = [];
  isShowScrollbar = false; // 显示滚动条

  get filterPanelStyle() {
    return {
      width: `${this.width}px`,
    };
  }

  @Watch('checkedData', { deep: true, immediate: true })
  handleCheckedDataChange(v) {
    this.filterData = JSON.parse(JSON.stringify(v));
  }

  render(): VNode {
    return (
      <transition name='slide'>
        <section
          class='filter-panel'
          v-show={this.show}
          onMouseenter={() => (this.isShowScrollbar = true)}
          onMouseleave={() => (this.isShowScrollbar = false)}
        >
          {this.$slots.header || (
            <div class='filter-panel-header mb20'>
              <span class='title'>{this.$t('筛选')}</span>
              {/* <span class="folding" onClick={this.handleHidePanel}>
              <i class="icon-monitor icon-double-up"></i>
            </span> */}
            </div>
          )}
          <div class={['filter-panel-body', { 'show-scrollbar': this.isShowScrollbar }]}>
            {this.showSkeleton ? (
              <FilterListSkeleton />
            ) : (
              <Group
                scopedSlots={{
                  default: ({ item }) => this.collapseItemContentSlot(item),
                }}
                data={this.data}
                defaultActiveName={this.defaultActiveName}
                theme='filter'
                on-clear={this.handleClear}
              />
            )}
          </div>
        </section>
      </transition>
    );
  }

  /**
   * 隐藏筛选面板
   */
  handleHidePanel() {
    this.$emit('update:show', false);
  }

  /**
   * 分组内容区域
   * @param item
   * @returns
   */
  collapseItemContentSlot(item: IGroupData) {
    const data = JSON.parse(JSON.stringify(item.data));
    const group = this.checkedData.find(data => data.id === item.id);
    const defaultCheckedNodes = group ? group.values.map(value => value.id) : [];
    return (
      <bk-big-tree
        ext-cls='filter-panel-tree'
        scopedSlots={{
          default: ({ data }) => (
            <span class='check-label-content'>
              {data.icon && <i class={['icon-monitor', 'pre-icon', data.icon]} />}
              <span
                class='label-text'
                v-bk-overflow-tips
                title={data.name}
              >
                {data.name}
              </span>
              <span class='label-count'>{data.count || 0}</span>
            </span>
          ),
        }}
        collapse-icon=''
        data={data}
        default-checked-nodes={defaultCheckedNodes}
        expand-icon=''
        expand-on-click={false}
        padding={0}
        check-on-click
        default-expand-all
        show-checkbox
        on-check-change={(id, node) => this.handleTreeCheckChange(id, node, item)}
      />
    );
  }

  /**
   * Tree change事件
   * @param ids
   * @param item
   */
  handleTreeCheckChange(ids: string[], node: ITreeNode, item: IGroupData) {
    if (node.data.children) {
      const { children } = node.data;
      const childrenIds = children.map(item => item.id);
      const group = this.filterData.find(data => data.id === item.id);
      if (group) {
        const groupIds = group.values.map(item => item.id);
        const len = group.values.length;
        const childLen = childrenIds.length;
        const diffIds = [];
        groupIds.forEach(item => {
          if (childrenIds.includes(item)) {
            diffIds.push(item);
          }
        });
        // 全选
        if (childLen !== diffIds.length) {
          for (let i = 0; i < childLen; i++) {
            const childrenId = childrenIds[i];
            if (!groupIds.includes(childrenId)) {
              group.values.push(children.find(data => data.id === childrenId));
            }
          }
        } else {
          // 全不选
          for (let i = len - 1; i >= 0; i--) {
            if (diffIds.includes(group.values[i].id)) {
              group.values.splice(i, 1);
            }
          }
        }
      } else {
        this.filterData.push({
          id: item.id,
          name: item.name,
          values: JSON.parse(JSON.stringify(node.data.children)),
        });
      }
    } else {
      const group = this.filterData.find(data => data.id === item.id);
      if (group) {
        const index = group.values.findIndex(value => value.id === node.data.id);
        index === -1 ? group.values.push(node.data) : group.values.splice(index, 1);
      } else {
        this.filterData.push({
          id: item.id,
          name: item.name,
          values: [node.data],
        });
      }
    }
    this.handleCheckChange();
  }

  @Emit('change')
  handleCheckChange() {
    return this.filterData;
  }
  handleClear(item) {
    const { id } = item;
    const index = this.filterData.findIndex(data => data.id === id);
    if (index > -1) {
      this.filterData[index].values = [];
      this.handleCheckChange();
    }
  }
}
