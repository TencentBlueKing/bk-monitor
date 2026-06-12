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

import { type PropType, defineComponent, shallowRef, watchEffect } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import EditPinyinUserChooser from './edit-components/edit-pinyinuserchooser/edit-pinyinuserchooser';
import EditText from './edit-components/edit-text/edit-text';
import EditTextarea from './edit-components/edit-textarea/edit-textarea';
import { mockFields } from './mock';
import { type IField, EditType } from './typing';

import './tapd-field-form.scss';

export default defineComponent({
  name: 'TapdFieldForm',
  props: {
    fields: {
      type: Array as PropType<IField[]>,
      default: () => mockFields,
    },
    value: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    const fieldValue = shallowRef({});

    watchEffect(() => {
      const obj = {};
      for (const field of props.fields) {
        if (field.editabled_type === EditType.text) {
          obj[field.system_name] = fieldValue.value?.[field.system_name] || '';
        }
      }
      fieldValue.value = obj;
    });

    const handleChangeValue = (key, value) => {
      const obj = {
        ...fieldValue.value,
        [key]: value,
      };
      console.log(obj);
      fieldValue.value = obj;
    };

    return {
      fieldValue,
      t,
      handleChangeValue,
    };
  },
  render() {
    const formItem = (field: IField, content: () => JSX.Element) => {
      const isHalf = field.span === 'half';
      const key = field.system_name;
      return (
        <div
          key={key}
          class={['form-item', { 'form-item--half': isHalf }]}
        >
          <div class={['form-item-title', { required: !!field.required }]}>
            <span>{field?.fieldName || key}</span>
          </div>
          {content()}
        </div>
      );
    };
    return (
      <div class='tapd-field-form-component'>
        <span class='form-header mb-24'>
          <span class='form-header-title'>{this.t('单据字段')}</span>
          <Button
            theme='primary'
            text
          >
            <span class='icon-monitor icon-configuration' />
            {this.t('管理字段')}
          </Button>
        </span>
        <div class='form-grid'>
          {this.fields.map(field => {
            const value = this.fieldValue?.[field.system_name];
            if (field.editabled_type === EditType.text) {
              return formItem(field, () => (
                <EditText
                  modelValue={value}
                  placeholder={field?.placeholder || ''}
                  onUpdate:modelValue={val => this.handleChangeValue(field.system_name, val)}
                />
              ));
            }
            if (field.editabled_type === EditType.textarea) {
              return formItem(field, () => (
                <EditTextarea
                  modelValue={value}
                  onUpdate:modelValue={val => this.handleChangeValue(field.system_name, val)}
                />
              ));
            }
            if (field.editabled_type === EditType.pinyinUserChooser) {
              return formItem(field, () => (
                <EditPinyinUserChooser
                  modelValue={value}
                  onUpdate:modelValue={val => this.handleChangeValue(field.system_name, val)}
                />
              ));
            }
            return null;
          })}
        </div>
      </div>
    );
  },
});
