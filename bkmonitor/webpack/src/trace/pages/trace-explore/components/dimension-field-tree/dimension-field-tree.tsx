/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import FieldTypeIcon from '../field-type-icon';

import type { IDimensionFieldTreeItem } from '../../typing';

import './dimension-field-tree.scss';

/**
 * APM 嵌入时 trace 主站的 global.scss 可能未进包，宿主全局气泡样式会污染默认主题，
 * 需要额外的 theme token 提高特异性；独立运行时该对象为空，等价于不传配置。
 */
const OVERFLOW_TIPS_OPTIONS = {
  // #if IS_APM_MONITOR
  theme: 'dark dimension-filter-name-overflow',
  // #endif
};

/**
 * 维度字段树。
 *
 * 只负责字段行的渲染与 object 节点的展开收起，统计弹层由调用方在收到 fieldClick 后自行挂载，
 * 这样 trace 检索与 RUM 检索可以共用同一套字段行样式和交互，各自对接不同的统计接口。
 */
export default defineComponent({
  name: 'DimensionFieldTree',
  props: {
    /** 已经过 convertToTree 转换的字段树 */
    list: { type: Array as PropType<IDimensionFieldTreeItem[]>, default: () => [] },
    /** 当前高亮的字段名 */
    activeField: { type: String, default: '' },
    /** 搜索态下 object 节点默认展开 */
    expandAll: { type: Boolean, default: false },
  },
  emits: {
    fieldClick: (_event: MouseEvent, _field: IDimensionFieldTreeItem) => true,
  },
  setup(props, { emit }) {
    /** 用户手动展开收起的结果，未记录的节点回落到 expandAll */
    const expandOverrides = shallowRef(new Map<string, boolean>());

    watch(
      () => props.list,
      () => {
        expandOverrides.value = new Map();
      }
    );

    /** object 节点的 name 只是路径的一段，同名节点可能出现在不同分支，用完整路径做键 */
    function isExpanded(nodeKey: string) {
      return expandOverrides.value.get(nodeKey) ?? props.expandAll;
    }

    function toggleExpand(nodeKey: string) {
      const overrides = new Map(expandOverrides.value);
      overrides.set(nodeKey, !isExpanded(nodeKey));
      expandOverrides.value = overrides;
    }

    function handleItemClick(event: MouseEvent, item: IDimensionFieldTreeItem, nodeKey: string) {
      if (item.children && item.children.length > 0) {
        toggleExpand(nodeKey);
        return;
      }
      emit('fieldClick', event, item);
    }

    function renderItem(item: IDimensionFieldTreeItem, level: number, parentKey: string) {
      const nodeKey = `${parentKey}/${item.levelAlias}`;
      const isTreeNode = item.children && item.children.length > 0;
      const expanded = isTreeNode && isExpanded(nodeKey);
      const disabled = !isTreeNode && !item.is_dimensions;

      return (
        <div
          key={nodeKey}
          style={{ '--level': level }}
          v-bk-tooltips={{
            content: window.i18n.t('该字段类型，暂时不支持统计分析'),
            disabled: !disabled,
            interactive: false,
            placement: 'right',
          }}
        >
          <div
            class={{
              'dimension-item': true,
              active: props.activeField === item.name,
              disabled,
              'leaf-item': !isTreeNode,
            }}
            onClick={event => handleItemClick(event, item, nodeKey)}
          >
            <FieldTypeIcon type={item.type} />
            <span
              class='dimension-name'
              v-overflow-tips={OVERFLOW_TIPS_OPTIONS}
            >
              {item.levelAlias}
              {item?.levelName && !isTreeNode && item.name !== item.alias && (
                <span class='subtitle'>({item.levelName})</span>
              )}
            </span>
            {isTreeNode && [
              <span
                key='object-count'
                class='object-count'
              >
                {item.count}
              </span>,
              <i
                key='object-arrow'
                class={['icon-monitor icon-arrow-right object-arrow', { expand: expanded }]}
              />,
            ]}
            {item.is_dimensions && !isTreeNode && <i class='icon-monitor icon-Chart statistics-icon' />}
          </div>

          {isTreeNode && expanded && (
            <div class='leaf-content'>{item.children.map(child => renderItem(child, level + 1, nodeKey))}</div>
          )}
        </div>
      );
    }

    return { renderItem };
  },
  render() {
    return <div class='dimension-field-tree'>{this.list.map(item => this.renderItem(item, 0, ''))}</div>;
  },
});
