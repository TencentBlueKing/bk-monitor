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

import { computed, defineComponent, shallowRef, useTemplateRef, watch } from 'vue';

import { onClickOutside, promiseTimeout } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import AutoWidthInput from './auto-width-input';
import { type IValue, EFieldType, VALUE_TAG_SELECTOR_EMITS, VALUE_TAG_SELECTOR_PROPS } from './typing';
import { isNumeric, triggerShallowRef } from './utils';
import ValueOptions from './value-options';
import ValueTagInput from './value-tag-input';

import './value-tag-selector.scss';

export default defineComponent({
  name: 'ValueTagSelector',
  props: VALUE_TAG_SELECTOR_PROPS,
  emits: VALUE_TAG_SELECTOR_EMITS,
  setup(props, { emit }) {
    const elRef = useTemplateRef<HTMLDivElement>('el');
    const { t } = useI18n();

    const localValue = shallowRef<IValue[]>([]);
    const isShowDropDown = shallowRef(false);
    const activeIndex = shallowRef(-1);
    const inputValue = shallowRef('');
    const isFocus = shallowRef(false);
    const isChecked = shallowRef(false);

    const isTypeInteger = computed(() => [EFieldType.integer, EFieldType.long].includes(props.fieldInfo?.type));

    init();
    watch(
      () => props.value,
      val => {
        localValue.value = structuredClone(val);
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

    /**
     * 处理下拉框显示状态的切换
     * @param {boolean} v - 是否显示下拉框
     * @description
     * 1. 设置下拉框的显示状态
     * 2. 当下拉框显示时，添加点击外部区域的监听
     * 3. 点击外部区域时，关闭下拉框，取消焦点状态，并触发失焦事件
     * 4. 使用 setTimeout 延迟 100ms 添加监听，避免与其他点击事件冲突
     */
    function handleShowShowDropDown(v: boolean) {
      isShowDropDown.value = v;
      if (isShowDropDown.value) {
        setTimeout(() => {
          onClickOutside(
            elRef.value,
            () => {
              isShowDropDown.value = false;
              isFocus.value = false;
              handleSelectorBlur();
            },
            { controls: true }
          );
        }, 100);
      }
    }
    function handleSelectorBlur() {
      emit('selectorBlur');
    }
    /**
     * 处理选中值的回调函数
     * @param {IValue} item - 选中的值对象
     * @description
     * 1. 重置当前激活项索引为-1
     * 2. 如果已选中列表中存在相同id的值则直接返回
     * 3. 将选中项添加到本地值列表中
     * 4. 触发值变更回调
     */
    function handleCheck(item: IValue) {
      activeIndex.value = -1;
      if (localValue.value.some(v => v.id === item.id)) return;
      localValue.value.push(item);
      triggerShallowRef(localValue);
      handleChange();
    }
    /**
     * 处理点击事件
     * - 如果下拉框未显示,则显示下拉框
     * - 设置当前激活项为最后一项
     * - 设置焦点状态为 true
     * - 触发选择器获得焦点事件
     */
    function handleClick() {
      if (!isShowDropDown.value) {
        handleShowShowDropDown(true);
      }
      activeIndex.value = localValue.value.length - 1;
      isFocus.value = true;
      handleSelectorFocus();
    }
    /**
     * 处理输入框值变化
     * @param {string} value - 输入框的值
     * @description 更新输入值,显示下拉框,重置选中状态
     */
    function handleInput(value: string) {
      inputValue.value = value;
      if (!isShowDropDown.value) {
        handleShowShowDropDown(true);
      }
      emit('selectorFocus');
      isChecked.value = false;
    }
    /**
     * 处理输入框失焦事件
     * 延迟 300ms 后清空输入值
     * @returns {Promise<void>}
     */
    async function handleBlur() {
      // handleEnter();
      await promiseTimeout(300);
      inputValue.value = '';
    }
    /**
     * 处理输入框回车事件
     * 当输入框有值且未被选中时,将输入值添加到本地数据中
     * 如果输入值已存在则清空输入框
     * 添加成功后:
     * - 清空输入框
     * - 更新选中索引
     * - 触发change事件
     * - 保持输入框焦点
     */
    function handleEnter() {
      if (!inputValue.value || isChecked.value) {
        return;
      }
      if (localValue.value.some(v => String(v.id) === inputValue.value)) {
        inputValue.value = '';
        return;
      }
      localValue.value.push({ id: inputValue.value, name: inputValue.value });
      triggerShallowRef(localValue);
      if (activeIndex.value === -1 && localValue.value.length) {
        activeIndex.value = localValue.value.length - 1;
      } else {
        activeIndex.value += 1;
      }
      inputValue.value = '';
      handleChange();
      isFocus.value = true;
    }
    /**
     * 处理退格键在输入为空时的逻辑
     * - 当输入值为空时,如果有活动索引,则将其减1
     * - 如果本地值长度大于1,则删除活动索引后的一个值
     * - 如果本地值长度为1,则清空本地值并延迟300ms后触发点击事件
     */
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
      triggerShallowRef(localValue);
      handleChange();
    }
    /**
     * 处理值变更事件
     * 触发 change 事件，将当前本地值传递给父组件
     * @emits change - 值变更时触发，参数为当前选中的值
     */
    function handleChange() {
      emit('change', localValue.value);
    }
    /**
     * 处理标签更新
     * @param {string} v - 标签值
     * @param {number} index - 需要更新的标签索引
     * @description 更新或删除指定索引位置的标签值,并触发变更事件
     */
    function handleTagUpdate(v: string, index: number) {
      if (v) {
        localValue.value.splice(index, 1, { id: v, name: v });
      } else {
        localValue.value.splice(index, 1);
      }
      triggerShallowRef(localValue);
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
      t,
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
        placeholder={this.placeholder || `${this.t('请输入')} ${this.t('或')} ${this.t('选择')}`}
        value={this.inputValue}
        onBackspaceNull={this.handleBackspaceNull}
        onBlur={this.handleBlur}
        onEnter={this.handleEnter}
        onInput={this.handleInput}
      />
    );
    return (
      <div
        ref='el'
        class='vue3_retrieval__value-tag-selector-component'
      >
        <div
          class={['value-tag-selector-component-wrap', { active: this.isFocus }]}
          onClick={this.handleClick}
        >
          {this.localValue.length
            ? [
                this.localValue.map((item, index) => [
                  <ValueTagInput
                    key={item.id}
                    class={{ 'is-error': this.isTypeInteger ? !isNumeric(item.id) : false }}
                    value={item.id}
                    onChange={v => this.handleTagUpdate(v, index)}
                    onDelete={() => this.handleDelete(index)}
                  />,
                  this.activeIndex === index && inputRender(`${item.id}_input`),
                ]),
                this.activeIndex === -1 && inputRender('input'),
              ]
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
