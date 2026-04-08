/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { DatePicker } from '@blueking/date-picker';

import { getDefaultTimezone, updateTimezone } from '../../i18n/dayjs';

import type { TimeRangeType } from './utils';

import '@blueking/date-picker/vue3/vue3.css';

/**
 * 图表选择时间范围组件
 */
export default defineComponent({
  name: 'TimeRange',
  props: {
    modelValue: {
      type: Array as PropType<TimeRangeType>,
      default: () => [],
    },
    timezone: {
      type: String,
      default: getDefaultTimezone(),
    },
    needTimezone: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['update:timezone', 'update:modelValue'],
  setup(_, { emit }) {
    const handleChange = (value: any[]) => {
      emit('update:modelValue', value);
    };
    const handleTimezoneChange = (value: string) => {
      updateTimezone(value);
      emit('update:timezone', value);
    };
    return {
      handleChange,
      handleTimezoneChange,
    };
  },
  render() {
    return (
      <DatePicker
        class='time-range-date-picker'
        behavior='simplicity'
        modelValue={this.modelValue}
        needTimezone={this.needTimezone}
        timezone={this.timezone}
        onUpdate:modelValue={this.handleChange}
        onUpdate:timezone={this.handleTimezoneChange}
      />
    );
  },
});
