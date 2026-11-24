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

import type { FieldActions } from '../field-value/field-value';

export default defineComponent({
  name: 'RumCompositeActionPlaceholder',
  props: {
    /** 关联记录入口的可见名称，完整 URL 入口只显示图标。 */
    label: { type: String, default: '' },
    /** 图标的悬浮提示和无障碍名称。 */
    tooltip: { type: String, required: true },
    /** 复用表格的悬浮层控制器。 */
    hoverPopoverTools: { type: Object as PropType<FieldActions['hoverPopoverTools']>, required: true },
  },
  setup(props) {
    /** Session 和 Trace 暂用前进图标，URL 使用外链图标。 */
    const iconClass = computed(() => (props.label ? 'icon-qianjin' : 'icon-mc-goto'));

    /** 展示入口用途，复用表格的单例提示。 */
    const handleMouseEnter = (event: MouseEvent) => {
      props.hoverPopoverTools.showPopover(event, props.tooltip, {
        theme: 'dark',
        placement: props.label ? 'top' : 'bottom',
        interactive: false,
      });
    };

    /** 占位入口只响应悬停，点击时阻止表格行响应。 */
    const handleClick = (event: MouseEvent) => event.stopPropagation();

    return { handleClick, handleMouseEnter, iconClass };
  },
  render() {
    return (
      <button
        class={['rum-composite-action', { 'is-icon-only': !this.label }]}
        aria-disabled='true'
        aria-label={this.tooltip}
        tabindex={-1}
        type='button'
        onClick={this.handleClick}
        onMouseenter={this.handleMouseEnter}
        onMouseleave={this.hoverPopoverTools.clearPopoverTimer}
      >
        {this.label}
        <i
          class={['icon-monitor', this.iconClass, 'rum-composite-action-icon']}
          aria-hidden='true'
        />
      </button>
    );
  },
});
