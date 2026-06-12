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

import { type PropType, computed, defineComponent } from 'vue';

import { Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

interface IOption {
  color: string;
  label: string;
  value: string;
}

export default defineComponent({
  name: 'EditSelect',
  props: {
    modelValue: {
      type: String,
      default: '',
    },
    options: {
      type: Array as PropType<IOption[]>,
      default: () => [],
    },
  },
  emits: {
    'update:modelValue': (_val: string) => typeof _val === 'string',
  },
  setup(_props, { emit }) {
    const { t } = useI18n();
    const allOptions = computed(() => {
      return [
        {
          color: '',
          label: `-${t('空')}-`,
          value: '',
        },
        ..._props.options,
      ];
    });

    const handleInput = val => {
      emit('update:modelValue', val);
    };
    return {
      allOptions,
      handleInput,
    };
  },
  render() {
    const tagRender = (color, label) => {
      return (
        <span
          style={`height: 20px;
      line-height: 20px;
      padding: 0 6px;
      border-radius: 4px;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      box-sizing: border-box;
      display: inline-block;
      position: relative;
      line-height: 18px;
      color: #fff;
      font-size: 12px;background-color: ${color}`}
        >
          {label}
        </span>
      );
    };
    return (
      <div class='field-form-edit-select'>
        <Select
          popoverOptions={{
            extCls: 'field-form-edit-select-popover',
          }}
          modelValue={this.modelValue}
          multipleMode='tag'
          onUpdate:modelValue={this.handleInput}
        >
          {{
            tag: ({ selected }) =>
              selected.map(item => {
                const color = this.allOptions.find(opt => opt.value === item.value)?.color;
                return tagRender(color, item.label);
              }),
            default: () =>
              this.allOptions.map(item => (
                <Select.Option
                  id={item.value}
                  key={`__${item.value}`}
                  name={item.label}
                >
                  {item.color ? tagRender(item.color, item.label) : item.label}
                </Select.Option>
              )),
          }}
        </Select>
      </div>
    );
  },
});
