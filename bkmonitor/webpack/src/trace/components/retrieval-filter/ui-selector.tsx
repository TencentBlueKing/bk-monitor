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

import { type IFilterItem, UI_SELECTOR_EMITS, UI_SELECTOR_PROPS } from './typing';

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
          theme: 'light common-monitor',
          arrow: true,
          boundary: 'window',
          zIndex: 998,
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

    function handleKeyDownSlash(event) {
      if (event.key === '/' && !inputValue.value && !showSelector.value) {
        event.preventDefault();
        handleClickComponent();
        cleanup();
      }
    }

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

    return {
      handleAdd,
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
          <div ref='selector'>xxxx</div>
        </div>
      </div>
    );
  },
});
