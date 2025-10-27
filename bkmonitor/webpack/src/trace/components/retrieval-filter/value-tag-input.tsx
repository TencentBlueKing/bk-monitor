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

import { defineComponent, nextTick, shallowRef, useTemplateRef, watch } from 'vue';

import { VALUE_TAG_INPUT_EMITS, VALUE_TAG_INPUT_PROPS } from './typing';
import { getCharLength, NULL_VALUE_ID, NULL_VALUE_NAME } from './utils';

import './value-tag-input.scss';

export default defineComponent({
  name: 'ValueTagInput',
  props: VALUE_TAG_INPUT_PROPS,
  emits: VALUE_TAG_INPUT_EMITS,
  setup(props, { emit }) {
    const inputRef = useTemplateRef<HTMLInputElement>('input');

    const localValue = shallowRef('');
    const isEdit = shallowRef(false);

    watch(
      () => props.value,
      val => {
        if (val !== localValue.value) {
          localValue.value = val;
        }
      },
      { immediate: true }
    );

    /**
     * 处理点击事件
     * 将编辑状态设置为 true 并使输入框获得焦点
     * @private
     */
    function handleClick() {
      isEdit.value = true;
      inputFocus();
    }
    /**
     * 处理输入框值变化的函数
     * @param {Event} event - 输入事件对象
     * @description
     * 1. 获取输入框的值
     * 2. 计算字符长度
     * 3. 根据字符长度动态设置输入框宽度
     * 4. 去除输入值中的换行符并更新本地值
     */
    function handleInput(event) {
      const input = event.target;
      const value = input.value;
      const charLen = getCharLength(value);
      input.style.setProperty('width', `${charLen * 12}px`);
      localValue.value = value.replace(/(\r\n|\n|\r)/gm, '');
    }

    /**
     * 处理键盘按键事件
     * @param {KeyboardEvent} event 键盘事件对象
     * @description 当按下回车键时,触发值变更并退出编辑状态
     */
    function handleKeyUp(event) {
      const key = event.key || event.keyCode || event.which;
      if (key === 'Enter' || key === 13) {
        event.preventDefault();
        handleChangeEmit();
        isEdit.value = false;
      }
    }
    /**
     * 处理键盘按键事件
     * @description 阻止回车键的默认行为
     * @param {KeyboardEvent} event - 键盘事件对象
     */
    function handleKeyDown(event) {
      const key = event.key || event.keyCode || event.which;
      if (key === 'Enter' || key === 13) {
        event.preventDefault();
      }
    }
    /**
     * 聚焦输入框
     * 等待下一个 tick 后将焦点设置到输入框元素
     * @returns {Promise<void>}
     */
    async function inputFocus() {
      await nextTick();
      inputRef.value?.focus?.();
    }
    /**
     * 处理输入框失焦事件
     * 当输入框处于编辑状态时,失焦后会:
     * 1. 关闭编辑状态
     * 2. 触发值变更事件
     */
    function handleBlur() {
      if (isEdit.value) {
        isEdit.value = false;
        handleChangeEmit();
      }
    }
    function handleChangeEmit() {
      if (props.value !== localValue.value) {
        emit('change', localValue.value);
      }
    }
    function handleComponentClick(event) {
      event.stopPropagation();
    }
    function handleDelete(e) {
      emit('delete', e);
    }

    return {
      isEdit,
      localValue,
      handleComponentClick,
      handleClick,
      handleBlur,
      handleInput,
      handleKeyDown,
      handleKeyUp,
      handleDelete,
    };
  },
  render() {
    return (
      <div
        class={[
          'vue3_retrieval__value-tag-input-component',
          { 'edit-active': this.isEdit },
          { 'one-row': this.isOneRow },
        ]}
        onClick={this.handleComponentClick}
      >
        <span
          key={'01'}
          class={'value-span'}
          onClick={() => this.handleClick()}
        >
          {this.localValue === NULL_VALUE_ID ? NULL_VALUE_NAME : this.localValue}
        </span>
        {this.isEdit ? (
          <textarea
            ref={'input'}
            class='value-span-input'
            v-model={this.localValue}
            spellcheck={false}
            onBlur={this.handleBlur}
            onInput={this.handleInput}
            onKeydown={this.handleKeyDown}
            onKeyup={this.handleKeyUp}
          />
        ) : (
          <span
            key={'02'}
            class='icon-monitor icon-mc-close'
            onClick={this.handleDelete}
          />
        )}
      </div>
    );
  },
});
