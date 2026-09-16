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
import { defineComponent, shallowRef } from 'vue';

import './collapse-section.scss';

/** 输入 / 输出分区折叠面板 */
export default defineComponent({
  name: 'LlmCollapseSection',
  props: {
    /** 分区标题 */
    title: {
      type: String,
      required: true,
    },
    /** 分区条目数量 */
    count: {
      type: Number,
      default: 0,
    },
    /** 标题左侧图标 class */
    icon: {
      type: String,
      default: '',
    },
    /** 初始化时是否展开 */
    defaultExpand: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { slots }) {
    const expanded = shallowRef(props.defaultExpand);

    return () => (
      <div class='llm-collapse-section'>
        <div
          class={['llm-collapse-section-header', { 'is-collapsed': !expanded.value }]}
          onClick={() => {
            expanded.value = !expanded.value;
          }}
        >
          <div class='llm-collapse-section-title'>
            {props.icon ? <i class={['icon-monitor', 'llm-collapse-section-icon', props.icon]} /> : null}
            <span class='llm-collapse-section-label'>{props.title}</span>
            <span class='llm-collapse-section-count'>{props.count}</span>
          </div>
          <i class='icon-monitor icon-arrow-down llm-collapse-section-arrow' />
        </div>
        {expanded.value ? <div class='llm-collapse-section-body'>{slots.default?.()}</div> : null}
      </div>
    );
  },
});
