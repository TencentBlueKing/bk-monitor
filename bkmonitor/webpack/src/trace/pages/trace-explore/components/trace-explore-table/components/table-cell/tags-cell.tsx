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

import { Tag } from 'bkui-vue';

import { ENABLED_TABLE_CONDITION_MENU_CLASS_NAME } from '../../constants';
import CollapseTags from './collapse-tags';

import type {
  ExploreTableColumn,
  ExploreTableColumnTypeEnum,
  GetTableCellRenderValue,
  TableCellRenderContext,
} from '../../typing';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './tags-cell.scss';

const DEFAULT_TAG_COLOR = {
  tagColor: '#4D4F56',
  tagBgColor: '#F0F1F5',
  tagHoverColor: '#4D4F56',
  tagHoverBgColor: '#DCDEE5',
};
export default defineComponent({
  name: 'TagsCell',
  props: {
    /** 当前列配置信息 */
    column: {
      type: Object as PropType<ExploreTableColumn<ExploreTableColumnTypeEnum.TAGS>>,
    },
    /** 当前需要渲染的数据 */
    tags: {
      type: Object as PropType<GetTableCellRenderValue<ExploreTableColumnTypeEnum.TAGS>>,
    },
    /** 当前列 id */
    colId: {
      type: String,
    },
    /** 当前行数据 id */
    rowId: {
      type: String,
    },
    /** table 单元格渲染上下文信息 */
    renderCtx: {
      type: Object as PropType<TableCellRenderContext>,
      default: () => ({}),
    },
  },
  setup() {
    /**
     * @description 默认的溢出标签提示popover内容渲染方法
     * @param ellipsisTags 溢出标签列表
     * @returns {SlotReturnValue} popover 展示的内容
     */
    const defaultEllipsisTipsContentRender = (ellipsisTags: any[] | string[]): SlotReturnValue =>
      ellipsisTags.map(tag => tag?.alias || tag).join('，');
    return {
      defaultEllipsisTipsContentRender,
    };
  },
  render() {
    return (
      <CollapseTags
        class='explore-col explore-tags-col'
        v-slots={{
          customTag: (tag, index) => (
            <Tag
              key={index}
              style={{
                '--tag-color': tag?.tagColor || DEFAULT_TAG_COLOR.tagColor,
                '--tag-bg-color': tag?.tagBgColor || DEFAULT_TAG_COLOR.tagBgColor,
                '--tag-hover-color': tag?.tagHoverColor || tag?.tagColor || DEFAULT_TAG_COLOR.tagHoverColor,
                '--tag-hover-bg-color': tag?.tagHoverBgColor || tag?.tagBgColor || DEFAULT_TAG_COLOR.tagHoverBgColor,
              }}
              class={`tag-item ${this.renderCtx?.isEnabledCellEllipsis(this.column)}`}
            >
              {{
                default: () => (
                  <span
                    class={`${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
                    data-col-id={this.colId}
                    data-index={index}
                    data-row-id={this.rowId}
                  >
                    {tag?.alias || tag}
                  </span>
                ),
              }}
            </Tag>
          ),
        }}
        data={this.tags}
        ellipsisTip={this.column?.cellSpecificProps?.ellipsisTip ?? this.defaultEllipsisTipsContentRender}
        ellipsisTippyOptions={this.column?.cellSpecificProps?.ellipsisTippyOptions ?? {}}
      />
    );
  },
});
