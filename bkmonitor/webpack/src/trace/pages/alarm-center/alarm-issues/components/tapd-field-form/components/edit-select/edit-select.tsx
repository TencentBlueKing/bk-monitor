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

import { useValidate } from '../../hooks/use-validate';
import { EditType } from '../../typing';

import './edit-select.scss';

interface IOption {
  color?: string;
  id: string;
  name: string;
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
    required: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'update:modelValue': (_val: string) => typeof _val === 'string',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const { errMsg, validate } = useValidate<string>(() => ({
      fieldType: EditType.select,
      required: props.required,
      value: props.modelValue,
    }));
    const allOptions = computed(() => {
      return [
        {
          color: '',
          name: `-${t('空')}-`,
          id: '',
        },
        ...props.options,
      ];
    });

    const handleInput = val => {
      emit('update:modelValue', val);
    };

    const handleToggle = val => {
      console.log(val);
      if (val) {
        errMsg.value = '';
      } else {
        validate();
      }
    };

    return {
      errMsg,
      allOptions,
      handleInput,
      validate,
      handleToggle,
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
      <div class={['field-form-edit-select', { 'is-error': !!this.errMsg }]}>
        <Select
          popoverOptions={{
            extCls: 'field-form-edit-select-popover',
          }}
          allowEmptyValues={['']}
          clearable={false}
          modelValue={this.modelValue}
          multipleMode='tag'
          onToggle={this.handleToggle}
          onUpdate:modelValue={this.handleInput}
        >
          {{
            tag: ({ selected }) =>
              selected.length
                ? selected.map(item => {
                    const color = this.allOptions.find(opt => opt.id === item.value)?.color;
                    return color ? tagRender(color, item.label) : item.label;
                  })
                : this.allOptions[0].name,
            default: () =>
              this.allOptions.map(item => (
                <Select.Option
                  id={item.id}
                  key={`__${item.id}`}
                  name={item.name}
                >
                  {item.color ? tagRender(item.color, item.name) : item.name}
                </Select.Option>
              )),
          }}
        </Select>
        {this.errMsg ? <span class='err-msg'>{this.errMsg}</span> : undefined}
      </div>
    );
  },
});
