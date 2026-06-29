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
import { defineComponent } from 'vue';

import { Input } from 'bkui-vue';

import { useValidate } from '../../hooks/use-validate';
import { EditType } from '../../typing';

import './edit-input.scss';

export default defineComponent({
  name: 'EditInput',
  props: {
    modelValue: {
      type: String,
      default: '',
    },
    placeholder: {
      type: String,
      default: '',
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
    const { errMsg, validate } = useValidate<string>(() => ({
      fieldType: EditType.input,
      required: props.required,
      value: props.modelValue,
    }));

    /**
     * @description 输入
     * @param val
     */
    const handleInput = val => {
      emit('update:modelValue', val);
    };

    /** 聚焦时清除错误提示 */
    const handleFocus = () => {
      errMsg.value = '';
    };

    /** 失焦时触发必填校验 */
    const handleBlur = () => {
      validate();
    };

    return {
      errMsg,
      handleInput,
      validate,
      handleFocus,
      handleBlur,
    };
  },
  render() {
    return (
      <div class={['field-form-edit-input', { 'is-error': !!this.errMsg }]}>
        <Input
          modelValue={this.modelValue}
          placeholder={this.placeholder}
          onBlur={this.handleBlur}
          onFocus={this.handleFocus}
          onUpdate:modelValue={this.handleInput}
        />
        {this.errMsg ? <span class='err-msg'>{this.errMsg}</span> : undefined}
      </div>
    );
  },
});
