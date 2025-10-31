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

import { type PropType, computed, defineComponent, onUnmounted, shallowRef, useTemplateRef } from 'vue';

import { useEventListener } from '@vueuse/core';
import { useI18n } from 'vue-i18n';
import { useTippy } from 'vue-tippy';

import IndexSetSelectorPopSimple from './index-set-selector-pop-simple';

import type { IIndexSet } from './typing';

import './index-set-selector.scss';

export default defineComponent({
  name: 'IndexSetSelector',
  props: {
    indexSetList: {
      type: Array as PropType<IIndexSet[]>,
      default: () => [],
    },
    value: {
      type: [Number, String] as PropType<number | string>,
      default: '',
    },
  },
  emits: {
    change: (_indexSetId: number | string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const elRef = useTemplateRef<HTMLDivElement>('el');
    const selectorRef = useTemplateRef<HTMLDivElement>('selector');

    const popoverInstance = shallowRef(null);
    const showSelector = shallowRef(false);

    const curIndexSet = computed<IIndexSet>(() => {
      return props.indexSetList.find(item => item.index_set_id === props.value) || null;
    });

    let cleanup = () => {};

    init();

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
      popoverInstance.value = useTippy(event.target as any, {
        content: () => selectorRef.value,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor padding-0',
        arrow: false,
        appendTo: document.body,
        zIndex: 4000,
        maxWidth: 700,
        offset: [0, 6],
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
     * 处理快捷键按下事件
     * 当按下Ctrl+O(Windows/Linux)或Cmd+O(Mac)且选择器未显示且不在输入框中时,触发组件点击事件并执行清理
     * @param {KeyboardEvent} event 键盘事件对象
     */
    function handleKeyDownSlash(event) {
      const isCtrlO = (event.ctrlKey || event.metaKey) && event.key === 'o';
      console.log(isCtrlO);
      if (isCtrlO && !showSelector.value && !['BK-WEWEB', 'INPUT'].includes(event.target?.tagName)) {
        event.preventDefault();
        handleClickComponent();
        cleanup();
      }
    }

    function handleClickComponent(event?: MouseEvent) {
      event?.stopPropagation();
      const el = elRef.value.querySelector('.index-set-trigger');
      const customEvent = {
        ...event,
        target: el,
      };
      handleShowSelect(customEvent);
    }

    function handleSelect(indexSetId: number | string) {
      destroyPopoverInstance();
      emit('change', indexSetId);
    }

    return {
      t,
      showSelector,
      curIndexSet,
      handleSelect,
      handleShowSelect,
      handleClickComponent,
    };
  },
  render() {
    return (
      <div
        ref='el'
        class='alarm-center-detail-panel-alarm-log-index-set-selector'
      >
        <div
          class={['index-set-trigger', { active: this.showSelector }]}
          data-shortcut-key={'Cmd+o'}
          onClick={this.handleClickComponent}
        >
          <span
            class='index-set-trigger-text'
            data-placeholder={this.curIndexSet ? '' : this.t('请选择索引集')}
          >
            <span class='name'>{this.curIndexSet?.index_set_name || ''}</span>
            <span class='alias' />
          </span>
          <span class='index-set-trigger-icon'>
            <span class='icon-monitor icon-mc-arrow-down' />
          </span>
        </div>
        <div style={{ display: 'none' }}>
          <div ref='selector'>
            <IndexSetSelectorPopSimple
              id={this.value}
              list={this.indexSetList}
              show={this.showSelector}
              onSelect={this.handleSelect}
            />
          </div>
        </div>
      </div>
    );
  },
});
