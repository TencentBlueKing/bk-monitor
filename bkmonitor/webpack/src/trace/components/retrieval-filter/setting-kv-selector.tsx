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

import { computed, defineComponent, nextTick, onBeforeUnmount, shallowRef, useTemplateRef, watch } from 'vue';
import { onMounted } from 'vue';

import { promiseTimeout, useResizeObserver } from '@vueuse/core';
import { Dropdown } from 'bkui-vue';
import tippy, { sticky } from 'tippy.js';
import { useI18n } from 'vue-i18n';

import AutoWidthInput from './auto-width-input';
import { METHOD_MAP, NOT_TYPE_METHODS, SETTING_KV_SELECTOR_EMITS, SETTING_KV_SELECTOR_PROPS } from './typing';
import { NOT_VALUE_METHODS, onClickOutside, triggerShallowRef } from './utils';
import ValueOptions from './value-options';
import ValueTagInput from './value-tag-input';

import './setting-kv-selector.scss';

export default defineComponent({
  name: 'SettingKvSelector',
  props: SETTING_KV_SELECTOR_PROPS,
  emits: SETTING_KV_SELECTOR_EMITS,
  setup(props, { emit }) {
    const selectorRef = useTemplateRef<HTMLDivElement>('selector');
    const elRef = useTemplateRef<HTMLDivElement>('el');
    const localValue = shallowRef<string[]>([]);
    const localMethod = shallowRef('');
    const expand = shallowRef(false);
    const popoverInstance = shallowRef(null);
    const isHover = shallowRef(false);
    const inputValue = shallowRef('');
    const isFocus = shallowRef(false);
    const methodMap = shallowRef({});
    const showSelector = shallowRef(false);
    const isChecked = shallowRef(false);
    const hideIndex = shallowRef(-1);
    const optionsWidth = shallowRef(0);
    const keyWrapMinWidth = shallowRef(0);
    const { t } = useI18n();

    let clickOutsideFn = () => {};

    const localValueSet = computed(() => {
      return new Set(localValue.value);
    });
    const isHighLight = computed(() => !!inputValue.value || showSelector.value || expand.value);
    const notNeedValueWrap = computed(() => NOT_VALUE_METHODS.includes(localMethod.value));

    init();
    onMounted(async () => {
      keyWrapMinWidth.value = getTextWidth(props.fieldInfo?.alias || props.fieldInfo?.field || '');
      await promiseTimeout(100);
      overviewCount();
      const valueWrap = elRef.value?.querySelector('.component-main > .value-wrap') as any;
      if (valueWrap) {
        useResizeObserver(valueWrap, entries => {
          const entry = entries[0];
          const { width } = entry.contentRect;
          optionsWidth.value = width;
        });
      }
    });
    onBeforeUnmount(() => {
      clickOutsideFn();
    });
    watch(
      () => props.value,
      val => {
        if (val) {
          const valueStr = val.value.join('____');
          const localValueStr = localValue.value.join('____');
          localMethod.value = val.method;
          if (valueStr !== localValueStr) {
            localValue.value = val.value.slice();
          }
          if (val.method !== localMethod.value) {
            localMethod.value = val.method;
          }
        }
      },
      {
        immediate: true,
      }
    );
    watch(
      () => localValue.value,
      () => {
        overviewCount();
      }
    );

    function init() {
      methodMap.value = JSON.parse(JSON.stringify(METHOD_MAP));
      for (const item of props.fieldInfo?.methods || []) {
        methodMap.value[item.id] = item.name;
      }
    }

    function overviewCount() {
      let hasHide = false;
      nextTick(() => {
        const valueWrap = elRef.value?.querySelector('.component-main > .value-wrap') as any;
        let i = -1;
        if (!valueWrap) {
          return;
        }
        for (const el of Array.from(valueWrap.children)) {
          if (el.className.includes('tag-item')) {
            i += 1;
            if ((el as any).offsetTop > 22) {
              hasHide = true;
              break;
            }
          }
        }
        if (hasHide && i > 1) {
          const preItem = valueWrap.children[i - 1] as any;
          if (preItem.offsetLeft + preItem.offsetWidth + 4 > valueWrap.offsetWidth - 72) {
            hideIndex.value = i - 1;
            return;
          }
        }
        hideIndex.value = hasHide ? i : -1;
      });
    }
    function handleClickValueWrap() {
      // event.stopPropagation();
      if (!expand.value) {
        expand.value = true;
        isFocus.value = true;
      }
      const targetEvent = {
        target: elRef.value.querySelector('.component-main > .value-wrap'),
      };
      handleShowSelect(targetEvent as any);
    }

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
        arrow: false,
        appendTo: document.body,
        zIndex: 998,
        interactive: true,
        offset: [0, 4],
        sticky: 'reference',
        plugins: [sticky],
        onHidden: () => {
          destroyPopoverInstance();
        },
      });
      popoverInstance.value.show();
      showSelector.value = true;
      setTimeout(() => {
        handleOnClickOutside();
      }, 200);
    }
    function destroyPopoverInstance() {
      popoverInstance.value?.hide();
      popoverInstance.value?.destroy();
      popoverInstance.value = null;
      showSelector.value = false;
    }
    function handleOnClickOutside() {
      const el = document.querySelector('.resident-setting__setting-kv-selector-component-pop');
      clickOutsideFn = onClickOutside(
        [elRef, el],
        () => {
          expand.value = false;
          inputValue.value = '';
          showSelector.value = false;
          destroyPopoverInstance();
        },
        { once: true }
      );
    }
    function handleMouseenter() {
      isHover.value = true;
    }
    function handleMouseleave() {
      isHover.value = false;
    }
    function handleEnter() {
      if (!isChecked.value || !showSelector.value) {
        if (!localValue.value.map(str => String(str)).includes(inputValue.value) && inputValue.value) {
          localValue.value.push(inputValue.value);
          triggerShallowRef(localValue);
          handleChange();
        }
        inputValue.value = '';
      }
    }
    function handleInput(v: string) {
      inputValue.value = v;
    }
    function handleBlur() {
      isFocus.value = false;
    }
    function handleClear(event: MouseEvent) {
      event.stopPropagation();
      localValue.value = [];
      handleChange();
    }
    function handleDeleteTag(e: MouseEvent, index: number) {
      e.stopPropagation();
      localValue.value.splice(index, 1);
      triggerShallowRef(localValue);
      handleChange();
    }
    function handleSelectOption(item: { id: string; name: string }) {
      if (localValueSet.value.has(item.id)) {
        const delIndex = localValue.value.findIndex(v => v === item.id);
        localValue.value.splice(delIndex, 1);
      } else {
        localValue.value.push(item.id);
      }
      localValue.value = structuredClone(localValue.value);
      handleChange();
    }
    function handleMethodChange(item: { id: string; name: string }) {
      methodMap.value[item.id] = item.name;
      localMethod.value = item.id;
      handleChange();
    }
    function handleChange() {
      if (notNeedValueWrap.value) {
        localValue.value = [];
      }
      emit('change', {
        ...props.value,
        key: props.fieldInfo.field,
        method: localMethod.value,
        value: localValue.value,
      });
    }
    function handleIsChecked(v: boolean) {
      isChecked.value = v;
    }
    function handleValueUpdate(v: string, index: number) {
      if (v) {
        localValue.value.splice(index, 1, v);
      } else {
        localValue.value.splice(index, 1);
      }
      triggerShallowRef(localValue);
      handleChange();
    }
    function handleBackspaceNull() {
      if (!inputValue.value && localValue.value.length) {
        localValue.value.splice(localValue.value.length - 1, 1);
        triggerShallowRef(localValue);
        handleChange();
      }
    }
    function getTextWidth(text: string) {
      const span = document.createElement('span');
      span.style.visibility = 'hidden';
      span.style.position = 'absolute';
      span.style.whiteSpace = 'nowrap';
      span.style.fontSize = '12px';
      document.body.appendChild(span);
      span.textContent = text;
      const width = span.offsetWidth;
      document.body.removeChild(span);
      return width;
    }

    return {
      isHighLight,
      expand,
      localMethod,
      methodMap,
      localValue,
      hideIndex,
      isFocus,
      inputValue,
      isHover,
      optionsWidth,
      showSelector,
      notNeedValueWrap,
      keyWrapMinWidth,
      handleIsChecked,
      handleMouseenter,
      handleMouseleave,
      handleMethodChange,
      handleClickValueWrap,
      handleValueUpdate,
      handleDeleteTag,
      handleBackspaceNull,
      handleBlur,
      handleEnter,
      handleInput,
      handleClear,
      handleSelectOption,
      t,
    };
  },
  render() {
    return (
      <div
        ref='el'
        class={['vue3_resident-setting__setting-kv-selector-component', { active: this.isHighLight }]}
      >
        <div
          class={['component-main', { expand: this.expand, 'not-value-wrap': this.notNeedValueWrap }]}
          onMouseenter={this.handleMouseenter}
          onMouseleave={this.handleMouseleave}
        >
          <span
            style={{
              minWidth: `${this.keyWrapMinWidth < 120 ? this.keyWrapMinWidth : 120}px`,
            }}
            class='key-wrap'
            v-bk-tooltips={{
              content: this.fieldInfo?.field || this.fieldInfo?.alias,
              placement: 'top',
            }}
          >
            {this.fieldInfo?.alias || this.fieldInfo?.field}
          </span>
          <span class='method-wrap'>
            <Dropdown
              popoverOptions={{
                clickContentAutoHide: true,
              }}
              trigger='click'
            >
              {{
                default: () => (
                  <span class={['method-span', { 'red-text': NOT_TYPE_METHODS.includes(this.localMethod as any) }]}>
                    {this.methodMap[this.localMethod] || this.localMethod}
                  </span>
                ),
                content: () => (
                  <ul class='vue3_resident-setting__setting-kv-selector-component_method-list-wrap'>
                    {this.fieldInfo.methods.map(item => (
                      <li
                        key={item.id}
                        class={['method-list-wrap-item', { active: item.id === this.localMethod }]}
                        onClick={() => this.handleMethodChange(item)}
                      >
                        {item.name}
                      </li>
                    ))}
                  </ul>
                ),
              }}
            </Dropdown>
          </span>

          <div
            style={{
              borderBottomWidth: this.localValue?.length ? '1px' : '0',
              display: this.notNeedValueWrap ? 'none' : 'flex',
            }}
            class='value-wrap'
            onClick={this.handleClickValueWrap}
          >
            {this.localValue?.map((item, index) => [
              this.hideIndex === index && !this.expand ? (
                <span
                  key={'count'}
                  class='hide-count'
                  v-bk-tooltips={{
                    content: this.localValue.slice(index).join(','),
                    delay: 300,
                  }}
                >
                  <span>{`+${this.localValue.length - index}`}</span>
                </span>
              ) : undefined,
              // <span
              //   key={index}
              //   class='tag-item'
              // >
              //   <span class='tag-text'>{item}</span>
              //   <span
              //     class='icon-monitor icon-mc-close'
              //     onClick={e => this.handleDeleteTag(e, index)}
              //   />
              // </span>,
              <ValueTagInput
                key={index}
                class='tag-item'
                isOneRow={true}
                value={item}
                onChange={v => this.handleValueUpdate(v, index)}
                onDelete={e => this.handleDeleteTag(e, index)}
              />,
            ])}
            {(this.expand || !this.localValue.length) && (
              <AutoWidthInput
                height={22}
                isFocus={this.isFocus}
                placeholder={`${this.t('请输入')} ${this.t('或')} ${this.t('选择')}`}
                value={this.inputValue}
                onBackspaceNull={this.handleBackspaceNull}
                onBlur={this.handleBlur}
                onEnter={this.handleEnter}
                onInput={this.handleInput}
              />
            )}
            {this.isHover && this.localValue.length ? (
              <div class='delete-btn'>
                <span
                  class='icon-monitor icon-mc-close-fill'
                  onClick={this.handleClear}
                />
              </div>
            ) : (
              <div class='expand-btn'>
                <span class='icon-monitor icon-arrow-down' />
              </div>
            )}
          </div>
        </div>
        <div style='display: none;'>
          <div
            ref={'selector'}
            class='resident-setting__setting-kv-selector-component-pop'
          >
            <ValueOptions
              width={this.optionsWidth}
              fieldInfo={this.fieldInfo}
              getValueFn={this.getValueFn}
              isPopover={true}
              noDataSimple={true}
              search={this.inputValue}
              selected={this.localValue}
              show={this.showSelector}
              onIsChecked={this.handleIsChecked}
              onSelect={this.handleSelectOption}
            />
          </div>
        </div>
      </div>
    );
  },
});
