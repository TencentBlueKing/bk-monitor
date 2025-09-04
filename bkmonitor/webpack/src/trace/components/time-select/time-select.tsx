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
import { type PropType, defineComponent, ref } from 'vue';

import { Input, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './time-select.scss';

export interface ITimeListItem {
  id: string;
  name: string;
}
export default defineComponent({
  name: 'TimeSelect',
  props: {
    list: {
      type: Array as PropType<ITimeListItem[]>,
      required: true,
    },
    value: {
      type: String,
      required: true,
    },
    tip: {
      type: String,
      default: '',
    },
  },
  emits: ['change', 'addItem'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const customTimeVal = ref('');
    const showCustomTime = ref(false);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (/enter/i.test(e.code) && /^([1-9][0-9]+)+(m|h|d|w|M|y)$/.test(customTimeVal.value)) {
        if (props.list.every(item => item.id !== customTimeVal.value)) {
          emit('addItem', {
            id: customTimeVal.value,
            name: customTimeVal.value,
          });
        }
        emit('change', customTimeVal.value);
        customTimeVal.value = '';
        showCustomTime.value = false;
      }
    };

    const handleChange = (v: string) => {
      customTimeVal.value = '';
      emit('change', v);
    };

    return () => (
      <div class='time-select'>
        <Select
          clearable={false}
          modelValue={props.value}
          onUpdate:modelValue={handleChange}
        >
          {props.list.map(item => (
            <Select.Option
              id={item.id}
              key={item.id}
              name={item.name}
            >
              {item.name}
            </Select.Option>
          ))}
          <div class='time-select-custom'>
            {showCustomTime.value ? (
              <span class='time-input-wrap'>
                <Input
                  v-model={customTimeVal.value}
                  size='small'
                  onKeydown={handleKeyDown}
                />
                <span
                  class='help-icon icon-monitor icon-mc-help-fill'
                  v-bk-tooltips={{
                    allowHTML: false,
                    content: props.tip || t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年'),
                  }}
                />
              </span>
            ) : (
              <span
                class='custom-text'
                onClick={() => (showCustomTime.value = !showCustomTime.value)}
              >
                {t('自定义')}
              </span>
            )}
          </div>
        </Select>
      </div>
    );
  },
});
