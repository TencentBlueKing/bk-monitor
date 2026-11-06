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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

import { type PropType, computed, defineComponent } from 'vue';

import { COMMON_TABLE_ELLIPSIS_CLASS_NAME } from '../../../../../alarm-center/typings/constants';
import CollapseTags from '../../../../../trace-explore/components/trace-explore-table/components/table-cell/collapse-tags';
import { ENABLED_TABLE_CONDITION_MENU_CLASS_NAME } from '../../../../../trace-explore/components/trace-explore-table/constants';

import type {
  BaseTableColumn,
  TableCellRenderContext,
} from '../../../../../trace-explore/components/trace-explore-table/typing';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './collapse-array-cell.scss';

/**
 * @description 折叠数组单元格：按「值 , 值 , 值 +N」的形式内联展示数组，超出列宽的部分折叠为 +N，
 *              hover +N 以换行列表展示剩余值。
 *
 * 复用 CollapseTags 的溢出测量能力（其测量基于子元素真实 getBoundingClientRect，与 Tag 组件无耦合），
 * 通过 customTag 插槽把每一项替换为纯文本，故列宽拖拽后可见数量会自动重算。
 *
 * 通用化约定（与 tags-cell 同源，便于其它场景直接复用或小成本改造）：
 * - 省略类名：优先取 renderCtx.isEnabledCellEllipsis(column)（跟随表格/列配置与省略位置），
 *   非表格场景回退 ellipsisClass；只挂在「值文本层」而非整格包裹层——挂在包裹层会让 hover 任意位置
 *   （含 [+N]）都命中表格 tip，与 [+N] 自带的 tippy 同时弹出。
 * - 最小可见数量：列配置 cellSpecificProps.minVisibleCount 优先，未配置时取组件 prop。
 * - 外观与提示均可由 customTag / collapseTag / ellipsisTip 插槽整体替换。
 * - 只有传入 colId 才给值文本挂条件菜单类名（[+N] 与值项各自独立，不会互相触发）。
 */
export default defineComponent({
  name: 'CollapseArrayCell',
  props: {
    /** 已由调用方按字段语义格式化过的数组项文本（如耗时已带单位、时间已格式化） */
    values: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 当前列配置：读取 cellSpecificProps.minVisibleCount 等列级配置 */
    column: {
      type: Object as PropType<BaseTableColumn>,
    },
    /** 表格单元格渲染上下文：用于推导省略类名（非表格场景可不传） */
    renderCtx: {
      type: Object as PropType<TableCellRenderContext>,
      default: () => ({}),
    },
    /** 当前列 id：传入后值文本才挂「加为检索条件」菜单类名 */
    colId: {
      type: String,
    },
    /** 当前行数据 id */
    rowId: {
      type: String,
    },
    /** 最少保持可见的数组项数量，未配置时回退列配置 cellSpecificProps.minVisibleCount，默认 0 保持原有折叠行为 */
    minVisibleCount: {
      type: Number,
      default: 0,
    },
    /** 非表格场景下的单元格溢出省略类名兜底（表格场景由 renderCtx 推导） */
    ellipsisClass: {
      type: String,
      default: COMMON_TABLE_ELLIPSIS_CLASS_NAME,
    },
    /** 值之间的分隔符（渲染在非首项之前，折叠发生在任意位置时末尾都不会残留孤立分隔符） */
    separator: {
      type: String,
      default: ',',
    },
    /** 是否启用条件菜单类名（[+N] 与值项各自独立，不会互相触发） */
    enableConditionMenu: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    /** 省略类名：表格场景按列配置推导，非表格场景回退 ellipsisClass */
    const tipClass = computed(() => props.renderCtx?.isEnabledCellEllipsis?.(props.column) || props.ellipsisClass);
    /** 最小可见数量：列配置优先于组件 prop */
    const resolvedMinVisibleCount = computed(
      () => props.column?.cellSpecificProps?.minVisibleCount ?? props.minVisibleCount
    );
    /**
     * @description 溢出项提示内容：每行一个值，数组项较长时比逗号拼接更易读
     * @param {string[]} ellipsisList 被折叠的数组项
     * @returns {SlotReturnValue} popover 展示的内容
     */
    const ellipsisTipRender = (ellipsisList: string[]) =>
      (
        <div class='ellipsis-tip-content'>
          {ellipsisList.map((value, index) => (
            <div
              key={`${index}_${value}`}
              class='ellipsis-tip-item'
            >
              <div class='item-prefix'>
                <i class='item-hyphen' />
              </div>
              <div class='item-text'>{value}</div>
            </div>
          ))}
        </div>
      ) as unknown as SlotReturnValue;

    return { ellipsisTipRender, tipClass, resolvedMinVisibleCount };
  },
  render() {
    /** 分隔符号渲染在「非首项之前」而非「非末项之后」：折叠发生在任意位置时，末尾都不会残留孤立分隔符 */
    const defaultCustomTag = (value: string, index: number): SlotReturnValue =>
      (
        <span class='collapse-array-value-item'>
          {index > 0 && <span class='collapse-array-value-sep'>{this.separator}</span>}
          {/* 省略类名只挂值文本层：复用表格委托，溢出才弹全文 tip，且不会与 [+N] 的 tippy 同时弹出 */}
          <span
            class={[
              'collapse-array-value-text',
              this.tipClass,
              { [ENABLED_TABLE_CONDITION_MENU_CLASS_NAME]: this.enableConditionMenu },
            ]}
            data-col-id={this.colId}
            data-index={index}
            data-row-id={this.rowId}
          >
            {value}
          </span>
        </span>
      ) as unknown as SlotReturnValue;

    return (
      <CollapseTags
        class='explore-col collapse-array-col'
        v-slots={{
          customTag: this.$slots?.customTag ?? defaultCustomTag,
          /** 折叠标识默认按 [+N] 呈现 */
          collapseTag: this.$slots?.collapseTag ?? ((count: number) => <>[+{count}]</>),
        }}
        ellipsisTippyOptions={{
          theme: 'dark text-wrap max-width-50vw collapse-array-ellipsis-tip',
        }}
        data={this.values}
        ellipsisTip={this.$slots?.ellipsisTip ?? this.ellipsisTipRender}
        minVisibleCount={this.resolvedMinVisibleCount}
      />
    );
  },
});
