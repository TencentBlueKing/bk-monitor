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

import { computed, defineComponent, nextTick, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue';

import { useEventListener, watchDebounced } from '@vueuse/core';
import { promiseTimeout } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

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
    const { t } = useI18n();
    const elRef = useTemplateRef<HTMLDivElement>('el');

    const localOptions = shallowRef<IValue[]>([]);
    const loading = shallowRef(false);
    const hoverActiveIndex = shallowRef(-1);
    const scrollLoading = shallowRef(false);
    const pageSize = shallowRef(200);
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
            const list = await getValueData(false, true);
            localOptions.value = localOptionsFilter(list);
            cleanup = useEventListener(window, 'keydown', handleKeydownEvent);
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

    onUnmounted(() => {
      cleanup?.();
    });

    async function init() {
      if (!props.isPopover) {
        dataInit();
        const list = await getValueData(false, true);
        localOptions.value = localOptionsFilter(list);
        cleanup = useEventListener(window, 'keydown', handleKeydownEvent);
      }
    }
    /**
     * @description 初始化数据状态
     * 重置选项列表、悬浮索引、分页数据和结束标记
     */
    function dataInit() {
      localOptions.value = [];
      hoverActiveIndex.value = -1;
      page.value = 1;
      isEnd.value = false;
    }
    /**
     * 处理键盘事件的函数，用于实现选项列表的上下键导航和回车选择功能
     * @param {KeyboardEvent} event - 键盘事件对象
     *
     * @description
     * - 当按下向上箭头键时，将选中项索引减1
     * - 当按下向下箭头键时，将选中项索引加1
     * - 当按下回车键时，触发选项确认
     * - 如果 needUpDownCheck 为 false，则不处理任何键盘事件
     * - 索引变化时会自动处理边界情况，确保不会超出有效范围
     */
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
          if (!(event.ctrlKey || event.metaKey)) {
            handleOptionsEnter();
            emit(
              'isChecked',
              hoverActiveIndex.value >= 0 &&
                hoverActiveIndex.value <= renderOptions.value.length - 1 &&
                !!renderOptions.value.length
            );
          }
          break;
        }
      }
    }
    /**
     * 更新选中状态并处理滚动位置
     *
     * 该函数执行两个主要操作：
     * 1. 根据悬停索引位置发送选中状态
     * 2. 将当前选中项滚动到可视区域
     *
     * @emits isChecked - 发送选中状态，当悬停索引在有效范围内时为 true
     */
    function updateSelection() {
      emit(
        'isChecked',
        hoverActiveIndex.value >= 0 &&
          hoverActiveIndex.value <= renderOptions.value.length - 1 &&
          !!renderOptions.value.length
      );
      nextTick(() => {
        const listEl = elRef.value?.querySelector('.options-drop-down-wrap.main__wrap');
        const el = hasCustomOption.value
          ? listEl?.children?.[hoverActiveIndex.value + 1]
          : listEl?.children?.[hoverActiveIndex.value];
        if (el) {
          el.scrollIntoView(false);
        }
      });
    }
    /**
     * 处理选项回车事件
     * 当鼠标悬停在某个选项上时(hoverActiveIndex不为-1),
     * 触发该选项的选中事件
     */
    function handleOptionsEnter() {
      if (hoverActiveIndex.value !== -1) {
        const item = renderOptions.value?.[hoverActiveIndex.value];
        if (item) {
          handleCheck(item);
        }
      }
    }
    /**
     * 处理滚动事件,实现滚动加载更多数据的功能
     * @param {Event} event - 滚动事件对象
     * @description
     * 1. 监听滚动容器的滚动位置
     * 2. 当滚动到底部时(距离底部小于3px),触发加载更多
     * 3. 通过 scrollLoading 和 isEnd 标记控制加载状态
     * 4. 加载成功后更新本地选项数据
     */
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
    /**
     * 处理选中事件
     * @param {IValue} item - 选中的值对象
     * @description 当选项被选中时触发，通过 emit 方法向父组件发送 'select' 事件并传递选中项
     */
    function handleCheck(item: IValue) {
      emit('select', item);
    }
    /**
     * 获取值数据的异步函数
     * @param {boolean} isScroll - 是否为滚动加载，默认为 false
     * @returns {Promise<Array>} 返回获取到的数据列表
     * @description
     * - 当启用选项时，通过 getValueFn 获取数据
     * - 支持分页加载和搜索功能
     * - 处理加载状态和滚动加载状态
     * - 判断是否到达数据末尾
     */
    async function getValueData(isScroll = false, isInit = false) {
      let list = [];
      if (isScroll) {
        scrollLoading.value = true;
      } else {
        loading.value = true;
      }
      if (props.fieldInfo?.isEnableOptions) {
        const limit = pageSize.value * page.value;
        await promiseTimeout(300);
        const data = await props.getValueFn({
          search: props.search,
          limit,
          field: props.fieldInfo.field,
          isInit__: isInit,
        });
        list = data.list;
        isEnd.value = limit > data.count;
      }
      scrollLoading.value = false;
      loading.value = false;
      return list;
    }
    /**
     * 过滤本地选项列表
     * @param {IValue[]} list - 选项值列表
     * @returns {IValue[]} 过滤后的列表
     * @description 当列表为空时,页码加1;返回原始列表
     */
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
      t,
    };
  },
  render() {
    return (
      <div
        ref='el'
        style={
          this.width
            ? {
                width: `${Math.max(222, this.width)}px`,
              }
            : {}
        }
        class='vue3_retrieval-filter__value-options-select-component'
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
              <span class='no-data-text'>{this.t('暂无数据，请输入生成')}</span>
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
                <i18n-t keypath='直接输入 "{0}"'>
                  <span class='highlight'>{this.search}</span>
                </i18n-t>
              </div>
            )}
            {this.renderOptions.map((item, index) => (
              <div
                key={index}
                class={['options-item', { 'active-index': this.hoverActiveIndex === index }]}
                onClick={e => {
                  e.stopPropagation();
                  this.handleCheck(item);
                }}
              >
                <TextHighlighter
                  class='title__text'
                  v-overflow-tips={{
                    content: item.name,
                    placement: 'top',
                  }}
                  content={item.name}
                  keyword={this.search}
                />
                {item.id !== item.name ? (
                  <TextHighlighter
                    class={item.name ? 'subtitle__text' : 'title__text'}
                    v-overflow-tips={{
                      content: item.id,
                      placement: 'top',
                    }}
                    content={item.name && item.id !== '' ? `（${item.id}）` : item.id}
                    keyword={this.search}
                  />
                ) : (
                  ''
                )}
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
