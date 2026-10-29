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

import { defineComponent, h, onMounted, ref, type PropType } from 'vue';
import DatePicker from '@blueking/date-picker';
import { updateTimezone } from '../../../platform/i18n/dayjs';
import { DEFAULT_TIME_RANGE } from './utils';
import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';
import useStore from '@/shared/composables/use-store';
import '@blueking/date-picker/vue3/vue3.css';

// The official Vue3 component consumes modelValue/update:modelValue. Keep that
// contract when it is rendered inside the temporary Vue2 compatibility host.
// This metadata is ignored by the final native Vue3 runtime.
Object.assign(DatePicker, { compatConfig: { MODE: 3 } });

export type TimeRangeType = [string, string];
type TimeRangeDisplayType = 'normal' | 'simplicity';

export default defineComponent({
  compatConfig: { MODE: 3 },
  name: 'TimeRange',
  props: {
    value: { type: Array as unknown as PropType<TimeRangeType>, default: () => DEFAULT_TIME_RANGE },
    type: { type: String as PropType<TimeRangeDisplayType>, default: 'simplicity' },
    timezone: { type: String, default: () => window.timezone },
    needTimezone: { type: Boolean, default: true },
    maxDuration: Number,
  },
  emits: ['change', 'format-change', 'timezone-change', "formatChange", "timezoneChange"],
  setup(props, { emit, expose }) {
    const store = useStore();
    const datePicker = ref();
    const formatStr = ref(store.getters.retrieveParams.format);
    onMounted(() => store.commit('retrieve/updateCachePickerValue', props.value));
    function handleModelValueChange(value: TimeRangeType) {
      if (value.every(item => typeof item === 'string'))
        localStorage.setItem('SEARCH_DEFAULT_TIME', JSON.stringify(value));
      store.commit('updateStorage', { [BK_LOG_STORAGE.CACHED_BATCH_LIST]: [] });
      store.commit('retrieve/updateCachePickerValue', props.value);
      emit('change', value);
    }
    function handleFormatChange(value: string) {
      formatStr.value = value;
      localStorage.setItem('SEARCH_DEFAULT_TIME_FORMAT', value);
      emit('format-change', value);
    }
    function handleTimezoneChange(timezone: string) {
      if (timezone) updateTimezone(timezone);
      emit('timezone-change', timezone);
    }
    expose({ datePicker, handleModelValueChange, handleFormatChange, handleTimezoneChange });
    return () =>
      h('div', { style: { display: 'inline-flex' } }, [
        h(DatePicker, {
          ref: datePicker,
          behavior: props.type,
          modelValue: props.value,
          needTimezone: props.needTimezone,
          enableFormatClick: true,
          timezone: props.timezone,
          format: formatStr.value,
          maxDuration: props.maxDuration,
          'onUpdate:modelValue': handleModelValueChange,
          'onUpdate:format': handleFormatChange,
          'onUpdate:timezone': handleTimezoneChange,
        }),
      ]);
  },
});
