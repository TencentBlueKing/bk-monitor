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

import SampleColumnSelect from '@/features/collection/shared/sample-column-select';

import { defineComponent, ref, reactive, computed, watch, nextTick, type PropType } from 'vue';
import { Form as TForm, FormItem as TFormItem, Input as TInput, InputNumber as TInputNumber } from 'tdesign-vue-next';
import type { FormRules, InputProps } from 'tdesign-vue-next';

import useLocale from '@/shared/composables/use-locale';

import './validator-input.scss';

type IProps = {
  tableIndex?: number;
  value: string;
  placeholder: string;
  activeType: string;
  inputType: string;
  rowData: any;
  originalFilterItemSelect: { id: string; name: string; value?: string }[];
};

/**
 * 校验输入框
 */
export default defineComponent({
  name: 'ValidatorInput',
  compatConfig: { MODE: 3 },
  props: {
    tableIndex: Number,
    value: {
      type: String,
      default: '',
    },
    placeholder: {
      type: String,
      default: '',
    },
    activeType: {
      type: String,
      default: '',
    },
    inputType: {
      type: String,
      default: 'text',
    },
    rowData: {
      type: Object,
      default: () => ({}),
    },
    originalFilterItemSelect: {
      type: Array as PropType<IProps['originalFilterItemSelect']>,
      default: () => [],
    },
  },
  emits: ['change'],
  setup(props: IProps, { emit, expose }) {
    const { t } = useLocale();
    // 引用
    const inputRef = ref<{ focus(): void }>();
    const validateFormRef = ref<any>(null);

    // 响应式数据
    const isClick = ref(false);
    const isError = ref(false);
    const formData = reactive({
      inputValue: '',
    });
    const checkValidator = () => {
      const { fieldindex, word } = props.rowData;
      if (!(fieldindex || word) || (fieldindex && word) || formData.inputValue || props.activeType === 'match') {
        return true;
      }
      return false;
    };

    // 验证规则
    const rules: FormRules<typeof formData> = {
      inputValue: [
        {
          validator: checkValidator,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
    };

    // 计算属性
    const isShowSelect = computed(() => {
      return !!props.originalFilterItemSelect.length;
    });

    const selectedShowStr = computed(() => {
      return props.originalFilterItemSelect.find((item: any) => item.id === formData.inputValue)?.name;
    });

    const isShowFormInput = computed(() => {
      return isClick.value || !formData.inputValue;
    });

    // Watchers
    watch(
      () => formData.inputValue,
      () => {
        handleEmitModel();
      },
    );

    watch(
      () => props.value,
      (newVal) => {
        formData.inputValue = newVal;
      },
      { immediate: true },
    );

    // 方法
    const handleEmitModel = () => {
      emit('change', formData.inputValue);
    };

    /**
     * 校验value是否为空
     * @returns {boolean} 校验是否通过，true表示通过，false表示失败
     */
    const validateValue = (): boolean => {
      const isEmpty = !formData.inputValue || !String(formData.inputValue).trim();
      isError.value = isEmpty;
      return !isEmpty;
    };

    const handleClickInput = () => {
      isClick.value = true;
      nextTick(() => {
        inputRef.value?.focus();
      });
    };

    const blurInput = () => {
      isClick.value = false;
      // 失焦时自动校验
      validateValue();
    };

    // 暴露方法给父组件
    expose({
      validateValue,
    });

    function updateInput(value: string | number | undefined) {
      const next = value === undefined ? '' : String(value);
      formData.inputValue = next;
      if (isError.value && next && next.trim()) isError.value = false;
    }

    // 渲染辅助函数
    const inputTriggerSlot = (isSelect = false) => (
      <div
        class={{
          'input-trigger': true,
          'none-border': isShowFormInput.value,
          'input-error': isError.value,
        }}
        onClick={handleClickInput}
      >
        {isShowFormInput.value ? (
          formInput()
        ) : (
          <div class='input-box'>
            <span
              class='input-value overflow-tips'
              title={isSelect ? selectedShowStr.value : t('第{n}行', { n: formData.inputValue })}
            >
              {isSelect
                ? `${selectedShowStr.value || t('第{n}行', { n: formData.inputValue })}`
                : t('第{n}行', { n: formData.inputValue })}
            </span>
          </div>
        )}
      </div>
    );

    const formInput = () => (
      <TForm
        ref={validateFormRef}
        class='form-main'
        layout='inline'
        labelWidth={0}
        {...{
          ...{
            data: formData,
            rules,
          },
        }}
      >
        <TFormItem label='' name='inputValue'>
          {props.inputType === 'number' ? (
            <TInputNumber
              largeNumber
              ref={inputRef}
              value={formData.inputValue}
              min={1}
              theme='normal'
              placeholder={props.placeholder}
              class={{ 'validate-input': true, 'input-error': isError.value }}
              onFocus={() => {
                isClick.value = true;
              }}
              onBlur={blurInput}
              onChange={updateInput}
            />
          ) : (
            <TInput
              ref={inputRef}
              value={formData.inputValue}
              type={props.inputType as InputProps['type']}
              placeholder={props.placeholder}
              class={{ 'validate-input': true, 'input-error': isError.value }}
              clearable
              onFocus={() => {
                isClick.value = true;
              }}
              onBlur={blurInput}
              onChange={updateInput}
            />
          )}
        </TFormItem>
      </TForm>
    );

    const renderMain = () => (props.inputType !== 'number' ? formInput() : inputTriggerSlot());

    return () => (
      <div class='validator-input-main'>
        {isShowSelect.value ? (
          <SampleColumnSelect
            class={{ 'input-error': isError.value }}
            value={formData.inputValue}
            options={props.originalFilterItemSelect}
            onChange={(value) => {
              formData.inputValue = value;
              if (isError.value && value) isError.value = false;
            }}
          >
            {() => inputTriggerSlot(true)}
          </SampleColumnSelect>
        ) : (
          renderMain()
        )}
      </div>
    );
  },
});
