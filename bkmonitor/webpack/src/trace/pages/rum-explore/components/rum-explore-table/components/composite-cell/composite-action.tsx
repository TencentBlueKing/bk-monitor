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

import CellIcon, { type CellIconContent } from '../cell-icon/cell-icon';

import type { FieldActions } from '../../../../typings';

export default defineComponent({
  name: 'RumCompositeAction',
  props: {
    /** 外链跳转地址。省略时渲染为页内操作按钮。 */
    href: { type: String, default: '' },
    /** 调用方为当前入口指定的图标。 */
    icon: { type: [String, Function] as PropType<CellIconContent>, required: true },
    /** 关联记录入口的可见名称，完整 URL 入口只显示图标。 */
    label: { type: String, default: '' },
    /** 图标的悬浮提示和无障碍名称。 */
    tooltip: { type: String, required: true },
    /** 复用表格的悬浮层控制器。 */
    hoverPopoverTools: { type: Object as PropType<FieldActions['hoverPopoverTools']>, required: true },
  },
  emits: {
    /** 将页内操作的点击通知列渲染器。 */
    click: () => true,
  },
  /**
   * @description 将复合列入口的悬浮提示和点击统一接入表格交互。
   * @param props 当前入口的地址、图标及提示
   * @param context Vue 组件上下文，用于向列渲染器传递页内点击
   * @returns 渲染入口所需的悬浮和点击处理方法
   */
  setup(props, { emit }) {
    /**
     * @description 复用表格的单例提示，带标签的入口在上方显示，纯图标入口在下方显示。
     * @param {MouseEvent} event 提供提示的锚点元素
     * @returns {void}
     */
    const handleMouseEnter = (event: MouseEvent) => {
      props.hoverPopoverTools.showPopover(event, props.tooltip, {
        theme: 'dark',
        placement: props.label ? 'top' : 'bottom',
        interactive: false,
      });
    };

    /**
     * @description 拦截冒泡以避免触发表格行交互，保留外链由浏览器处理的默认行为。
     * @param {MouseEvent} event 入口的原生点击事件
     * @returns {void}
     */
    const handleClick = (event: MouseEvent) => {
      event.stopPropagation();
      props.hoverPopoverTools.hidePopover();
      if (!props.href) emit('click');
    };

    return { handleClick, handleMouseEnter };
  },
  /**
   * @description 根据入口地址选择原生链接或按钮，两者共用图标和提示。
   * @returns 页内操作按钮或新标签页外链节点
   */
  render() {
    const actionProps = {
      class: ['rum-composite-action', { 'is-icon-only': !this.label }],
      'aria-label': this.tooltip,
      onClick: this.handleClick,
      onMouseenter: this.handleMouseEnter,
      onMouseleave: this.hoverPopoverTools.clearPopoverTimer,
    };
    const content = (
      <>
        {this.label}
        <CellIcon
          class='rum-composite-action-icon'
          icon={this.icon}
        />
      </>
    );
    return this.href ? (
      <a
        {...actionProps}
        href={this.href}
        rel='noopener noreferrer'
        target='_blank'
      >
        {content}
      </a>
    ) : (
      <button
        {...actionProps}
        type='button'
      >
        {content}
      </button>
    );
  },
});
