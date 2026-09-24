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
import { defineComponent } from 'vue';

import './profiling-empty-state.scss';

export default defineComponent({
  name: 'ProfilingEmptyState',
  props: {
    icon: { type: String, required: true },
    title: { type: String, required: true },
    description: { type: String, required: true },
    hint: { type: String, default: '' },
  },
  render() {
    return (
      <section class='profiling-empty-state'>
        <div class='profiling-empty-state-content'>
          <div
            class='profiling-empty-state-icon'
            aria-hidden='true'
          >
            <i class={`icon-monitor icon-${this.icon}`} />
          </div>
          <h2>{this.title}</h2>
          <p class='profiling-empty-state-description'>{this.description}</p>
          <div class='profiling-empty-state-actions'>{this.$slots.default?.()}</div>
          {this.hint && <p class='profiling-empty-state-hint'>{this.hint}</p>}
          {this.$slots.footer && <div class='profiling-empty-state-footer'>{this.$slots.footer()}</div>}
        </div>
      </section>
    );
  },
});
