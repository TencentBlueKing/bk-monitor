import { type PropType, defineComponent } from 'vue';

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
import UserSelector from 'trace/components/user-selector/user-selector';

import { useValidate } from '../../hooks/use-validate';
import { EditType } from '../../typing';

import './edit-user-chooser.scss';

export default defineComponent({
  name: 'EditUserChooser',
  props: {
    /**
     * 选中的用户ID列表
     */
    modelValue: {
      type: [Array, String] as PropType<string | string[]>,
      default: () => [],
    },
    required: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'update:modelValue': (value: string[]) => Array.isArray(value),
  },
  setup(props, { emit }) {
    const { errMsg, validate } = useValidate<string | string[]>(() => ({
      fieldType: EditType.userChooser,
      required: props.required,
      value: props.modelValue,
    }));
    const handleInput = val => {
      emit('update:modelValue', val);
    };
    const handleBlur = () => {
      validate();
    };
    const handleFocus = () => {
      errMsg.value = '';
    };
    return {
      errMsg,
      validate,
      handleInput,
      handleBlur,
      handleFocus,
    };
  },
  render() {
    return (
      <div class={['field-form-edit-user-chooser', { 'is-error': !!this.errMsg }]}>
        <UserSelector
          modelValue={this.modelValue}
          onBlur={this.handleBlur}
          onFocus={this.handleFocus}
          onUpdate:modelValue={this.handleInput}
        />
        {this.errMsg ? <span class='err-msg'>{this.errMsg}</span> : undefined}
      </div>
    );
  },
});
