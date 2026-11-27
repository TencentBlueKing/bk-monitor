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

import { VIEW_ID_FIELD } from '../../../../constants';
import FieldTarget from './field-target';
import { EMethod } from '@/components/retrieval-filter/typing';

import type { CountDrillDown, IRumCountDrillDown, IRumSpanRecord } from '../../../../typings';
import type { FieldTargetInfo } from './field-target';

import './count-value.scss';

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
    /** 用于判断是否允许下钻的原始计数。 */
    value: { type: null, required: true },
  },
  emits: {
    /** 切换至目标视角并应用当前记录的 ID 筛选。 */
    drillDown: (_payload: IRumCountDrillDown) => true,
  },
  setup(props, { emit }) {
    /** 仅将数字和非空字符串解析为计数。 */
    const count = computed(() => {
      const { value } = props;
      return typeof value === 'number' || (typeof value === 'string' && value.trim()) ? Number(value) : NaN;
    });
    /** 根据下钻配置从当前行获取会话或页面 ID。 */
    const id = computed(() => String(props.row[props.drillDown.idField] ?? ''));
    /** 只有非标签位置的正数计数且 ID 存在时可下钻。 */
    const canDrill = computed(() => Number.isFinite(count.value) && count.value > 0 && !!id.value && !props.badge);
    /** 普通计数按零值和下钻状态选择样式，标签样式由调用方提供。 */
    const valueClass = computed(() => {
      if (props.badge) return undefined;
      const drillDownClass = props.drillDown.idField === VIEW_ID_FIELD ? 'is-danger is-underlined' : 'is-brand';
      return `rum-count-value ${count.value === 0 ? 'is-zero' : canDrill.value ? drillDownClass : ''}`;
    });

    /**
     * @description 触发计数下钻并阻止点击冒泡到表格行。
     * @param event 下钻按钮的点击事件
     */
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
        {this.$slots.default?.()}
      </FieldTarget>
    );
  },
});
