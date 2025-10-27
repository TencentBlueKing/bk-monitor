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

import { defineComponent, ref, computed } from 'vue';

import useLocale from '@/hooks/use-locale';

import './file-date-picker.scss';

export default defineComponent({
  name: 'FileDatePicker',
  props: {
    timeRange: {
      type: String,
      required: true,
    },
    timeValue: {
      type: Array,
      required: true,
    },
  },
  emits: ['update:timeRange', 'update:timeValue'],

  setup(props, { emit }) {
    const { t } = useLocale();

    const showDatePicker = ref(false); // 是否显示日期选择器

    // 时间常量
    const oneDay = 1000 * 60 * 60 * 24;
    const oneWeek = oneDay * 7;
    const oneMonth = oneDay * 30;

    // 快捷选项配置
    const shortcuts = computed(() => [
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
    const shortTextEnum = computed(() => ({
      [t('近一天')]: '1d',
      [t('近一周')]: '1w',
      [t('近一月')]: '1m',
      [t('所有')]: 'all',
      '1d': t('近一天'),
      '1w': t('近一周'),
      '1m': t('近一月'),
      all: t('所有'),
    }));

    // 切换日期选择器显示状态
    const togglePicker = () => {
      showDatePicker.value = !showDatePicker.value;
    };

    // 处理打开状态变化
    const handleOpenChange = (state: boolean) => {
      showDatePicker.value = state;
    };

    // 处理日期变化
    const handleDateChange = (date: any) => {
      // if (type !== undefined) console.log('日期选择事件')
      // else console.log('快捷键事件')
      emit('update:timeValue', date);
    };

    // 处理快捷键变化
    const handleShortcutChange = (data: any) => {
      if (data !== undefined) {
        emit('update:timeRange', shortTextEnum.value[data.text]);
      } else {
        emit('update:timeRange', 'custom');
      }
    };

    // 主渲染函数
    return () => (
      <bk-date-picker
        class='king-date-picker'
        scopedSlots={{
          trigger: () =>
            props.timeRange !== 'custom' ? (
              <div
                class='king-date-trigger'
                onClick={(e: Event) => {
                  e.stopPropagation();
                  togglePicker();
                }}
              >
                <div class={['bk-date-picker-editor', { 'is-focus': showDatePicker.value }]}>
                  {shortTextEnum.value[props.timeRange]}
                </div>
                <div class='icon-wrapper'>
                  <span class='bklog-icon bklog-date-picker' />
                </div>
              </div>
            ) : null,
        }}
        clearable={false}
        format='yyyy-MM-dd HH:mm:ss'
        open={showDatePicker.value}
        shortcuts={shortcuts.value}
        type='datetimerange'
        value={props.timeValue}
        shortcut-close
        use-shortcut-text
        on-open-change={handleOpenChange}
        on-shortcut-change={handleShortcutChange}
        onChange={handleDateChange}
      />
    );
  },
});
