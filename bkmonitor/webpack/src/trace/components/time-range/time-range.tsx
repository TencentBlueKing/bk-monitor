/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { defineComponent, PropType } from 'vue';
import { DatePicker } from '@blueking/date-picker';
import dayjs from 'dayjs';

import { updateTimezone } from '../../i18n/dayjs';

import { TimeRangeType } from './utils';

import '@blueking/date-picker/dist/vue3-light.css';

/**
 * 图表选择时间范围组件
 */
export default defineComponent({
  name: 'TimeRange',
  props: {
    modelValue: {
      type: Array as PropType<TimeRangeType>,
      default: () => []
    },
    timezone: {
      type: String,
      default: window.timezone
    },
    needTimezone: {
      type: Boolean,
      default: true
    }
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
      handleTimezoneChange
    };
  },
  render() {
    console.info(this.modelValue, '----------')
    return (
      <DatePicker
        class='time-range-date-picker'
        behavior='simplicity'
        modelValue={this.modelValue}
        timezone={this.timezone}
        needTimezone={this.needTimezone}
        onUpdate:modelValue={this.handleChange}
        onUpdate:timezone={this.handleTimezoneChange}
      />
    );
  }
});
