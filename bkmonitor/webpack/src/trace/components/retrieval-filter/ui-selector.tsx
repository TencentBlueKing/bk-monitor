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

import { isEn } from '../../i18n/i18n';
import { defineComponent, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue';

import { useEventListener } from '@vueuse/core';
import tippy from 'tippy.js';
import { useI18n } from 'vue-i18n';

import AutoWidthInput from './auto-width-input';
import KvTag from './kv-tag';
import { type IFilterItem, ECondition, EMethod, UI_SELECTOR_EMITS, UI_SELECTOR_PROPS } from './typing';
import UiSelectorOptions from './ui-selector-options';
import { DURATION_KEYS, getDurationDisplay, triggerShallowRef } from './utils';

import './ui-selector.scss';
import 'tippy.js/dist/tippy.css';
export default defineComponent({
  name: 'UiSelector',
  props: UI_SELECTOR_PROPS,
  emits: UI_SELECTOR_EMITS,
  setup(props, { emit }) {
    const { t } = useI18n();

    const elRef = useTemplateRef<HTMLDivElement>('el');
    const selectorRef = useTemplateRef<HTMLDivElement>('selector');

    const showSelector = shallowRef(false);
    const localValue = shallowRef<IFilterItem[]>([]);
    const popoverInstance = shallowRef(null);
    const updateActive = shallowRef(-1);
    const inputValue = shallowRef('');
    const inputFocus = shallowRef(false);
    let cleanup = () => {};

    init();
    watch(
      () => props.value,
      val => {
        const valueStr = JSON.stringify(val);
        const localValueStr = JSON.stringify(localValue.value);
        if (valueStr !== localValueStr) {
          localValue.value = structuredClone(props.value);
        }
      },
      { immediate: true }
    );
    watch(
      () => props.clearKey,
      () => {
        handleClear();
      }
    );

    function init() {
      cleanup = useEventListener(window, 'keydown', handleKeyDownSlash);
    }

    onUnmounted(() => {
      cleanup?.();
    });

    async function handleShowSelect(event: MouseEvent) {
      if (popoverInstance.value) {
        destroyPopoverInstance();
        return;
      }
      popoverInstance.value = tippy(event.target as any, {
        content: selectorRef.value,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor padding-0',
        arrow: true,
        appendTo: document.body,
        zIndex: 998,
        maxWidth: 720,
        offset: [0, 4],
        interactive: true,
        onHidden: () => {
          destroyPopoverInstance();
          cleanup = useEventListener(window, 'keydown', handleKeyDownSlash);
        },
      });
      popoverInstance.value?.show();
      showSelector.value = true;
    }

    function destroyPopoverInstance() {
      popoverInstance.value?.hide();
      popoverInstance.value?.destroy();
      popoverInstance.value = null;
      showSelector.value = false;
    }

    /**
     * 处理添加按钮点击事件
     * @param {MouseEvent} event - 鼠标事件对象
     * @description
     * 1. 阻止事件冒泡
     * 2. 重置激活状态为-1
     * 3. 创建自定义事件对象,将currentTarget作为target
     * 4. 显示选择器
     * 5. 隐藏输入框
     */
    function handleAdd(event: MouseEvent) {
      event.stopPropagation();
      updateActive.value = -1;
      const customEvent = {
        ...event,
        target: event.currentTarget,
      };
      handleShowSelect(customEvent);
      hideInput();
    }

    /**
     * @description 清空
     */
    /**
     * 清空选择器的值并重置状态
     * @param {MouseEvent} event - 鼠标事件对象
     * @description
     * 1. 阻止事件冒泡
     * 2. 清空本地选中值
     * 3. 重置激活状态为-1
     * 4. 隐藏输入框
     * 5. 触发change事件回调
     */
    function handleClear(event?: MouseEvent) {
      event?.stopPropagation?.();
      localValue.value = [];
      updateActive.value = -1;
      hideInput();
      handleChange();
    }

    function hideInput() {
      inputFocus.value = false;
      inputValue.value = '';
    }

    function handleChange() {
      emit('change', localValue.value);
    }

    /**
     * 处理斜杠键按下事件
     * 当按下斜杠键且输入框为空且选择器未显示时,触发组件点击事件并执行清理
     * @param {KeyboardEvent} event 键盘事件对象
     */
    function handleKeyDownSlash(event) {
      if (
        event.key === '/' &&
        !inputValue.value &&
        !showSelector.value &&
        !['BK-WEWEB', 'INPUT'].includes(event.target?.tagName)
      ) {
        event.preventDefault();
        handleClickComponent();
        cleanup();
      }
    }

    /**
     * 处理组件点击事件
     * @param {MouseEvent} event - 鼠标事件对象
     * @description
     * 1. 阻止事件冒泡
     * 2. 重置更新激活状态为 -1
     * 3. 设置输入框焦点状态为 true
     * 4. 获取占位符元素并创建自定义事件
     * 5. 触发显示选择器的处理函数
     */
    function handleClickComponent(event?: MouseEvent) {
      event?.stopPropagation();
      updateActive.value = -1;
      inputFocus.value = true;
      const el = elRef.value.querySelector('.kv-placeholder');
      const customEvent = {
        ...event,
        target: el,
      };
      handleShowSelect(customEvent);
      // setTimeout(() => {
      //   inputFocus.value = true;
      // }, 300);
    }

    function handleCancel() {
      destroyPopoverInstance();
      hideInput();
    }
    /**
     * 处理确认选择的过滤项
     * @param {IFilterItem} value - 选中的过滤项值
     * @description
     * 1. 深拷贝当前本地值
     * 2. 如果存在更新索引,则替换对应位置的值,否则追加到末尾
     * 3. 更新本地值
     * 4. 销毁弹出层实例
     * 5. 隐藏输入框
     * 6. 触发变更回调
     */
    function handleConfirm(value: IFilterItem) {
      const localValueV = structuredClone(localValue.value);
      if (value) {
        if (updateActive.value > -1) {
          localValueV.splice(updateActive.value, 1, value);
        } else {
          localValueV.push(value);
        }
      }
      localValue.value = localValueV;
      destroyPopoverInstance();
      hideInput();
      handleChange();
    }

    function handleBlur() {
      inputFocus.value = false;
      if (!inputValue.value) {
        hideInput();
      }
    }
    function handleEnter() {
      if (inputValue.value) {
        localValue.value.push({
          key: {
            id: '*',
            name: t('全文'),
          },
          value: [{ id: inputValue.value, name: inputValue.value }],
          method: { id: EMethod.include, name: t('包含') },
          condition: { id: ECondition.and, name: 'AND' },
        });
        triggerShallowRef(localValue);
        inputValue.value = '';
        destroyPopoverInstance();
        // setTimeout(() => {
        //   handleClickComponent();
        // }, 50);
        handleChange();
      }
    }
    function handleInput(v: string) {
      inputValue.value = v;
    }
    function handleDeleteTag(index: number) {
      localValue.value.splice(index, 1);
      triggerShallowRef(localValue);
      handleChange();
      handleCancel();
    }
    function handleHideTag(index: number) {
      let hide = false;
      if (typeof localValue.value[index]?.hide === 'boolean') {
        hide = !localValue.value[index].hide;
      } else {
        hide = true;
      }
      localValue.value.splice(index, 1, {
        ...localValue.value[index],
        hide,
      });
      triggerShallowRef(localValue);
      handleChange();
    }
    function handleUpdateTag(event: MouseEvent, index: number) {
      event.stopPropagation();
      updateActive.value = index;
      const customEvent = {
        ...event,
        target: event.currentTarget,
      };
      handleShowSelect(customEvent);
      hideInput();
    }

    return {
      inputValue,
      showSelector,
      localValue,
      updateActive,
      inputFocus,
      handleBlur,
      handleEnter,
      handleInput,
      handleAdd,
      handleCancel,
      handleConfirm,
      handleDeleteTag,
      handleHideTag,
      handleUpdateTag,
      handleClickComponent,
      t,
    };
  },
  render() {
    return (
      <div
        ref='el'
        class='vue3_retrieval-filter__ui-selector-component'
        onClick={this.handleClickComponent}
      >
        <div onClick={this.handleAdd}>
          <div class='add-btn'>
            <span class='icon-monitor icon-mc-add' />
            <span class='add-text'>{this.t('添加条件')}</span>
          </div>
        </div>
        {this.localValue.map((item, index) => (
          <KvTag
            key={`${index}_kv`}
            value={item}
            onDelete={() => this.handleDeleteTag(index)}
            onHide={() => this.handleHideTag(index)}
            onUpdate={event => this.handleUpdateTag(event, index)}
          >
            {{
              value: DURATION_KEYS.includes(item.key.id)
                ? () => <span class='value-name'>{getDurationDisplay(item.value.map(item => item.id))}</span>
                : undefined,
            }}
          </KvTag>
        ))}
        <div class={['kv-placeholder', { 'is-en': isEn }]}>
          <AutoWidthInput
            height={40}
            isFocus={this.inputFocus}
            placeholder={this.placeholder || `${this.t('快捷键 / ，可直接输入')}`}
            value={this.inputValue}
            onBlur={this.handleBlur}
            onEnter={this.handleEnter}
            onInput={this.handleInput}
          />
        </div>
        <div style='display: none;'>
          <div ref='selector'>
            <UiSelectorOptions
              fields={this.fields}
              getValueFn={this.getValueFn}
              keyword={this.inputValue}
              show={this.showSelector}
              value={this.localValue?.[this.updateActive]}
              onCancel={this.handleCancel}
              onConfirm={this.handleConfirm}
            />
          </div>
        </div>
      </div>
    );
  },
});
