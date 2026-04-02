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

import { IssuePriorityEnum, ISSUES_PRIORITY_MAP } from '../../../constant';

import type { IssuePriorityType } from '../../../typing';

import './priority-menu.scss';

/** 优先级选项列表 */
const PRIORITY_OPTIONS: IssuePriorityType[] = [IssuePriorityEnum.P0, IssuePriorityEnum.P1, IssuePriorityEnum.P2];

export default defineComponent({
  name: 'PriorityMenu',
  props: {
    /** 当前选中的优先级 */
    currentPriority: {
      type: String as PropType<IssuePriorityType>,
      required: true,
    },
  },
  emits: {
    select: (priority: IssuePriorityType) => !!priority,
  },
  setup(props, { emit }) {
    /**
     * @description 处理优先级选项点击，与当前优先级相同时不触发事件
     * @param {IssuePriorityType} priority - 被点击的优先级
     * @returns {void}
     */
    const handleSelect = (priority: IssuePriorityType) => {
      if (priority === props.currentPriority) return;
      emit('select', priority);
    };

    return {
      handleSelect,
    };
  },
  render() {
    return (
      <div class='issues-priority-menu'>
        {PRIORITY_OPTIONS.map(priority => {
          const config = ISSUES_PRIORITY_MAP[priority];
          const isActive = this.currentPriority === priority;
          return (
            <div
              key={priority}
              class={['priority-menu-item', { 'is-active': isActive }]}
              onClick={() => this.handleSelect(priority)}
            >
              <span
                style={{
                  backgroundColor: config.bgColor,
                  color: config.color,
                }}
                class='priority-tag'
              >
                {config.alias}
              </span>
            </div>
          );
        })}
      </div>
    );
  },
});
