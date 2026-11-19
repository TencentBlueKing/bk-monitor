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

import { defineComponent, computed, type PropType } from 'vue';
import { DateRangePicker, type DateRangeValue } from 'tdesign-vue-next';

import useLocale from '@/shared/composables/use-locale';

import './file-date-picker.scss';

export default defineComponent({
  name: 'FileDatePicker',
  props: {
    timeRange: {
      type: String,
      required: true,
    },
    timeValue: {
      type: Array as PropType<string[]>,
      required: true,
    },
  },
  emits: ['update:timeRange', 'update:timeValue'],

  setup(props, { emit }) {
    const { t } = useLocale();

    // 时间常量
    const oneDay = 1000 * 60 * 60 * 24;
    const oneWeek = oneDay * 7;
    const oneMonth = oneDay * 30;

    // 快捷选项配置
    const shortcuts = computed<Array<{ text: string; value: () => [Date, Date] }>>(() => [
      {
        text: t('近一天'),
        value() {
          const end = new Date();
          const start = new Date();
          start.setTime(start.getTime() - oneDay);
          return [start, end];
        },
      },
      {
        text: t('近一周'),
        value() {
          const end = new Date();
          const start = new Date();
          start.setTime(start.getTime() - oneWeek);
          return [start, end];
        },
      },
      {
        text: t('近一月'),
        value() {
          const end = new Date();
          const start = new Date();
          start.setTime(start.getTime() - oneMonth);
          return [start, end];
        },
      },
      {
        text: t('所有'),
        value() {
          const end = new Date();
          const start = new Date('2000-01-01');
          return [start, end];
        },
      },
    ]);

    // 短文本枚举映射
    const shortTextEnum = computed<Record<string, string>>(() => ({
      [t('近一天')]: '1d',
      [t('近一周')]: '1w',
      [t('近一月')]: '1m',
      [t('所有')]: 'all',
      '1d': t('近一天'),
      '1w': t('近一周'),
      '1m': t('近一月'),
      all: t('所有'),
    }));

    const presets = computed(() => Object.fromEntries(shortcuts.value.map(item => [item.text, item.value])));
    const shortText = computed(() => shortTextEnum.value[props.timeRange]);

    // 处理日期变化
    const handleDateChange = (date: DateRangeValue, context: { trigger?: string }) => {
      emit('update:timeValue', date);
      if (context.trigger !== 'preset') emit('update:timeRange', 'custom');
    };

    // 处理快捷键变化
    const handlePresetClick = ({ preset }: { preset: Record<string, unknown> }) => {
      emit('update:timeRange', shortTextEnum.value[Object.keys(preset)[0]]);
    };

    // 主渲染函数
    return () => (
      <DateRangePicker
        class={['king-date-picker', 'file-date-picker', { 'has-shortcut': !!shortText.value }]}
        rangeInputProps={shortText.value ? { inputProps: [{ value: shortText.value }, { value: '' }] } : {}}
        clearable={false}
        enableTimePicker
        format='YYYY-MM-DD HH:mm:ss'
        valueType='YYYY-MM-DD HH:mm:ss'
        placeholder={[t('开始时间'), t('结束时间')]}
        presets={presets.value}
        presetsPlacement='left'
        value={props.timeValue}
        onPresetClick={handlePresetClick}
        onChange={handleDateChange}
      />
    );
  },
});
