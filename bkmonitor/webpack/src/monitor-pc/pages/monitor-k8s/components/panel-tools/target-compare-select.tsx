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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';
import { throttle } from 'throttle-debounce';

import { getEventPaths } from '../../../../utils';

import './target-compare-select.scss';

interface IItem {
  id: string;
  name: string;
}
interface ILocalListItem extends IItem {
  isCheck?: boolean;
  lightContent?: any;
  show?: boolean;
  type?: 'input';
}
interface IProps {
  filterList?: IItem[];
  list: IItem[];
  value: string[];
  onChange?: (v: string[]) => void;
}

const INPUT_ITEM = {
  type: 'input',
  id: '___input___',
  name: '___input___',
};

const numClassName = 'num-overflow-item';
@Component
export default class TargetCompareSelect extends tsc<IProps> {
  /* 当前已选项 */
  @Prop({ type: Array, default: () => [] }) value: string[];
  /* 所有可选项 */
  @Prop({ type: Array, default: () => [] }) list: IItem[];

  @Ref('options') optionsRef: HTMLDivElement;
  @Ref('input') inputRef: HTMLDivElement;
  @Ref('list') listRef: HTMLDivElement;
  /* 当前值 */
  localValue: ILocalListItem[] = [];
  /* 当前可选项 */
  localList: ILocalListItem[] = [];
  /* 输入框的值 */
  inputValue = '';
  /* 输入框的位置 */
  inputIndex = 0;
  /* 弹出层实例 */
  popoverInstance = null;
  /* 是否展开 */
  isExpand = false;
  /* controller */
  controller = null;
  /* 刷新 */
  refreshKey = random(8);
  /* 当前可选项选中位置 按上键减一， 按下键加一 */
  activeIndex = -1;
  /* 监听容器宽度的变化 */
  observer = null;
  /* 用于判断收起逻辑 */
  classId = random(8);
  /* 当前分页数据 */
  pagination: {
    count: number;
    current: number;
    data: ILocalListItem[];
    limit: number;
  } = {
    current: 1,
    count: 0,
    limit: 20,
    data: [],
  };
  /* 监听容器宽度的变化(节流) */
  throttleOverflow = () => {};

  @Watch('list')
  handleFilterList() {
    if (!this.localList.length) {
      // this.localList = [...v];
      this.getFilterLocalList();
      this.handleWatchValueChange(this.value);
    }
  }
  @Watch('value')
  handleWatchValueChange(v) {
    if (
      JSON.stringify(v.filter(item => !!item)) !==
      JSON.stringify(this.localValue.filter(item => item.type !== 'input').map(item => item.id))
    ) {
      this.init();
      setTimeout(() => {
        this.handleOverflow();
      }, 100);
    }
  }
  /* 初始化 */
  created() {
    this.init();
    this.throttleOverflow = throttle(300, this.handleOverflow);
  }
  init() {
    const value = [];
    this.list.forEach(item => {
      if (this.value.indexOf(item.id) > -1) {
        value.push(item);
      }
    });
    this.localValue = value;
    this.getFilterLocalList();
  }
  mounted() {
    /* 用于弹层清除 */
    this.controller?.abort?.();
    this.controller = new AbortController();
    document.addEventListener('mousedown', this.handleMousedown, { signal: this.controller.signal });
    this.handleResizeObserver();
    setTimeout(() => {
      this.handleOverflow();
    }, 100);
  }
  destroyed() {
    this.controller?.abort?.();
  }
  handleMousedown(event: Event) {
    const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
    if (!pathsClass.includes('target-compare-select-component-list-wrap')) {
      this.inputRef?.blur?.();
      this.inputValue = '';
      if (
        JSON.stringify(this.value.filter(item => !!item)) !==
        JSON.stringify(this.localValue.filter(item => item.type !== 'input').map(item => item.id))
      ) {
        this.handleEmitValue();
      }
      this.removePopoverInstance();
      const delIndex = this.localValue.findIndex(item => item?.type === 'input');
      if (delIndex > -1) {
        this.localValue.splice(delIndex, 1);
        this.refreshKey = random(8);
        this.getFilterLocalList();
        setTimeout(() => {
          this.handleOverflow();
          this.handleResizeObserver();
        }, 100);
      }
    }
  }

