import SampleColumnSelect from '@/features/collection/shared/sample-column-select';
/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { computed, defineComponent, nextTick, reactive, ref, watch, type PropType } from 'vue';
import { Form, FormItem, Input, InputNumber } from 'tdesign-vue-next';
import type { FormInstanceFunctions, FormRules, InputProps } from 'tdesign-vue-next';
import i18n from '@/platform/i18n/i18n';
import './validator-input.scss';

interface FilterRow {
  fieldindex?: string;
  word?: string;
}
interface FilterOption {
  id: string;
  name: string;
  value?: string;
}

export default defineComponent({
  name: 'LogFilterValidatorInput',
  compatConfig: { MODE: 3 },
  props: {
    value: { type: String, default: '' },
    placeholder: { type: String, default: '' },
    activeType: { type: String, default: '' },
    inputType: { type: String as PropType<NonNullable<InputProps['type']>>, default: 'text' },
    rowData: { type: Object as PropType<FilterRow>, default: () => ({}) },
    originalFilterItemSelect: { type: Array as PropType<FilterOption[]>, default: () => [] },
    tableIndex: Number,
  },
  emits: { change: (_value: string) => true },
  setup(props, { emit, expose }) {
    const editing = ref(false);
    const input = ref<{ focus(): void }>();
    const form = ref<FormInstanceFunctions<{ inputValue: string }>>();
    const data = reactive({ inputValue: props.value });
    watch(
      () => props.value,
      (value) => {
        data.inputValue = value;
      },
    );
    watch(
      () => data.inputValue,
      (value) => {
        emit('change', value);
      },
    );
    const showInput = computed(() => editing.value || !data.inputValue);
    const hasOptions = computed(() => props.originalFilterItemSelect.length > 0);
    const selectedLabel = computed(
      () => props.originalFilterItemSelect.find((item) => item.id === data.inputValue)?.name,
    );
    // Preserve V2's paired fieldindex/word validation, including match mode.
    function checkValidator() {
      const { fieldindex, word } = props.rowData;
      return !!(!(fieldindex || word) || (fieldindex && word) || data.inputValue || props.activeType === 'match');
    }
    const rules = computed<FormRules<typeof data>>(() => ({
      inputValue: [
        {
          validator: checkValidator,
          message: i18n.t('必填项'),
          trigger: 'blur',
        },
      ],
    }));
    async function validate(): Promise<boolean> {
      if (!form.value) return true;
      try {
        return (await form.value.validate()) === true;
      } catch {
        return false;
      }
    }
    async function edit() {
      editing.value = true;
      await nextTick();
      input.value?.focus();
    }
    function change(value: string | number | undefined) {
      data.inputValue = value === undefined ? '' : String(value);
    }
    expose({ validate });
    function formInput() {
      return (
        <Form ref={form} data={data} rules={rules.value} layout='inline' labelWidth={0}>
          <FormItem name='inputValue' label=''>
            {props.inputType === 'number' ? (
              <InputNumber
                largeNumber
                ref={input}
                value={data.inputValue}
                min={1}
                theme='normal'
                allowInputOverLimit={false}
                placeholder={props.placeholder}
                onChange={change}
                onFocus={() => {
                  editing.value = true;
                }}
                onBlur={() => {
                  editing.value = false;
                }}
              />
            ) : (
              <Input
                ref={input}
                value={data.inputValue}
                type={props.inputType}
                clearable
                placeholder={props.placeholder}
                onChange={change}
                onFocus={() => {
                  editing.value = true;
                }}
                onBlur={() => {
                  editing.value = false;
                }}
              />
            )}
          </FormItem>
        </Form>
      );
    }
    function trigger(isSelect = false) {
      return (
        <div class={{ 'input-trigger': true, 'none-border': showInput.value }} onClick={edit}>
          {showInput.value ? (
            formInput()
          ) : (
            <div class='input-box'>
              <span class='input-value overflow-tips' title={isSelect ? selectedLabel.value : undefined}>
                {(isSelect && selectedLabel.value) || i18n.t('第{n}行', { n: data.inputValue })}
              </span>
            </div>
          )}
        </div>
      );
    }
    return () => (
      <div class='bklog-log-filter form-input'>
        {hasOptions.value ? (
          <SampleColumnSelect value={data.inputValue} options={props.originalFilterItemSelect} onChange={change}>
            {() => trigger(true)}
          </SampleColumnSelect>
        ) : props.inputType !== 'number' ? (
          formInput()
        ) : (
          trigger()
        )}
      </div>
    );
  },
});
