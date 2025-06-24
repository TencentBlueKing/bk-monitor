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

import { defineComponent, ref as deepRef, watch, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { Tree, type TreeNodeValue } from 'tdesign-vue-next';

import './quick-filtering.scss';
export interface QuickFilteringGroupItem {
  id: number | string;
  name: string;
  icon?: string;
  color?: string;
  children?: QuickFilteringGroupItem[];
}

export interface QuickFilteringGroup {
  id: string;
  name: string;
  type: 'icon' | 'rect' | 'text';
  color?: string;
  children: QuickFilteringGroupItem[];
}

export default defineComponent({
  name: 'QuickFiltering',
  props: {
    groupList: {
      type: Array as PropType<QuickFilteringGroup[]>,
      default: () => [],
    },
    value: {
      type: Object as PropType<Record<string, string[]>>,
      default: () => ({}),
    },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const localValue = deepRef({});

    watch(
      () => props.value,
      val => {
        if (!val) {
          localValue.value = {};
        } else {
          localValue.value = { ...val };
        }
      }
    );

    const handleClose = () => {
      emit('close', true);
    };

    const handleNodeChecked = (groupId: string, itemId: TreeNodeValue[]) => {
      console.log(groupId, itemId);
      localValue.value[groupId] = itemId;
    };

    const renderFilterTree = (group: QuickFilteringGroup) => {
      return (
        <Tree
          class={{ 'no-multi-level': !group.children.some(child => child.children?.length) }}
          checkable={true}
          data={group.children}
          expandAll={true}
          expandOnClickNode={true}
          hover={false}
          keys={{ value: 'id', label: 'name', children: 'children' }}
          transition={false}
          value={localValue.value[group.id]}
          onChange={id => handleNodeChecked(group.id, id)}
        >
          {{
            icon: ({ node }) => {
              return node.isLeaf() ? undefined : <i class='icon-monitor icon-mc-arrow-right' />;
            },
            label: ({ node }) => (
              <div class='condition-tree-item'>
                {group.type === 'icon' && (
                  <i
                    style={{ color: node.data.color || group.color || '#8E9BB3' }}
                    class={['icon-monitor', 'item-icon', node.data.icon]}
                  />
                )}
                {group.type === 'rect' && (
                  <div
                    style={{ backgroundColor: node.data.color || group.color || '#8E9BB3' }}
                    class='item-rect'
                  />
                )}
                <span
                  style={{ color: (group.type === 'rect' ? node.data.color || group.color : '') || '#313238' }}
                  class='item-name'
                  v-overflow-tips
                >
                  {node.data.name}
                </span>
                <span class='item-count'>{node.data.count}</span>
              </div>
            ),
          }}
        </Tree>
      );
    };

    return {
      t,
      handleClose,
      renderFilterTree,
    };
  },
  render() {
    return (
      <div class='quick-filtering-comp'>
        <div class='quick-filtering-header'>
          <i
            class='icon-monitor icon-gongneng-shouqi'
            v-bk-tooltips={{ content: this.t('收起') }}
            onClick={this.handleClose}
          />
          <div class='title'>{this.t('快捷筛选')}</div>
        </div>
        <div class='group-list'>
          {this.groupList.map(group => (
            <div
              key={group.id}
              class='group-item'
            >
              <div class='group-header'>
                <div class='group-title'>{group.name}</div>
                <i class='icon-monitor icon-a-Clearqingkong' />
              </div>
              <div class='group-children'>{this.renderFilterTree(group)}</div>
            </div>
          ))}
        </div>
      </div>
    );
  },
});
