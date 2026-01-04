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

import { computed, defineComponent, shallowRef, useTemplateRef } from 'vue';

import { Popover } from 'bkui-vue';

import type { PropType } from 'vue';

import './interval-select.scss';
export const CHART_INTERVAL = [
  {
    id: 'auto',
    name: 'Auto',
  },
  {
    id: 60,
    name: '1 min',
  },
  {
    id: 5 * 60,
    name: '5 min',
  },
  {
    id: 60 * 60,
    name: '1 h',
  },
  {
    id: 24 * 60 * 60,
    name: '1 d',
  },
];

export default defineComponent({
  name: 'IntervalSelect',
  props: {
    label: {
      type: String,
      default: '',
    },
    intervalList: {
      type: Array as PropType<{ id: number | string; name: string }[]>,
      default: () => CHART_INTERVAL,
    },
    interval: {
      type: [String, Number],
      default: 'auto',
    },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const intervalPopover = useTemplateRef<InstanceType<typeof Popover>>('intervalPopover');
    const isShow = shallowRef(false);

    const listLabelByIdMap = computed(() => {
      return props.intervalList.reduce((prev, curr) => {
        prev[curr.id] = curr.name;
        return prev;
      }, {});
    });

    const handleIntervalChange = (id: number | string) => {
      emit('change', id);
      intervalPopover.value.hide();
    };

    const handlePopoverChange = (show: boolean) => {
      isShow.value = show;
    };

    return {
      isShow,
      listLabelByIdMap,
      handleIntervalChange,
      handlePopoverChange,
    };
  },
  render() {
    return (
      <div class='interval-select'>
        <span class='interval-label'>{this.label}</span>
        <Popover
          ref='intervalPopover'
          arrow={false}
          placement='bottom'
          theme='light interval-select-popover'
          trigger='click'
          onAfterHidden={() => this.handlePopoverChange(false)}
          onAfterShow={() => this.handlePopoverChange(true)}
        >
          {{
            default: () => (
              <div class={['popover-trigger', this.isShow ? 'is-active' : '']}>
                <span class='trigger-value'>{this.listLabelByIdMap[this.interval] || '--'}</span>
                <i class='icon-monitor icon-arrow-up' />
              </div>
            ),
            content: () => (
              <ul
                ref='menu'
                class='interval-list-menu'
              >
                {this.intervalList.map(item => (
                  <li
                    key={item.id}
                    class={`menu-item ${this.interval === item.id ? 'is-active' : ''}`}
                    onClick={() => this.handleIntervalChange(item.id)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            ),
          }}
        </Popover>
      </div>
    );
  },
});