  async handleOverflow() {
    this.removeOverflow();
    const list = this.listRef;
    const childs = list?.children || [];
    const listWidth = list?.offsetWidth || 0;
    const overflowTagWidth = 35;
    let totalWidth = 0;
    await this.$nextTick();

    for (const i in childs) {
      const item = childs[i] as HTMLDivElement;
      if (!item.className || item.className.indexOf('list-item') === -1) continue;
      totalWidth += item.offsetWidth + 4;
      // 超出省略
      if (totalWidth + overflowTagWidth > listWidth) {
        const hideNum = this.localValue.length + 1 - +i;
        hideNum > 1 && this.insertOverflow(item, hideNum > 99 ? 99 : hideNum);
        break;
      }
    }
  }
  /* 展示溢出数量 */
  insertOverflow(target, num) {
    if ((this.isExpand && num > 1) || num < 0) return;
    const li = document.createElement('li');
    li.className = numClassName;
    li.innerText = `+${num - 1}`;
    li.addEventListener('click', this.handleExpandMore, false);
    this.listRef.insertBefore(li, target);
  }
  /* 收起更多 */
  handleClickOutSide(evt: Event) {
    const targetEl = evt.target as HTMLBaseElement;
    const pathsClass = JSON.parse(JSON.stringify(getEventPaths(evt).map(item => item.className)));
    if (
      this.$el.contains(targetEl) ||
      this.optionsRef?.contains?.(targetEl) ||
      pathsClass.some(c => c?.indexOf?.(this.classId) >= 0)
    )
      return;
    this.isExpand = false;
    document.removeEventListener('click', this.handleClickOutSide, false);
    setTimeout(() => this.handleOverflow(), 100);
  }
  /* 展开更多 */
  handleExpandMore(event: Event) {
    event.stopPropagation();
    this.isExpand = !this.isExpand;
    if (this.isExpand) {
      document.addEventListener('click', this.handleClickOutSide, false);
      this.handleClickWrap();
    } else {
      document.removeEventListener('click', this.handleClickOutSide, false);
      setTimeout(() => this.handleOverflow(), 100);
    }
  }
  /* 删除溢出数量 */
  removeOverflow() {
    const overflowList = this.listRef?.querySelectorAll?.(`.${numClassName}`);
    if (!overflowList?.length) return;
    overflowList.forEach(item => {
      this.listRef?.removeChild?.(item);
    });
  }
  /* 监听容器变化 */
  handleResizeObserver() {
    this.observer = new ResizeObserver(() => {
      if (!this.isExpand) {
        this.throttleOverflow();
      }
    });
    this.observer.observe(this.$el);
  }
  /* 筛选可选项列表 */
  getFilterLocalList() {
    const values = this.localValue.filter(item => item?.type !== 'input').map(item => item.id);
    this.localList = this.list.map(item => {
      const isSearch = item.name.indexOf(this.inputValue) >= 0;
      const isHas = values.indexOf(item.id) >= 0;
      return {
        ...item,
        isCheck: isHas,
        show: isSearch,
        lightContent: this.highLightContent(this.inputValue, item.name),
      };
    });
    this.setPaginationData(true);
  }
  setPaginationData(isInit = false) {
    const showData = this.localList.filter(item => item.show);
    this.pagination.count = showData.length;
    if (isInit) {
      this.pagination.current = 1;
      this.pagination.data = showData.slice(0, this.pagination.limit);
    } else {
      if (this.pagination.current * this.pagination.limit < this.pagination.count) {
        this.pagination.current += 1;
        const temp = showData.slice(
          (this.pagination.current - 1) * this.pagination.limit,
          this.pagination.current * this.pagination.limit
        );
        this.pagination.data.push(...temp);
      }
    }
  }
  /* 关键字高亮 */
  highLightContent(search: string, content: string) {
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
    contentValueArr.forEach(item => {
      const temp = tempIndex + item.length;
      indexRanges.push([tempIndex, temp]);
      tempIndex = temp + search.length;
    });
    return indexRanges.map((range: number[], index: number) => {
      if (index !== indexRanges.length - 1) {
        return [
          <span>{content.slice(range[0], range[1])}</span>,
          <span class='light'>{content.slice(range[1], indexRanges[index + 1][0])}</span>,
        ];
      }
      return <span>{content.slice(range[0], range[1])}</span>;
    });
  }
  /* 选中选项，并弹出可选项 */
  handleClickItem(event: Event, index: number) {
    event.stopPropagation();
    const inputIndex = this.localValue.findIndex(item => item?.type === 'input');
    if (inputIndex < 0) {
      const overflowList = this.listRef?.querySelectorAll?.(`.${numClassName}`);
      if (overflowList?.length) {
        this.isExpand = true;
        document.addEventListener('click', this.handleClickOutSide, false);
        this.removeOverflow();
      }
      this.inputIndex = index + 1;
      this.localValue.splice(this.inputIndex, 0, INPUT_ITEM as any);
      this.$nextTick(() => {
        this.inputRef?.focus();
        this.handleShowPop();
      });
    }
  }
  /* 删除 */
  handleDelete(event: Event, index: number) {
    event.stopPropagation();
    this.localValue.splice(index, 1);
    this.getFilterLocalList();
    this.handleEmitValue();
    setTimeout(() => this.handleOverflow(), 100);
  }
  /* 展开可选项 */
  handleShowPop() {
    if (!this.localList.length) {
      this.removePopoverInstance();
      return;
    }
    this.removePopoverInstance();
    this.popoverInstance = this.$bkPopover(this.inputRef, {
      content: this.optionsRef,
      trigger: 'manual',
      interactive: true,
      theme: 'light common-monitor',
      arrow: false,
      placement: 'bottom-start',
      boundary: 'window',
      hideOnClick: false,
    });
    this.popoverInstance?.show?.();
  }
  /* 清空pop */
  removePopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.inputValue = '';
  }
  /* 点击列表 */
  handleClickWrap(event?: Event) {
    event?.stopPropagation();
    this.localValue.push(INPUT_ITEM as any);
    this.inputIndex = this.localValue.length - 1;
    const overflowList = this.listRef?.querySelectorAll?.(`.${numClassName}`);
    if (overflowList?.length) {
      this.isExpand = true;
      document.addEventListener('click', this.handleClickOutSide, false);
      this.removeOverflow();
    }
    this.$nextTick(() => {
      this.inputRef?.focus();
      this.handleShowPop();
    });
  }
  /* 选择 */
  handleSelectItem(item) {
    if (item?.isCheck) {
      const delIndex = this.localValue.findIndex(v => v.id === item.id);
      if (delIndex >= 0) {
        this.localValue.splice(delIndex, 1);
        this.inputIndex = this.localValue.findIndex(v => v?.type === 'input') || 0;
      }
    } else {
      this.localValue.splice(this.inputIndex, 0, item);
    }
    this.inputValue = '';
    this.getFilterLocalList();
    this.$nextTick(() => {
      this.inputPostionExpand();
      this.inputRef?.focus();
      this.handleShowPop();
    });
  }

  /* 判断当前输入位置是否在第多行 */
  inputPostionExpand() {
    const distance = this.inputRef.getBoundingClientRect().top - this.listRef.getBoundingClientRect().top;
    if (distance > 22) {
      this.isExpand = true;
      document.addEventListener('click', this.handleClickOutSide, false);
      setTimeout(() => this.removeOverflow(), 100);
    }
  }

  handBlur() {}
  handleInput() {
    this.getFilterLocalList();
  }
  handleInputKeydown(event: KeyboardEvent) {
    const len = this.pagination.data.length;
    /* 往下 */
    if (event.code === 'ArrowDown') {
      if (this.activeIndex >= len - 1) {
        this.activeIndex = 0;
      } else {
        this.activeIndex += 1;
      }
    } else if (event.code === 'ArrowUp') {
      /* 往上 */
      if (this.activeIndex <= 0) {
        this.activeIndex = len - 1;
      } else {
        this.activeIndex -= 1;
      }
    } else if (event.code === 'Enter' || event.code === 'NumpadEnter') {
      const item = this.pagination.data?.[this.activeIndex];
      if (item) {
        this.handleSelectItem(item);
      }
    }
  }

  handleClearAll(event: Event) {
    event.stopPropagation();
    this.localValue = [];
    this.isExpand = false;
    this.getFilterLocalList();
    this.removeOverflow();
  }

  @Emit('change')
  handleEmitValue() {
    return this.localValue.filter(item => item.type !== 'input').map(item => item.id);
  }

  handleScroll(event) {
    const el = event.target;
    const { scrollHeight, scrollTop, clientHeight } = el;
    if (Math.ceil(scrollTop) + clientHeight >= scrollHeight) {
      this.setPaginationData(false);
    }
  }

  handlePaste(event) {
    event.preventDefault();
    try {
      const pastedText = (event.clipboardData || window.clipboardData).getData('text');
      const list = pastedText.replaceAll('\r', '').split('\n');
      const selects = this.localValue.map(item => item.name);
      list.forEach(str => {
        if (selects.indexOf(str) < 0) {
          const item = this.localList.find(l => l.name === str);
          item && this.handleSelectItem(item);
        }
      });
    } catch (error) {
      console.log(error);
    }
  }

  render() {
    return (
      <div
        key={this.refreshKey}
        class={['target-compare-select-component', { 'is-expand': this.isExpand }]}
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
  }
}
