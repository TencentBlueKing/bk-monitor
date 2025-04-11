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

import { defineComponent, shallowRef, computed, useTemplateRef, watch } from 'vue';

import { promiseTimeout } from '@vueuse/core';

import AutoWidthInput from './auto-width-input';
import { type IValue, VALUE_TAG_SELECTOR_EMITS, VALUE_TAG_SELECTOR_PROPS } from './typing';
import { isNumeric, onClickOutside } from './utils';
import ValueOptions from './value-options';
import ValueTagInput from './value-tag-input';

import './value-tag-selector.scss';

export default defineComponent({
  name: 'ValueTagSelector',
  props: VALUE_TAG_SELECTOR_PROPS,
  emits: VALUE_TAG_SELECTOR_EMITS,
  setup(props, { emit }) {
    const $el = useTemplateRef<HTMLDivElement>('el');

    const localValue = shallowRef<IValue[]>([]);
    const isShowDropDown = shallowRef(false);
    const activeIndex = shallowRef(-1);
    const inputValue = shallowRef('');
    const isFocus = shallowRef(false);
    const isChecked = shallowRef(false);

    const isTypeInteger = computed(() => (isTypeInteger.value ? localValue.value.some(v => !isNumeric(v)) : false));

    init();
    watch(
      () => props.value,
      val => {
        localValue.value = JSON.parse(JSON.stringify(val));
      },
      { immediate: true }
    );

    function init() {
      activeIndex.value = localValue.value.length - 1;
      if (props.autoFocus) {
        focusFn();
      }
    }
    function focusFn() {
      isFocus.value = true;
      handleShowShowDropDown(true);
    }

    function handleShowShowDropDown(v: boolean) {
      isShowDropDown.value = v;
      if (isShowDropDown.value) {
        setTimeout(() => {
          onClickOutside(
            $el.value,
            () => {
              isShowDropDown.value = false;
              isFocus.value = false;
              handleSelectorBlur();
            },
            { once: true }
          );
        }, 100);
      }
    }
    function handleSelectorBlur() {
      emit('selectorBlur');
    }
    function handleCheck(item: IValue) {
      activeIndex.value = -1;
      if (localValue.value.some(v => v.id === item.id)) return;
      localValue.value.push(item);
      handleChange();
    }
    function handleClick() {
      if (!isShowDropDown.value) {
        handleShowShowDropDown(true);
      }
      activeIndex.value = localValue.value.length - 1;
      isFocus.value = true;
      handleSelectorFocus();
    }
    function handleInput(value: string) {
      inputValue.value = value;
      if (!isShowDropDown.value) {
        handleShowShowDropDown(true);
      }
      isChecked.value = false;
    }
    async function handleBlur() {
      await promiseTimeout(300);
      inputValue.value = '';
    }
    function handleEnter() {
      if (!inputValue.value || isChecked.value) {
        return;
      }
      if (localValue.value.some(v => v.id === inputValue.value)) {
        inputValue.value = '';
        return;
      }
      localValue.value.push({ id: inputValue.value, name: inputValue.value });
      activeIndex.value += 1;
      inputValue.value = '';
      handleChange();
      isFocus.value = true;
    }
    async function handleBackspaceNull() {
      if (!inputValue.value) {
        if (activeIndex.value > 0) {
          activeIndex.value -= 1;
        }
        if (localValue.value.length > 1) {
          localValue.value.splice(activeIndex.value + 1, 1);
        } else {
          localValue.value = [];
          await promiseTimeout(300);
          handleClick();
        }
      }
    }
    /**
     * 删除指定索引位置的值并触发变更事件
     * @param {number} index - 要删除的数组元素索引
     */
    function handleDelete(index: number) {
      localValue.value.splice(index, 1);
      handleChange();
    }
    function handleChange() {
      emit('change', localValue.value);
    }
    function handleTagUpdate(v: string, index: number) {
      if (v) {
        localValue.value.splice(index, 1, { id: v, name: v });
      } else {
        localValue.value.splice(index, 1);
      }

      handleChange();
    }
    function handleIsChecked(v: boolean) {
      isChecked.value = v;
    }

    function handleSelectorFocus() {
      emit('selectorFocus');
    }

    return {
      localValue,
      isFocus,
      activeIndex,
      isShowDropDown,
      inputValue,
      isTypeInteger,
      handleBackspaceNull,
      handleClick,
      handleBlur,
      handleEnter,
      handleInput,
      handleTagUpdate,
      handleDelete,
      handleIsChecked,
      handleCheck,
    };
  },
  render() {
    const inputRender = (key: string) => (
      <AutoWidthInput
        key={key}
        height={22}
        class='mb-4 mr-4'
        fontSize={12}
        isFocus={this.isFocus}
        placeholder={`${this.$t('请输入')} ${this.$t('或')} ${this.$t('选择')}`}
        value={this.inputValue}
        onBackspaceNull={this.handleBackspaceNull}
        onBlur={this.handleBlur}
        onEnter={this.handleEnter}
        onInput={this.handleInput}
      />
    );
    return (
      <div class='retrieval__value-tag-selector-component'>
        <div
          class={['value-tag-selector-component-wrap', { active: this.isFocus }]}
          onClick={this.handleClick}
        >
          {this.localValue.length
            ? this.localValue.map((item, index) => [
                <ValueTagInput
                  key={item.id}
                  class={{ 'is-error': this.isTypeInteger ? !isNumeric(item.id) : false }}
                  value={item.id}
                  onChange={v => this.handleTagUpdate(v, index)}
                  onDelete={() => this.handleDelete(index)}
                />,
                this.activeIndex === index && inputRender(`${item.id}_input`),
              ])
            : inputRender('input')}
        </div>
        {this.isShowDropDown && (
          <ValueOptions
            fieldInfo={this.fieldInfo}
            getValueFn={this.getValueFn}
            needUpDownCheck={this.isFocus}
            noDataSimple={true}
            search={this.inputValue}
            selected={this.localValue.map(item => item.id)}
            onIsChecked={this.handleIsChecked}
            onSelect={this.handleCheck}
          />
        )}
      </div>
    );
  },
});
