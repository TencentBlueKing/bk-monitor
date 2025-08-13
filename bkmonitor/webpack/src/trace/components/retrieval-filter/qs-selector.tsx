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

import { defineComponent, nextTick, onBeforeUnmount, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue';

import { useEventListener, watchDebounced } from '@vueuse/core';
import tippy from 'tippy.js';
import { useI18n } from 'vue-i18n';

import QsSelectorOptions from './qs-selector-options';
import { QueryStringEditor } from './query-string-utils';
import { EQueryStringTokenType, QS_SELECTOR_EMITS, QS_SELECTOR_PROPS } from './typing';
import { onClickOutside } from './utils';

import './qs-selector.scss';

export default defineComponent({
  name: 'QsSelector',
  props: QS_SELECTOR_PROPS,
  emits: QS_SELECTOR_EMITS,
  setup(props, { emit }) {
    const selectRef = useTemplateRef<HTMLDivElement>('select');
    const elRef = useTemplateRef<HTMLDivElement>('elRef');
    const elBRef = useTemplateRef<HTMLDivElement>('elB');

    const localValue = shallowRef('');
    const popoverInstance = shallowRef(null);
    const showSelector = shallowRef(false);
    const curTokenType = shallowRef<EQueryStringTokenType>(EQueryStringTokenType.key);
    const search = shallowRef('');
    const curTokenField = shallowRef('');
    const queryStringEditor = shallowRef<QueryStringEditor>(null);
    const inputValue = shallowRef('');
    // const fieldsMap = shallowRef<Map<string, IFilterField>>(new Map());
    let onClickOutsideFn = () => {};
    let cleanup = () => {};

    const { t } = useI18n();

    init();
    onBeforeUnmount(() => {
      onClickOutsideFn?.();
      destroyPopoverInstance();
    });

    watch(
      () => props.value,
      val => {
        if (localValue.value !== val) {
          localValue.value = val;
          inputValue.value = val;
          init();
        }
      },
      { immediate: true }
    );
    watchDebounced(
      localValue,
      () => {
        handleAddKeyDownSlash();
      },
      { debounce: 200, immediate: true }
    );
    watch(
      () => props.clearKey,
      () => {
        handleClear();
      }
    );

    onUnmounted(() => {
      cleanup?.();
    });

    function init() {
      nextTick(() => {
        if (queryStringEditor.value) {
          queryStringEditor.value.setQueryString(localValue.value);
        } else {
          const el = elRef.value.querySelector('.retrieval-filter__qs-selector-component');
          queryStringEditor.value = new QueryStringEditor({
            target: el,
            value: localValue.value,
            popUpFn: handlePopUp,
            onSearch: handleSearch,
            popDownFn: destroyPopoverInstance,
            onChange: handleChange,
            onQuery: handleQuery,
            onInput: handleInput,
            keyFormatter: fieldFormatter,
            valueFormatter: valueFormatter,
          });
        }
      });
    }

    function handleAddKeyDownSlash() {
      if (localValue.value) {
        cleanup?.();
      } else {
        cleanup = useEventListener(window, 'keydown', handleKeyDownSlash);
      }
    }

    async function handleShowSelect(event: MouseEvent) {
      if (popoverInstance.value) {
        destroyPopoverInstance();
        return;
      }
      popoverInstance.value = tippy(event.target as any, {
        content: selectRef.value,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor padding-0',
        arrow: false,
        appendTo: document.body,
        zIndex: 998,
        maxWidth: props.qsSelectorOptionsWidth || 1600,
        offset: [0, 5],
        interactive: true,
        onHidden: () => {
          destroyPopoverInstance();
          cleanup = useEventListener(window, 'keydown', handleKeyDownSlash);
        },
      });
      popoverInstance.value?.show();
      showSelector.value = true;
      setTimeout(() => {
        onClickOutsideFn = onClickOutside(
          [elRef.value, document.querySelector('.retrieval-filter__qs-selector-component__popover')],
          () => {
            destroyPopoverInstance();
          },
          { once: true }
        );
      }, 50);

      // popoverInstance.value = $bkPopover({
      //   target: event.target as any,
      //   content: selectRef.value,
      //   trigger: 'click',
      //   placement: 'bottom-start',
      //   theme: 'light common-monitor padding-0',
      //   arrow: true,
      //   boundary: 'window',
      //   zIndex: 998,
      //   padding: 0,
      //   onHide: () => {
      //     destroyPopoverInstance();
      //   },
      // });
      // popoverInstance.value.install();
      // setTimeout(() => {
      //   popoverInstance.value?.vm?.show();
      //   showSelector.value = true;
      //   onClickOutsideFn = onClickOutside(
      //     [elRef.value, document.querySelector('.retrieval-filter__qs-selector-component__popover')],
      //     () => {
      //       destroyPopoverInstance();
      //     },
      //     { once: true }
      //   );
      // }, 200);
    }

    function destroyPopoverInstance() {
      popoverInstance.value?.hide();
      popoverInstance.value?.destroy();
      popoverInstance.value = null;
      showSelector.value = false;
      onClickOutsideFn?.();
      queryStringEditor.value?.setIsPopup?.(false);
    }
    function handlePopUp(type, field) {
      let fieldStr = field;
      const regex = /^dimensions\./;
      if (regex.test(field)) {
        fieldStr = field.replace(regex, '');
      }
      if (
        (EQueryStringTokenType.condition === type && type === EQueryStringTokenType.key) ||
        EQueryStringTokenType.method === type
      ) {
        search.value = '';
      }
      curTokenType.value = type;
      curTokenField.value = fieldStr;
      const customEvent = {
        target: elBRef.value,
      };
      if (popoverInstance.value) {
        popoverInstance.value?.show();
        return;
      }
      handleShowSelect(customEvent as any);
    }
    function handleSelectOption(str: string) {
      queryStringEditor.value.setToken(str, curTokenType.value);
    }
    function handleSearch(value) {
      search.value = value;
    }
    function handleChange(str: string) {
      localValue.value = str;
      emit('change', str);
    }
    function handleQuery() {
      popoverInstance.value?.hide?.();
      emit('query');
    }
    function handleSelectFavorite(value: string) {
      queryStringEditor.value.setQueryString(value);
      handleChange(value);
      handleQuery();
    }
    function handleClear() {
      inputValue.value = '';
      localValue.value = '';
      queryStringEditor.value.setQueryString('');
      handleChange('');
      handleQuery();
    }
    function handleInput(val) {
      inputValue.value = val.replace(/^\s+|\s+$/g, '');
    }
    function handleKeyDownSlash(event) {
      if (event.key === '/' && !localValue.value && !['BK-WEWEB', 'INPUT'].includes(event.target?.tagName)) {
        handlePopUp(EQueryStringTokenType.key, '');
        setTimeout(() => {
          queryStringEditor.value.editorEl?.focus?.();
        }, 300);
        cleanup?.();
      }
    }
    /**
     * @description
     *  fields 中 is_dimensions=true 的，需要补充 dimensions
     *  dimensions.xxxxx
     * @param field
     * @returns
     */
    function fieldFormatter(field: string) {
      return field;
      // const fieldItem = fieldsMap.value.get(field);
      // const regex = /^dimensions\./;
      // if (fieldItem?.is_dimensions && !regex.test(field)) {
      //   return `dimensions.${field}`;
      // }
      // return field;
    }
    /**
   * @description 语句模式 : (等于) 某个值的时候需要将值用双引号包裹

   * @param field
   * @param method
   * @param value
   */
    function valueFormatter(field: string, method: string, value: string) {
      const regex = /^".*"$/;
      if (field && method === ':' && !regex.test(value)) {
        return `"${value}"`;
      }
      return value;
    }
    return {
      localValue,
      inputValue,
      curTokenField,
      search,
      showSelector,
      curTokenType,
      handleSelectOption,
      handleSelectFavorite,
      t,
    };
  },
  render() {
    return (
      <div
        ref='elRef'
        class='vue3_retrieval-filter__qs-selector-component-wrap'
        data-placeholder={
          !this.inputValue && !this.localValue ? `${this.placeholder || this.t('快速定位到搜索，请输入关键词')}` : ''
        }
      >
        <div class='retrieval-filter__qs-selector-component' />
        <div
          ref='elB'
          class='__bottom__'
        />

        <div style='display: none;'>
          <div
            ref='select'
            style={{
              ...(this.qsSelectorOptionsWidth ? { width: `${this.qsSelectorOptionsWidth}px` } : {}),
            }}
            class='retrieval-filter__qs-selector-component__popover'
          >
            <QsSelectorOptions
              favoriteList={this.favoriteList}
              field={this.curTokenField}
              fields={this.fields}
              getValueFn={this.getValueFn}
              queryString={this.localValue}
              search={this.search}
              show={this.showSelector}
              type={this.curTokenType}
              onSelect={this.handleSelectOption}
              onSelectFavorite={this.handleSelectFavorite}
            />
          </div>
        </div>
      </div>
    );
  },
});
