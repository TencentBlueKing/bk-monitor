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
import type { VNodeChild } from 'vue';

/** 单元格图标及其所在位置附加的样式。 */
export interface CellIconConfig {
  /** 图标的尺寸、颜色等样式类。 */
  className?: string;
  /** 具体字库字形或渲染函数。 */
  icon: CellIconContent;
}

/** 图标字库类名或调用方提供的图标渲染函数。 */
export type CellIconContent = (() => VNodeChild) | string;

export default defineComponent({
  name: 'RumCellIcon',
  props: {
    /** 字库类名由组件补上 icon-monitor，自定义渲染函数返回图标节点。 */
    icon: { type: [String, Function] as PropType<CellIconContent>, required: true },
  },
  setup(props) {
    const fontClass = computed(() => (typeof props.icon === 'string' ? ['icon-monitor', props.icon] : undefined));
    return { fontClass };
  },
  render() {
    const { icon } = this;
    return typeof icon === 'string' ? (
      <i
        class={this.fontClass}
        aria-hidden='true'
      />
    ) : (
      <span
        class='rum-cell-icon-content'
        aria-hidden='true'
      >
        {icon()}
      </span>
    );
  },
});
