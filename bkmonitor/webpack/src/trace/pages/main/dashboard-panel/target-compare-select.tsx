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

import { nextTick, onMounted, onUnmounted, shallowReactive, watch } from 'vue';
import { defineComponent, ref, type PropType } from 'vue';

import { $bkPopover } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { throttle } from 'throttle-debounce';

import { getEventPaths } from './utils';

import './target-compare-select.scss';
const INPUT_ITEM = {
  type: 'input',
  id: '___input___',
  name: '___input___',
};

const numClassName = 'num-overflow-item';

interface IItem {
  id: string;
  name: string;
}

interface ILocalListItem extends IItem {
  type?: 'input';
  lightContent?: any;
  isCheck?: boolean;
  show?: boolean;
}

export default defineComponent({
  name: 'TargetCompareSelect',
  props: {
    value: { type: Array as PropType<string[]>, default: () => [] },
    list: { type: Array as PropType<IItem[]>, default: () => [] },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const optionsRef = ref(null);
    const inputRef = ref(null);
    const listRef = ref(null);

    const localValue = ref<ILocalListItem[]>([]);
    let localList: ILocalListItem[] = [];
    const inputValue = ref('');
    const refreshKey = ref('');
    const isExpand = ref(false);
    const classId = ref('');
    const pagination = shallowReactive({
      current: 1,
      count: 0,
      limit: 20,
      data: [],
    });
    const activeIndex = ref(-1);
    const throttleOverflow = throttle(300, handleOverflow);
    let controller = null;
    let observer = null;
    let inputIndex = 0;
    let popoverInstance = null;

    watch(
      () => props.list,
      () => {
        if (!localList.length) {
          getFilterLocalList();
          handleWatchValueChange(props.value);
        }
      }
    );
    watch(() => props.value, handleWatchValueChange);

    init();
    onMounted(() => {
      /* 用于弹层清除 */
      controller?.abort?.();
      controller = new AbortController();
      document.addEventListener('mousedown', handleMousedown, { signal: controller.signal });
      handleResizeObserver();
      setTimeout(() => {
        handleOverflow();
      }, 100);
    });
    onUnmounted(() => {
      controller?.abort?.();
    });

    function init() {
      const value = [];
      for (const item of props.list) {
        if (props.value.indexOf(item.id) > -1) {
          value.push(item);
        }
      }
      localValue.value = value;
      getFilterLocalList();
    }

    function handleWatchValueChange(v) {
      if (
        JSON.stringify(v.filter(item => !!item)) !==
        JSON.stringify(localValue.value.filter(item => item.type !== 'input').map(item => item.id))
      ) {
        init();
        setTimeout(() => {
          handleOverflow();
        }, 100);
      }
    }

    function getFilterLocalList() {
      const values = localValue.value.filter(item => item?.type !== 'input').map(item => item.id);
      localList = props.list.map(item => {
        const isSearch = item.name.indexOf(inputValue.value) >= 0;
        const isHas = values.indexOf(item.id) >= 0;
        return {
          ...item,
          isCheck: isHas,
          show: isSearch,
          lightContent: highLightContent(inputValue.value, item.name),
        };
      });
      setPaginationData(true);
    }
    /* 关键字高亮 */
    function highLightContent(search: string, content: string) {
      if (!search) {
        return content;
      }
      /* 搜索不区分大小写 */
      const searchValue = search.trim().toLowerCase();
      const contentValue = content.toLowerCase();
      /* 获取分隔下标 */
      const indexRanges: number[][] = [];
      const contentValueArr = contentValue.split(searchValue);
      let tempIndex = 0;
      for (const item of contentValueArr) {
        const temp = tempIndex + item.length;
        indexRanges.push([tempIndex, temp]);
        tempIndex = temp + search.length;
      }
      return indexRanges.map((range: number[], index: number) => {
        if (index !== indexRanges.length - 1) {
          return [
            <span key={'key1'}>{content.slice(range[0], range[1])}</span>,
            <span
              key={'key2'}
              class='light'
            >
              {content.slice(range[1], indexRanges[index + 1][0])}
            </span>,
          ];
        }
        return <span key={'key3'}>{content.slice(range[0], range[1])}</span>;
      });
    }

    async function handleOverflow() {
      removeOverflow();
      const list = listRef.value;
      const childs = list?.children || [];
      const listWidth = list?.offsetWidth || 0;
      const overflowTagWidth = 35;
      let totalWidth = 0;
      await nextTick();
      for (const i in childs) {
        const item = childs[i] as HTMLDivElement;
        if (!item.className || item.className.indexOf('list-item') === -1) continue;
        totalWidth += item.offsetWidth + 4;
        // 超出省略
        if (totalWidth + overflowTagWidth > listWidth) {
          const hideNum = localValue.value.length + 1 - +i;
          hideNum > 1 && insertOverflow(item, hideNum > 99 ? 99 : hideNum);
          break;
        }
      }
    }
    function insertOverflow(target, num) {
      if ((isExpand.value && num > 1) || num < 0) return;
      const li = document.createElement('li');
      li.className = numClassName;
      li.innerText = `+${num - 1}`;
      li.addEventListener('click', handleExpandMore, false);
      listRef.value.insertBefore(li, target);
    }
    /* 展开更多 */
    function handleExpandMore(event: Event) {
      event.stopPropagation();
      isExpand.value = !isExpand.value;
      if (isExpand.value) {
        document.addEventListener('click', handleClickOutSide, false);
        handleClickWrap();
      } else {
        document.removeEventListener('click', handleClickOutSide, false);
        setTimeout(() => handleOverflow(), 100);
      }
    }
    function removeOverflow() {
      const overflowList = listRef.value?.querySelectorAll?.(`.${numClassName}`);
      if (!overflowList?.length) return;
      for (const item of overflowList) {
        listRef.value?.removeChild?.(item);
      }
    }
    function handleClickOutSide(evt: Event) {
      const targetEl = evt.target as HTMLBaseElement;
      const pathsClass = JSON.parse(JSON.stringify(getEventPaths(evt).map(item => item.className)));
      const el = document.querySelector('.dashboard-panel__target-compare-select');
      if (
        el.contains(targetEl) ||
        optionsRef.value?.contains?.(targetEl) ||
        pathsClass.some(c => c?.indexOf?.(classId.value) >= 0)
      )
        return;
      isExpand.value = false;
      document.removeEventListener('click', handleClickOutSide, false);
      setTimeout(() => handleOverflow(), 100);
    }
    function handleClickWrap(event?: Event) {
      event?.stopPropagation();
      localValue.value.push(INPUT_ITEM as any);
      inputIndex = localValue.value.length - 1;
      const overflowList = listRef.value?.querySelectorAll?.(`.${numClassName}`);
      if (overflowList?.length) {
        isExpand.value = true;
        document.addEventListener('click', handleClickOutSide, false);
        removeOverflow();
      }
      nextTick(() => {
        inputRef.value?.focus();
        handleShowPop();
      });
    }
    function handBlur() {}
    function handleInput() {
      getFilterLocalList();
    }
    function handleInputKeydown(event: KeyboardEvent) {
      const len = pagination.data.length;
      /* 往下 */
      if (event.code === 'ArrowDown') {
        if (activeIndex.value >= len - 1) {
          activeIndex.value = 0;
        } else {
          activeIndex.value += 1;
        }
      } else if (event.code === 'ArrowUp') {
        /* 往上 */
        if (activeIndex.value <= 0) {
          activeIndex.value = len - 1;
        } else {
          activeIndex.value -= 1;
        }
      } else if (event.code === 'Enter' || event.code === 'NumpadEnter') {
        const item = pagination.data?.[activeIndex.value];
        if (item) {
          handleSelectItem(item);
        }
      }
    }
    function handlePaste(event) {
      event.preventDefault();
      try {
        const pastedText = (event.clipboardData || window.clipboardData).getData('text');
        const list = pastedText.replaceAll('\r', '').split('\n');
        const selects = localValue.value.map(item => item.name);
        for (const str of list) {
          if (selects.indexOf(str) < 0) {
            const item = localList.find(l => l.name === str);
            item && handleSelectItem(item);
          }
        }
      } catch (error) {
        console.log(error);
      }
    }
    function handleClickItem(event: Event, index: number) {
      event.stopPropagation();
      const inputIndexNum = localValue.value.findIndex(item => item?.type === 'input');
      if (inputIndexNum < 0) {
        const overflowList = listRef.value?.querySelectorAll?.(`.${numClassName}`);
        if (overflowList?.length) {
          isExpand.value = true;
          document.addEventListener('click', handleClickOutSide, false);
          removeOverflow();
        }
        inputIndex = index + 1;
        localValue.value.splice(inputIndex, 0, INPUT_ITEM as any);
        nextTick(() => {
          inputRef.value?.focus();
          handleShowPop();
        });
      }
    }

    /* 展开可选项 */
    function handleShowPop() {
      if (!localList.length) {
        removePopoverInstance();
        return;
      }
      removePopoverInstance();
      popoverInstance = $bkPopover({
        target: inputRef.value,
        content: optionsRef.value,
        trigger: 'manual',
        interactive: true,
        theme: 'light common-monitor',
        arrow: false,
        placement: 'bottom-start',
        boundary: 'window',
        hideOnClick: false,
      });
      popoverInstance?.show?.();
    }
    function removePopoverInstance() {
      popoverInstance?.hide?.();
      popoverInstance?.destroy?.();
      popoverInstance = null;
      inputValue.value = '';
    }
    function handleDelete(event: Event, index: number) {
      event.stopPropagation();
      localValue.value.splice(index, 1);
      getFilterLocalList();
      handleEmitValue();
      setTimeout(() => handleOverflow(), 100);
    }
    function handleClearAll(event: Event) {
      event.stopPropagation();
      localValue.value = [];
      isExpand.value = false;
      getFilterLocalList();
      removeOverflow();
    }
    function handleScroll(event) {
      const el = event.target;
      const { scrollHeight, scrollTop, clientHeight } = el;
      if (Math.ceil(scrollTop) + clientHeight >= scrollHeight) {
        setPaginationData(false);
      }
    }
    function handleSelectItem(item) {
      if (item?.isCheck) {
        const delIndex = localValue.value.findIndex(v => v.id === item.id);
        if (delIndex >= 0) {
          localValue.value.splice(delIndex, 1);
          inputIndex = localValue.value.findIndex(v => v?.type === 'input') || 0;
        }
      } else {
        localValue.value.splice(inputIndex, 0, item);
      }
      inputValue.value = '';
      getFilterLocalList();
      nextTick(() => {
        inputPositionExpand();
        inputRef.value?.focus();
        handleShowPop();
      });
    }
    function inputPositionExpand() {
      const distance = inputRef.value.getBoundingClientRect().top - listRef.value.getBoundingClientRect().top;
      if (distance > 22) {
        isExpand.value = true;
        document.addEventListener('click', handleClickOutSide, false);
        setTimeout(() => removeOverflow(), 100);
      }
    }
    function handleMousedown() {
      const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
      if (!pathsClass.includes('target-compare-select-component-list-wrap')) {
        inputRef.value?.blur?.();
        inputValue.value = '';
        if (
          JSON.stringify(props.value.filter(item => !!item)) !==
          JSON.stringify(localValue.value.filter(item => item.type !== 'input').map(item => item.id))
        ) {
          handleEmitValue();
        }
        removePopoverInstance();
        const delIndex = localValue.value.findIndex(item => item?.type === 'input');
        if (delIndex > -1) {
          localValue.value.splice(delIndex, 1);
          refreshKey.value = random(8);
          getFilterLocalList();
          setTimeout(() => {
            handleOverflow();
            handleResizeObserver();
          }, 100);
        }
      }
    }
    function setPaginationData(isInit = true) {
      const showData = localList.filter(item => item.show);
      pagination.count = showData.length;
      if (isInit) {
        pagination.current = 1;
        pagination.data = showData.slice(0, pagination.limit);
      } else {
        if (pagination.current * pagination.limit < pagination.count) {
          pagination.current += 1;
          const temp = showData.slice(
            (pagination.current - 1) * pagination.limit,
            pagination.current * pagination.limit
          );
          pagination.data.push(...temp);
        }
      }
    }
    function handleResizeObserver() {
      observer = new ResizeObserver(() => {
        if (!isExpand.value) {
          throttleOverflow();
        }
      });
      observer.observe(document.querySelector('.dashboard-panel__target-compare-select'));
    }
    function handleEmitValue() {
      emit(
        'change',
        localValue.value.filter(item => item.type !== 'input').map(item => item.id)
      );
    }

    return {
      optionsRef,
      inputRef,
      listRef,
      localValue,
      inputValue,
      refreshKey,
      isExpand,
      classId,
      pagination,
      activeIndex,
      handleClickWrap,
      handBlur,
      handleInput,
      handleInputKeydown,
      handlePaste,
      handleClickItem,
      handleDelete,
      handleClearAll,
      handleScroll,
      handleSelectItem,
      handleMousedown,
    };
  },
  render() {
    return (
      <div
        key={this.refreshKey}
        class={['dashboard-panel__target-compare-select', { 'is-expand': this.isExpand }]}
        onClick={this.handleClickWrap}
      >
        <ul
          ref='list'
          class='more-list'
          onClick={this.handleClickWrap}
        >
          {this.localValue.map((item, index) =>
            item?.type === 'input' ? (
              <div
                key={index}
                class='input-wrap'
              >
                <span class='input-value'>{this.inputValue}</span>
                <input
                  ref='input'
                  class='input'
                  v-model={this.inputValue}
                  onBlur={this.handBlur}
                  onInput={this.handleInput}
                  onKeydown={e => this.handleInputKeydown(e)}
                  onPaste={this.handlePaste}
                />
              </div>
            ) : (
              <li
                key={index}
                class='list-item'
                onClick={(event: Event) => this.handleClickItem(event, index)}
              >
                <div class='item-name'>{item.name}</div>
                <span
                  class='icon-monitor icon-mc-close'
                  onClick={(event: Event) => this.handleDelete(event, index)}
                />
              </li>
            )
          )}
        </ul>
        {!!this.localValue.filter(item => item?.type !== 'input').length && (
          <div class='right-wrap'>
            <div
              class='close-all'
              onClick={e => this.handleClearAll(e)}
            >
              <span class='icon-monitor icon-mc-close-fill' />
            </div>
          </div>
        )}
        {!this.localValue.length && <span class='placeholder-wrap'>{this.$t('选择目标')}</span>}
        <div style='display: none'>
          <div
            ref='options'
            class={[
              'target-compare-select-component-list-wrap',
              { 'no-data': !this.pagination.data.filter(item => !!item.show).length },
            ]}
            onScroll={this.handleScroll}
          >
            {this.pagination.data
              .filter(item => !!item.show)
              .map((item, index) => (
                <div
                  key={item.id}
                  class={[`list-item ${this.classId}`, { active: this.activeIndex === index }]}
                  onClick={() => this.handleSelectItem(item)}
                >
                  <span>{item.lightContent || item.name}</span>
                  {!!item?.isCheck && <span class='icon-monitor icon-mc-check-small' />}
                </div>
              ))}
          </div>
        </div>
      </div>
    );
  },
});
