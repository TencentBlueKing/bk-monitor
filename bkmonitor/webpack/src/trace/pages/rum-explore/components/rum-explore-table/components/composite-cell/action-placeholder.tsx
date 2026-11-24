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
import { computed, defineComponent } from 'vue';

export default defineComponent({
  name: 'RumCompositeActionPlaceholder',
  props: {
    /** 已有图标库中的图标类名。 */
    icon: { type: String, required: true },
    /** 入口名称，同时用作无障碍标签。 */
    label: { type: String, required: true },
    /** 是否在图标旁展示入口名称。 */
    showLabel: { type: Boolean, default: true },
  },
  setup(props) {
    const iconClass = computed(() => `icon-monitor ${props.icon}`);
    return { iconClass };
  },
  render() {
    return (
      <button
        class='rum-composite-action'
        aria-label={this.label}
        disabled={true}
        type='button'
      >
        {this.showLabel && this.label}
        <i
          class={this.iconClass}
          aria-hidden='true'
        />
      </button>
    );
  },
});
