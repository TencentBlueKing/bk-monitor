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

import { RumModeEnum, SESSION_ID_FIELD, VIEW_ID_FIELD } from '../../../../constants';
import FieldTarget from './field-target';
import { EMethod } from '@/components/retrieval-filter/typing';

import type { IRumCountDrillDown, IRumSpanRecord, RumModeType } from '../../../../typings';
import type { FieldTargetInfo } from './field-target';

/** 计数的目标视角和用于约束目标记录的 ID 字段。 */
interface CountDrillDown extends Pick<IRumCountDrillDown, 'spanType' | 'targetMode'> {
  /** 下钻筛选使用的会话 ID 或页面 ID 字段。 */
  idField: string;
}

const sessionTargets = new Map<string, Pick<IRumCountDrillDown, 'spanType' | 'targetMode'>>([
  ['action_count', { targetMode: RumModeEnum.SPAN, spanType: 'action' }],
  ['error_count', { targetMode: RumModeEnum.SPAN, spanType: 'error' }],
  ['view_count', { targetMode: RumModeEnum.VIEW }],
]);
const viewCountFields = new Set(['action_count', 'error_count', 'request_count']);

/**
 * 查找当前视角下计数字段对应的下钻目标。
 * @param mode 当前检索视角
 * @param fieldName 计数成员的真实字段名
 * @returns 下钻目标，普通字段返回 undefined
 */
export const resolveCountField = (mode: RumModeType, fieldName: string): CountDrillDown | undefined => {
  if (mode === RumModeEnum.SESSION) {
    const target = sessionTargets.get(fieldName);
    return target && { ...target, idField: SESSION_ID_FIELD };
  }
  if (mode === RumModeEnum.VIEW && viewCountFields.has(fieldName)) {
    return { targetMode: RumModeEnum.SPAN, idField: VIEW_ID_FIELD };
  }
};

export default defineComponent({
  name: 'RumCountValue',
  props: {
    /** 值作为复合列标签展示时，仅提供标签交互。 */
    badge: { type: Boolean, default: false },
    /** 当前计数字段的下钻目标。 */
    drillDown: { type: Object as PropType<CountDrillDown>, required: true },
    /** 提供下钻所需的会话或页面 ID。 */
    row: { type: Object as PropType<IRumSpanRecord>, required: true },
    /** 条件菜单回溯原始值时使用的定位信息。 */
    target: { type: Object as PropType<FieldTargetInfo>, required: true },
    /** 已按字段格式化的计数文案。 */
    text: { type: String, required: true },
    /** 用于判断是否允许下钻的原始计数。 */
    value: { type: null, required: true },
  },
  emits: {
    /** 切换至目标视角并应用当前记录的 ID 筛选。 */
    drillDown: (_payload: IRumCountDrillDown) => true,
  },
  setup(props, { emit }) {
    const count = computed(() => {
      const { value } = props;
      return typeof value === 'number' || (typeof value === 'string' && value.trim()) ? Number(value) : NaN;
    });
    const id = computed(() => String(props.row[props.drillDown.idField] ?? ''));
    const canDrill = computed(() => Number.isFinite(count.value) && count.value > 0 && !!id.value && !props.badge);
    const valueClass = computed(() => {
      if (props.badge) return 'rum-cell-badge';
      const linkStyle =
        props.drillDown.idField === VIEW_ID_FIELD ? 'is-link is-danger is-underlined' : 'is-link is-brand';
      return `rum-count-value ${count.value === 0 ? 'is-zero' : canDrill.value ? linkStyle : ''}`;
    });

    /** 从计数下钻，避免冒泡触发表格行高亮。 */
    const handleDrillDown = (event: MouseEvent) => {
      event.stopPropagation();
      emit('drillDown', {
        condition: { key: props.drillDown.idField, method: EMethod.eq, value: id.value },
        targetMode: props.drillDown.targetMode,
        spanType: props.drillDown.spanType,
      });
    };

    return { canDrill, handleDrillDown, valueClass };
  },
  render() {
    return (
      <FieldTarget
        class={this.valueClass}
        action={this.canDrill ? this.handleDrillDown : undefined}
        target={this.target}
      >
        {this.text}
      </FieldTarget>
    );
  },
});
