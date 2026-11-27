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
import { type PropType, computed, defineComponent } from 'vue';

import { ENABLED_TABLE_CONDITION_MENU_CLASS_NAME } from '../../../../../trace-explore/components/trace-explore-table/constants';

import './field-target.scss';

/** 条件菜单定位字段值所需的行和字段信息。 */
export interface FieldTargetInfo {
  /** 值实际所属的字段名。 */
  fieldName: string;
  /** 数组标签在原始数组中的下标。 */
  index?: number;
  /** 当前记录的表格行标识。 */
  rowId: string;
  /** 是否允许对该字段打开检索条件菜单。 */
  searchable: boolean;
}

export default defineComponent({
  name: 'RumFieldTarget',
  props: {
    /** 条件菜单从原始行取值的定位信息。 */
    target: { type: Object as PropType<FieldTargetInfo>, required: true },
    /** 左键已有详情或下钻动作时，条件菜单委托改用右键。 */
    action: { type: Function as PropType<(event: MouseEvent) => void>, default: undefined },
  },
  setup(props) {
    const actionable = computed(() => !!props.action || props.target.searchable);
    const targetAttrs = computed(() => ({
      class: [
        'rum-field-target',
        props.target.searchable && (props.action ? 'explore-click-text' : ENABLED_TABLE_CONDITION_MENU_CLASS_NAME),
      ],
      'data-col-id': props.target.fieldName,
      'data-row-id': props.target.rowId,
      'data-index': props.target.index,
    }));

    return { actionable, targetAttrs };
  },
  render() {
    const content = this.$slots.default?.();
    return this.actionable ? (
      <button
        {...this.targetAttrs}
        type='button'
        onClick={this.action}
      >
        {content}
      </button>
    ) : (
      <span {...this.targetAttrs}>{content}</span>
    );
  },
});
