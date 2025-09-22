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

import { computed, defineComponent, ref } from 'vue';

import useValidtor, { type Rules } from './use-validtor';

import './index.scss';

export default defineComponent({
  name: 'ValidateInput',
  props: {
    value: {
      type: String,
      default: '',
    },
    rules: {
      type: Array<Rules[number]>,
      default: () => [],
    },
    type: {
      type: String,
      default: 'text',
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    placeholder: {
      type: String,
      default: '',
    },
    clearable: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { emit, expose }) {
    const rootRef = ref<HTMLElement>();
    const localValue = ref(props.value);
    const isBlur = ref(true);

    const isPassword = computed(() => props.type === 'password');

    let oldInputText = '' as number | string;

    const { message: errorMessage, validator } = useValidtor(props.rules);

    const handleFocus = () => {
      isBlur.value = false;
      emit('focus');
    };

    const handleChange = (value: string) => {
      isBlur.value = true;
      localValue.value = value;
      if (props.type === 'number') {
        validator(localValue.value)
          .then(() => {
            emit('error', false);
            emit('submit', value);
          })
          .catch(() => emit('error', true));
      }
    };

    const handleClear = () => {
      localValue.value = '';
      validator('')
        .catch(() => emit('error', true))
        .finally(() => {
          emit('clear');
        });
    };

    // 响应输入
    const handleInput = (value: string) => {
      isBlur.value = false;
      localValue.value = value;
      emit('input', value);
    };

    // 失去焦点
    const handleBlur = (event: FocusEvent) => {
      setTimeout(() => {
        isBlur.value = true;
        if (props.disabled) {
          event.preventDefault();
          return;
        }
        if (localValue.value) {
          if (oldInputText === localValue.value) {
            return;
          }
          oldInputText = localValue.value;
          validator(localValue.value)
            .then(() => {
              emit('error', false);
              emit('submit', localValue.value);
            })
            .catch(() => emit('error', true));
          return;
        }
        emit('submit', localValue.value);
      }, 100);
    };

    // enter键提交
    const handleKeydown = (_value: string, event: KeyboardEvent) => {
      if (props.disabled) {
        event.preventDefault();
        return;
      }
      if (event.isComposing) {
        // 跳过输入法复合事件
        return;
      }
      if (event.which === 13 || event.key === 'Enter') {
        if (oldInputText === localValue.value) {
          return;
        }
        oldInputText = localValue.value;
        event.preventDefault();
        validator(localValue.value)
          .then((result: boolean) => {
            if (result) {
              emit('error', false);
              emit('submit', localValue.value);
            }
          })
          .catch(() => emit('error', true));
      }
    };

    expose({
      getValue() {
        return validator(localValue.value).then(() => localValue.value);
      },
      focus() {
        (rootRef.value as HTMLElement).querySelector('input')?.focus();
      },
    });

    return () => (
      <div
        ref='rootRef'
        class={{
          'bk-ediatable-input': true,
          'is-error': Boolean(errorMessage.value),
          'is-disabled': props.disabled,
          'is-password': isPassword.value,
        }}
      >
        <bk-input
          class='input-box'
          clearable={false}
          disabled={props.disabled}
          placeholder={props.placeholder}
          type={props.type}
          value={localValue.value}
          on-blur={handleBlur}
          on-change={handleChange}
          on-focus={handleFocus}
          on-input={handleInput}
          on-keydown={handleKeydown}
        />
        {!props.disabled && props.clearable && localValue.value && (
          <log-icon
            class='clear-icon'
            type='shanchu'
            on-click={handleClear}
          />
        )}
        {errorMessage.value && (
          <log-icon
            class='error-icon'
            v-bk-tooltips={errorMessage.value}
            type='circle-alert-filled'
          />
        )}
      </div>
    );
  },
});
