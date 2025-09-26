/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import './selector-trigger.scss';

export default defineComponent({
  name: 'SelectorTrigger',
  props: {
    active: {
      type: Boolean,
      default: false,
    },
    hasRightSplit: {
      type: Boolean,
      default: true,
    },
    mouseDown: {
      type: Function as PropType<(payload: MouseEvent) => void>,
      default: () => {},
    },
    click: {
      type: Function as PropType<(payload: MouseEvent) => void>,
      default: () => {},
    },
    defaultWidth: {
      type: Number,
      default: 210,
    },
    tips: {
      type: String,
      default: '',
    },
    isError: {
      type: Boolean,
      default: false,
    },
  },
  render() {
    return (
      <div
        style={{
          width: `${this.defaultWidth}px`,
        }}
        class={[
          'alarm-retrieval-filter-component__selector-trigger',
          { 'right-split': this.hasRightSplit },
          { 'is-error': this.isError },
        ]}
        v-bk-tooltips={{
          content: this.tips,
          disabled: !this.tips,
          delay: 500,
        }}
        onClick={this.click}
        onMousedown={this.mouseDown}
      >
        <div class='trigger-top-wrap'>{this.$slots?.top?.()}</div>
        <div class='trigger-bottom-wrap'>
          <span class='bottom-text'>{this.$slots?.bottom?.()}</span>
          <div class={['down-btn', { active: this.active }]}>
            <span class='icon-monitor icon-mc-triangle-down' />
          </div>
        </div>
      </div>
    );
  },
});
