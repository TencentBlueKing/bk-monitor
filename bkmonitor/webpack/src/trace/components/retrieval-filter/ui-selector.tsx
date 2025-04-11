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

import { defineComponent, useTemplateRef, watch } from 'vue';
import { shallowRef } from 'vue';

import { useEventListener } from '@vueuse/core';
import { $bkPopover } from 'bkui-vue';

import { EFieldType, type IFilterItem, UI_SELECTOR_EMITS, UI_SELECTOR_PROPS } from './typing';
import UiSelectorOptions from './ui-selector-options';

import './ui-selector.scss';

type PopoverInstance = {
  show: () => void;
  hide: () => void;
  close: () => void;
  [key: string]: any;
};

export default defineComponent({
  name: 'UiSelector',
  props: UI_SELECTOR_PROPS,
  emits: UI_SELECTOR_EMITS,
  setup(props, { emit }) {
    const $el = useTemplateRef<HTMLDivElement>('el');
    const selectorRef = useTemplateRef<HTMLDivElement>('selector');

    const showSelector = shallowRef(false);
    const localValue = shallowRef<IFilterItem[]>([]);
    const popoverInstance = shallowRef<PopoverInstance>(null);
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
          localValue.value = JSON.parse(valueStr);
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
      cleanup = useEventListener(document, 'keydown', handleKeyDownSlash);
    }

    /**
     * 处理显示选择器的点击事件
     * @param {MouseEvent} event - 鼠标事件对象
     * @description
     * 1. 如果已存在 popover 实例则更新目标和内容
     * 2. 否则创建新的 popover 实例并配置相关属性
     * 3. popover 隐藏时销毁实例并重新绑定键盘事件
     * 4. 延迟 100ms 显示 popover
     * @private
     */
    async function handleShowSelect(event: MouseEvent) {
      if (popoverInstance.value) {
        popoverInstance.value.update(event.target, {
          target: event.target as any,
          content: selectorRef.value,
        });
      } else {
        popoverInstance.value = $bkPopover({
          target: event.target as any,
          content: selectorRef.value,
          trigger: 'click',
          placement: 'bottom-start',
          theme: 'light common-monitor padding-0',
          arrow: true,
          boundary: 'window',
          zIndex: 998,
          padding: 0,
          onHide: () => {
            destroyPopoverInstance();
            cleanup = useEventListener(document, 'keydown', handleKeyDownSlash);
          },
        });
        popoverInstance.value.install();
        setTimeout(() => {
          popoverInstance.value?.vm?.show();
        }, 100);
      }
      showSelector.value = true;
    }

    function destroyPopoverInstance() {
      popoverInstance.value?.hide();
      popoverInstance.value?.close();
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
      if (event.key === '/' && !inputValue.value && !showSelector.value) {
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
      const el = $el.value.querySelector('.kv-placeholder');
      const customEvent = {
        ...event,
        target: el,
      };
      handleShowSelect(customEvent);
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
      const localValue$ = JSON.parse(JSON.stringify(localValue.value));
      if (value) {
        if (updateActive.value > -1) {
          localValue$.splice(updateActive.value, 1, value);
        } else {
          localValue$.push(value);
        }
      }
      localValue.value = localValue$;
      destroyPopoverInstance();
      hideInput();
      handleChange();
    }

    return {
      inputValue,
      showSelector,
      localValue,
      updateActive,
      handleAdd,
      handleCancel,
      handleConfirm,
    };
  },
  render() {
    return (
      <div
        ref='el'
        class='vue3_retrieval-filter__ui-selector-component'
      >
        <div
          class='add-btn'
          onClick={this.handleAdd}
        >
          <span class='icon-monitor icon-mc-add' />
          <span class='add-text'>{this.$t('添加条件')}</span>
        </div>
        <div style='display: none;'>
          <div ref='selector'>
            <UiSelectorOptions
              fields={[
                {
                  type: EFieldType.all,
                  name: '*',
                  alias: this.$tc('全文检索'),
                  is_option_enabled: false,
                  supported_operations: [],
                },
                ...this.fields,
              ]}
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
