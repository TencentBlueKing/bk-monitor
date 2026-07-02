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

import { type PropType, defineComponent, shallowReactive, shallowRef, toValue, watch } from 'vue';

// import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import EditInput from './components/edit-input/edit-input';
import EditRichEdit from './components/edit-rich-edit/edit-rich-edit';
import EditSelect from './components/edit-select/edit-select';
import EditUserChooser from './components/edit-user-chooser/edit-user-chooser';
import { type IField, EditType, FULL_FIELD_TYPES } from './typing';

import './tapd-field-form.scss';

type TComponentType = typeof EditInput | typeof EditRichEdit | typeof EditSelect | typeof EditUserChooser;

export default defineComponent({
  name: 'TapdFieldForm',
  props: {
    fields: {
      type: Array as PropType<IField[]>,
      default: () => [],
    },
    value: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
  },
  emits: {
    change: (_val: Record<string, unknown>) => true,
  },
  setup(props, { emit }) {
    const compRefMap = shallowRef<Map<string, InstanceType<TComponentType>>>(new Map());
    const { t } = useI18n();
    /** 按字段列表初始化表单值，后续由 handleChangeValue 响应式更新 */
    const fieldValue = shallowReactive<Record<string, unknown>>(
      Object.fromEntries(props.fields.map(f => [f.field_id, props.value?.[f.field_id] || '']))
    );
    watch(
      () => props.value,
      (newVal, oldVal) => {
        if (JSON.stringify(newVal) !== JSON.stringify(oldVal)) {
          for (const key in newVal) {
            if (typeof fieldValue[key] !== 'undefined') {
              fieldValue[key] = newVal[key];
            }
          }
        }
      },
      {
        immediate: true,
      }
    );

    const handleChangeValue = (key: string, value: unknown) => {
      fieldValue[key] = value;
      emit('change', toValue(fieldValue));
    };

    const validate = async () => {
      let isVaild = true;
      for (const field of props.fields) {
        const component = compRefMap.value.get(field.field_id);
        const success = component.validate();
        isVaild = isVaild && success;
      }
      return isVaild;
    };

    const setCompRef = (id: string, el: InstanceType<TComponentType> | null) => {
      compRefMap.value.set(id, el);
    };

    return {
      fieldValue,
      validate,
      t,
      handleChangeValue,
      setCompRef,
    };
  },
  render() {
    const formItem = (field: IField, content: () => JSX.Element) => {
      const isHalf = !FULL_FIELD_TYPES.includes(field.field_type);
      const key = field.field_id;
      return (
        <div
          key={key}
          class={['form-item', { 'form-item--half': isHalf }]}
        >
          <div class={['form-item-title', { required: !!field.is_required }]}>
            <span>{field.field_name}</span>
          </div>
          {content()}
        </div>
      );
    };
    return (
      <div class='tapd-field-form-component'>
        <span class='form-header mb-24'>
          <span class='form-header-title'>{this.t('单据字段')}</span>
          {/* <Button
            theme='primary'
            text
          >
            <span class='icon-monitor icon-configuration' />
            {this.t('管理字段')}
          </Button> */}
        </span>
        <div class='form-grid'>
          {this.fields.map(field => {
            const value = (this.fieldValue?.[field.field_id] as string) || '';
            if (field.field_type === EditType.input) {
              return formItem(field, () => (
                <EditInput
                  ref={el => this.setCompRef(field.field_id, el)}
                  modelValue={value}
                  required={field.is_required}
                  onUpdate:modelValue={val => this.handleChangeValue(field.field_id, val)}
                />
              ));
            }
            if (field.field_type === EditType.richEdit) {
              return formItem(field, () => (
                <EditRichEdit
                  ref={el => this.setCompRef(field.field_id, el)}
                  modelValue={value}
                  required={field.is_required}
                  onUpdate:modelValue={val => this.handleChangeValue(field.field_id, val)}
                />
              ));
            }
            if (field.field_type === EditType.userChooser) {
              return formItem(field, () => (
                <EditUserChooser
                  ref={el => this.setCompRef(field.field_id, el)}
                  modelValue={value}
                  required={field.is_required}
                  onUpdate:modelValue={val => this.handleChangeValue(field.field_id, val)}
                />
              ));
            }
            if (field.field_type === EditType.select) {
              return formItem(field, () => (
                <EditSelect
                  ref={el => this.setCompRef(field.field_id, el)}
                  modelValue={value}
                  options={field?.options || []}
                  required={field.is_required}
                  onUpdate:modelValue={val => this.handleChangeValue(field.field_id, val)}
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
