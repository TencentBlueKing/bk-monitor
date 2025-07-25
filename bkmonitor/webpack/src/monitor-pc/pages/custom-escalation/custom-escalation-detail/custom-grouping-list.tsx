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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { IGroupListItem } from './custom-escalation-detail';

import './custom-grouping-list.scss';

interface IGroup {
  autoRules?: string[];
  manualList?: string[];
  metric_count?: number;
  name: string;
}

interface IMenuItem {
  checked: boolean;
  id: 'delete' | 'edit';
  name: string;
}

@Component
export default class CustomGroupingList extends tsc<any, any> {
  @Prop({ default: () => [] }) groupList: IGroup[];
  @Prop({ default: '' }) selectedLabel;
  @Prop({ default: false }) isSearchMode: boolean;
  @Prop({ default: () => new Map() }) groupsMap: Map<string, IGroupListItem>;

  menuList: IMenuItem[] = [
    {
      name: window.i18n.tc('编辑'),
      checked: false,
      id: 'edit',
    },
    {
      name: window.i18n.tc('删除'),
      checked: false,
      id: 'delete',
    },
  ];

  /** 当前拖拽id */
  dragId = '';
  dragoverId = '';

  handleMenuClick(type: 'delete' | 'edit', groupName) {
    // TODO[中等]
    this.$emit('menuClick', type, groupName);
  }

  // 拖拽开始，记录当前拖拽的ID
  handleDragstart(index: number, e) {
    this.dragId = index.toString();
  }

  // 拖拽经过事件，设置当前拖拽ID
  handleDragover(index: number, e: DragEvent) {
    e.preventDefault();
    this.dragoverId = index.toString();
  }

  // 拖拽离开事件，清除当前拖拽的ID
  handleDragleave() {
    this.dragoverId = '';
  }

  @Emit('groupListOrder')
  saveGroupRuleOrder(tab) {
    this.$store.dispatch('custom-escalation/saveGroupingRuleOrder', {
      time_series_group_id: this.$route.params.id,
      group_names: tab.map(item => item.name),
    });
    return tab;
  }

  // 拖拽完成时逻辑
  handleDrop() {
    if (this.dragId !== this.dragoverId) {
      const tab = Object.assign([], this.groupList);
      const dragIndex = Number.parseInt(this.dragId, 10);
      const dragoverIndex = Number.parseInt(this.dragoverId, 10);

      const draggedTab = this.groupList[dragIndex];
      tab.splice(dragIndex, 1);
      tab.splice(dragoverIndex, 0, draggedTab);
      this.dragId = '';
      this.dragoverId = '';
      this.saveGroupRuleOrder(tab);
    }
    this.dragoverId = '';
  }
  // 拖拽 end

  changeSelectedLabel(name: string) {
    if (name === this.selectedLabel) return;
    this.$emit('changeGroup', name);
  }

  getGroupCountByName(name: string) {
    const group = this.groupsMap.get(name);
    if (!group) return 0;
    // 去重
    const groupArray = Array.from(new Set([...(group?.manualList || []), ...(group?.matchRulesOfMetrics || [])]));
    // 去除 null 和 undefined
    return groupArray.filter(name => name).length;
  }

  render() {
    return (
      <div class='custom-group'>
        {this.groupList.length ? (
          this.groupList.map((group, index) => (
            <div
              key={group.name}
              class={[
                'group',
                this.dragoverId === index.toString() ? 'is-dragover' : '',
                this.selectedLabel === group.name ? 'group-selected' : '',
              ]}
              draggable={!this.isSearchMode}
              onClick={() => this.changeSelectedLabel(group.name)}
              onDragleave={this.handleDragleave}
              onDragover={e => this.handleDragover(index, e)}
              onDragstart={e => this.handleDragstart(index, e)}
              onDrop={this.handleDrop}
            >
              {!this.isSearchMode && <i class='icon-monitor icon-mc-tuozhuai item-drag' />}
              <div class='group-name'>
                <i class='icon-monitor icon-FileFold-Close' />
                {group.name}
              </div>
              <div class='group-count'>{this.getGroupCountByName(group.name)}</div>
              <bk-popover
                ref='menuPopover'
                class='group-popover'
                ext-cls='group-popover'
                arrow={false}
                offset={'0, 0'}
                placement='bottom-start'
                theme='light common-monitor'
              >
                <span class='more-operation'>
                  <i class='icon-monitor icon-mc-more' />
                </span>
                <div
                  class='group-more-list'
                  slot='content'
                >
                  {this.menuList.map(item => (
                    <span
                      key={item.id}
                      class={`more-list-item ${item.id}`}
                      onClick={() => this.handleMenuClick(item.id, group.name)}
                    >
                      {item.name}
                    </span>
                  ))}
                </div>
              </bk-popover>
            </div>
          ))
        ) : (
          <div>
            {/* TODO 空态 */}
            空的
          </div>
        )}
      </div>
    );
  }
}
