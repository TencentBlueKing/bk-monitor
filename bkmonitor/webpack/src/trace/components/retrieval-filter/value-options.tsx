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

import { defineComponent, shallowRef, computed, watch, nextTick, useTemplateRef } from 'vue';

import { useEventListener, watchDebounced } from '@vueuse/core';

import loadingImg from '../../static/img/spinner.svg';
import EmptyStatus from '../empty-status/empty-status';
import TextHighlighter from './text-highlighter';
import { type IValue, VALUE_OPTIONS_EMITS, VALUE_OPTIONS_PROPS } from './typing';

import './value-options.scss';

export default defineComponent({
  name: 'ValueOptions',
  props: VALUE_OPTIONS_PROPS,
  emits: VALUE_OPTIONS_EMITS,
  setup(props, { emit }) {
    const $el = useTemplateRef<HTMLDivElement>('el');

    const localOptions = shallowRef<IValue[]>([]);
    const loading = shallowRef(false);
    const hoverActiveIndex = shallowRef(-1);
    const scrollLoading = shallowRef(false);
    const pageSize = shallowRef(10);
    const page = shallowRef(1);
    const isEnd = shallowRef(false);

    const hasCustomOption = computed(() => !!props.search);
    const renderOptions = computed(() => localOptions.value?.filter(item => !props.selected.includes(item.id)) || []);
    const showCustomOption = computed(
      () => !!props.search && !renderOptions.value.some(item => item.id === props.search)
    );
    const search = computed(() => props.search);

    let cleanup = () => {};

    init();
    watch(
      () => props.show,
      async val => {
        if (props.isPopover) {
          if (val) {
            dataInit();
            const list = await getValueData();
            localOptions.value = localOptionsFilter(list);
            cleanup = useEventListener(document, 'keydown', handleKeydownEvent);
            document.addEventListener('keydown', handleKeydownEvent);
          } else {
            cleanup();
          }
        }
      }
    );
    watchDebounced(
      search,
      async () => {
        if (props.isPopover ? props.show : true) {
          dataInit();
          const list = await getValueData();
          localOptions.value = localOptionsFilter(list);
        }
      },
      { debounce: 300 }
    );

    async function init() {
      if (!props.isPopover) {
        dataInit();
        const list = await getValueData();
        localOptions.value = localOptionsFilter(list);
        cleanup = useEventListener(document, 'keydown', handleKeydownEvent);
      }
    }
    function dataInit() {
      localOptions.value = [];
      hoverActiveIndex.value = -1;
      page.value = 1;
      isEnd.value = false;
    }
    function handleKeydownEvent(event: KeyboardEvent) {
      if (!props.needUpDownCheck) {
        return;
      }
      const min = hasCustomOption.value ? -1 : 0;
      switch (event.key) {
        case 'ArrowUp': {
          event.preventDefault();
          hoverActiveIndex.value -= 1;
          if (hoverActiveIndex.value < min) {
            hoverActiveIndex.value = min;
          }
          updateSelection();
          break;
        }
        case 'ArrowDown': {
          event.preventDefault();
          hoverActiveIndex.value += 1;
          if (hoverActiveIndex.value > renderOptions.value.length - 1) {
            hoverActiveIndex.value = renderOptions.value.length - 1;
          }
          updateSelection();
          break;
        }
        case 'Enter': {
          event.preventDefault();
          handleOptionsEnter();
          break;
        }
      }
    }
    function updateSelection() {
      emit('isChecked', hoverActiveIndex.value >= 0 && hoverActiveIndex.value <= localOptions.value.length - 1);
      nextTick(() => {
        const listEl = $el.value.querySelector('.options-drop-down-wrap.main__wrap');
        const el = hasCustomOption.value
          ? listEl?.children?.[hoverActiveIndex.value + 1]
          : listEl?.children?.[hoverActiveIndex.value];
        if (el) {
          el.scrollIntoView(false);
        }
      });
    }
    function handleOptionsEnter() {
      if (hoverActiveIndex.value !== -1) {
        const item = renderOptions.value?.[hoverActiveIndex.value];
        if (item) {
          handleCheck(item);
        }
      }
    }
    async function handleScroll(event) {
      const container = event.target;
      const scrollTop = container.scrollTop;
      const clientHeight = container.clientHeight;
      const scrollHeight = container.scrollHeight;
      if (scrollTop + clientHeight >= scrollHeight - 3) {
        if (!scrollLoading.value && !isEnd.value) {
          scrollLoading.value = true;
          page.value += 1;
          const data = await getValueData(true);
          localOptions.value = localOptionsFilter(data);
          scrollLoading.value = false;
        }
      }
    }
    function handleCheck(item: IValue) {
      emit('select', item);
    }
    async function getValueData(isScroll = false) {
      let list = [];
      if (isScroll) {
        scrollLoading.value = true;
      } else {
        loading.value = true;
      }
      if (props.fieldInfo?.isEnableOptions) {
        const limit = pageSize.value * page.value;
        const data = await props.getValueFn({
          search: props.search,
          limit,
          field: props.fieldInfo.field,
        });
        list = data.list;
        isEnd.value = limit >= data.count;
      }
      scrollLoading.value = false;
      loading.value = false;
      return list;
    }
    function localOptionsFilter(list: IValue[]) {
      if (!list.length) {
        page.value += 1;
      }
      return list;
    }

    return {
      loading,
      localOptions,
      renderOptions,
      showCustomOption,
      hoverActiveIndex,
      scrollLoading,
      handleCheck,
      handleScroll,
    };
  },
  render() {
    return (
      <div
        style={
          this.width
            ? {
                width: `${Math.max(222, this.width)}px`,
              }
            : {}
        }
        class='retrieval-filter__value-options-select-component'
      >
        {this.loading ? (
          <div
            class={['options-drop-down-wrap', { 'is-popover': this.isPopover, 'no-border': !this.localOptions.length }]}
          >
            {new Array(4).fill(null).map(index => {
              return (
                <div
                  key={index}
                  class='options-item skeleton-item'
                >
                  <div class='skeleton-element h-16' />
                </div>
              );
            })}
          </div>
        ) : !this.renderOptions.length && !this.search ? (
          <div class={['options-drop-down-wrap', { 'is-popover': this.isPopover }]}>
            {this.noDataSimple ? (
              <span class='no-data-text'>{this.$t('暂无数据，请输入生成')}</span>
            ) : (
              <EmptyStatus type={'empty'} />
            )}
          </div>
        ) : (
          <div
            class={[
              'options-drop-down-wrap main__wrap',
              { 'is-popover': this.isPopover, 'no-border': !this.renderOptions.length },
            ]}
            onScroll={this.handleScroll}
          >
            {this.showCustomOption && (
              <div
                key={'00'}
                class={['options-item', { 'active-index': this.hoverActiveIndex === -1 }]}
                onMousedown={e => {
                  e.stopPropagation();
                  this.handleCheck({ id: this.search, name: this.search });
                }}
              >
                <i18n path='生成 "{0}" Tag'>
                  <span class='highlight'>{this.search}</span>
                </i18n>
              </div>
            )}
            {this.renderOptions.map((item, index) => (
              <div
                key={index}
                class={['options-item', { 'active-index': this.hoverActiveIndex === index }]}
                v-bk-overflow-tips={{
                  content: item.name,
                  placement: 'right',
                }}
                onClick={e => {
                  e.stopPropagation();
                  this.handleCheck(item);
                }}
              >
                <TextHighlighter
                  content={item.name}
                  keyword={this.search}
                />
              </div>
            ))}
            {this.scrollLoading && (
              <div class='options-item scroll-loading'>
                <img
                  alt=''
                  src={loadingImg}
                />
              </div>
            )}
          </div>
        )}
      </div>
    );
  },
});
