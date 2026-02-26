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
// TreeComponent.tsx
import { defineComponent, computed } from 'vue';

import './tree-component.scss';
/**
 * 定义树节点数据结构
 */
type ITreeNode = {
  id: string;
  name: string;
  type?: string;
  children?: ITreeNode[];
  isOpen?: boolean;
};
export default defineComponent({
  name: 'TreeComponent',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
    maxLevel: {
      type: Number,
      default: 2,
    },
    activeNodeId: {
      type: String,
      default: '',
    },
  },
  emits: ['click-node', 'toggle'],
  setup(props, { emit }) {
    const treeNodes = computed<ITreeNode[]>(() => ((props.data as ITreeNode[]) || []));
    /**
     * 切换节点展开/收起状态
     * @param node
     * @param level
     */
    const toggleTree = (node: ITreeNode, level: number) => {
      node.isOpen = !node.isOpen;
      emit('toggle', node, level);
    };

    /**
     * 递归渲染树节点
     * @param node
     * @param parent
     * @param level
     * @returns
     */
    const renderITreeNode = (node: ITreeNode, parent?: ITreeNode, level = 0) => {
      const children = node.children || [];
      const hasChildren = children.length > 0;
      const isActive = props.activeNodeId === node.id;
      const nodeId = `${node.id}-${level}`;
      return (
        <li
          key={nodeId}
          class='tree-node'
        >
          <div class={{ 'tree-item': true, active: isActive }}>
            <div
              class='flex items-center'
              on-Click={e => {
                e.stopPropagation();
                if (level < props.maxLevel) {
                  toggleTree(node, level);
                } else {
                  emit('click-node', node, parent);
                }
              }}
            >
              {hasChildren && (
                <i
                  class={`bklog-icon bklog-arrow-down-filled tree-toggle ${node.isOpen ? '' : 'collapsed'}`}
                  data-toggle
                />
              )}
              <span
                class={hasChildren ? 'font-medium' : 'text-tree-light'}
                title={node.name}
              >
                {node.name}
              </span>
            </div>
            {level < props.maxLevel && <span class='count-badge'>{children.length}</span>}
          </div>

          {hasChildren && node.isOpen && (
            <ul
              id={`tree-children-${nodeId}`}
              class={'tree-children'}
            >
              {children.map(child => (
                <li
                  key={`${nodeId}-child-${child.id}`}
                  class='tree-line'
                >
                  {renderITreeNode(child, node, level + 1)}
                </li>
              ))}
            </ul>
          )}
        </li>
      );
    };

    return () => (
      <div class='tree-container-wrapper'>
        <ul class='tree-root-list'>{(treeNodes.value as ITreeNode[]).map(node => renderITreeNode(node))}</ul>
      </div>
    );
  },
});
