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

import { type PropType, defineComponent } from 'vue';

import CollapseTags from 'trace/pages/trace-explore/components/trace-explore-table/components/table-cell/collapse-tags';

import './tag-cell.scss';

/**
 * @description 标签单元格，用于展示智能体 / 知识库 / skill 等标签列表，超出部分折叠展示
 */
export default defineComponent({
  name: 'TagCell',
  props: {
    /** 标签列表 */
    tags: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    nameMap: {
      type: Object as PropType<Map<string, string>>,
      default: () => new Map(),
    },
  },
  setup(props) {
    /**
     * @description 默认的溢出标签提示popover内容渲染方法
     * @param ellipsisTags 溢出标签列表
     * @returns {SlotReturnValue} popover 展示的内容
     */
    const defaultEllipsisTipsContentRender = (ellipsisTags: string[]) =>
      ellipsisTags
        .map(item => {
          const name = props.nameMap.get(item);
          if (name && name !== item) {
            return `${name}（${item}）`;
          }
          return item;
        })
        .join('，');
    return {
      defaultEllipsisTipsContentRender,
    };
  },
  render() {
    return (
      <CollapseTags
        class='analysis-rule-table-tags-cell'
        data={this.tags}
        ellipsisTip={this.defaultEllipsisTipsContentRender}
      >
        {{
          customTag: (tag, index) => (
            <span
              key={`${index}-${tag}`}
              class='analysis-rule-table-tags-cell-tag-item'
              v-bk-tooltips={{
                content: tag,
              }}
            >
              {this.nameMap.get(tag) || tag}
            </span>
          ),
        }}
      </CollapseTags>
    );
  },
});
