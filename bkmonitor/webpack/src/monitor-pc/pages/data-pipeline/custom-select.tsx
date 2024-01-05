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

import { getEventPaths } from '../../utils';

import './custom-select.scss';

interface IListItem {
  id: string;
  name: string;
  isCheck?: boolean;
}

interface IProps {
  value?: string[];
  list?: IListItem[];
  onChange?: (v: string[]) => void;
  onPack?: () => void;
}

const componentClassNames = {
  selectInput: 'data-pipeline-select-content',
  pop: 'data-pipeline-select-component-popover-content'
};
const rightIconClassName = 'data-pipeline-select-right-icon';

@Component
export default class CustomSelect extends tsc<IProps> {
  /* 当前选中的空间 */
  @Prop({ default: () => [], type: Array }) value: string[];
  /* 所有空间列表 */
  @Prop({ default: () => [], type: Array }) list: IListItem[];
  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('select') selectRef: HTMLDivElement;

  localValue: string[] = [];
  /* 可选列表 */
  localList: IListItem[] = [];
  /* 弹出实例 */
  popInstance = null;
  /* 添加可被移除的事件监听器 */
  controller: AbortController = null;
  /* 已选择部分文字 */
  valueStr = '';
  /* 是否标红 */
  isErr = false;
  /* 是否弹出弹窗 */
  isOpen = false;
  width = 100;

  @Watch('value')
  handleWatchValue(v: string[]) {
    if (JSON.stringify(v) === JSON.stringify(this.localValue)) {
      return;
    }
    this.localValue = this.value;
    const strs = [];
    this.localList.forEach(item => {
      const has = v.includes(item.id);
      item.isCheck = has;
      if (has) {
        strs.push(item.name);
      }
    });
    this.valueStr = strs.join(',');
  }
  @Emit('change')
  handleChange() {
    return this.localValue;
  }

  mounted() {
    this.width = this.selectRef.offsetWidth;
  }

  created() {
    this.localList = [
      // { id: 'all', name: this.$tc('全部'), isCheck: false },
      ...this.list.map(item => ({ ...item, isCheck: false }))
    ];
    if (this.value.length) {
      this.handleWatchValue(this.value);
    }
  }
  /* 显示弹出层 */
  handleMousedown() {
    if (this.popInstance) {
      return;
    }
    const target = this.selectRef;
    this.popInstance = this.$bkPopover(target, {
      content: this.wrapRef,
      trigger: 'manual',
      interactive: true,
      theme: 'light common-monitor',
      arrow: false,
      placement: 'bottom-start',
      boundary: 'window',
      hideOnClick: false
    });
    this.popInstance?.show?.();
    this.isOpen = true;
    setTimeout(() => {
      this.addMousedownEvent();
    }, 50);
  }
  /* 添加清楚弹出层事件 */
  addMousedownEvent() {
    this.controller?.abort?.();
    this.controller = new AbortController();
    document.addEventListener('mousedown', this.handleMousedownRemovePop, { signal: this.controller.signal });
  }
  /* 清除弹出实例 */
  handleMousedownRemovePop(event: Event) {
    const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
    if (pathsClass.includes(rightIconClassName)) {
      return;
    }
    if (pathsClass.includes(componentClassNames.pop)) {
      return;
    }
    this.handlePopoverHidden();
  }
  /* 清楚弹出层 */
  handlePopoverHidden() {
    this.popInstance?.hide?.(0);
    this.popInstance?.destroy?.();
    this.popInstance = null;
    this.controller?.abort?.();
    this.isOpen = false;
    this.$emit('pack');
  }

  selectOption(item: IListItem, v: boolean) {
    this.localList.forEach(l => {
      if (item.id === 'all') {
        if (l.id === item.id) {
          l.isCheck = v;
        } else {
          l.isCheck = false;
        }
      } else {
        if (l.id === 'all') {
          l.isCheck = false;
        } else if (l.id === item.id) {
          l.isCheck = v;
        }
      }
    });
  }
  /* check */
  handleSelectOption(item: IListItem) {
    this.selectOption(item, !item.isCheck);
    this.getLocalValue();
  }
  handleCheckOption(v: boolean, item: IListItem) {
    this.selectOption(item, v);
    this.getLocalValue();
  }
  /* 获取当前选中的值 */
  getLocalValue() {
    const value = [];
    const strs = [];
    this.localList.forEach(item => {
      if (item.isCheck) {
        value.push(item.id);
        strs.push(item.name);
      }
    });
    this.valueStr = strs.join(',');
    this.localValue = value;
    this.handleChange();
  }
  /* 清空 */
  handleClear(e: Event) {
    e.stopPropagation();
    this.localValue = [];
    this.valueStr = '';
    this.localList.forEach(item => {
      item.isCheck = false;
    });
    this.handleChange();
  }

  render() {
    return (
      <span class={['data-pipeline-select-component', { error: this.isErr }, { active: this.isOpen }]}>
        <div
          ref='select'
          class={componentClassNames.selectInput}
          onMousedown={this.handleMousedown}
        >
          <span class='selected-text'>{this.valueStr}</span>
          <span
            class={rightIconClassName}
            onClick={e => this.handleClear(e)}
          >
            <span class='icon-monitor icon-arrow-down'></span>
            <span class='icon-monitor icon-mc-close-fill'></span>
          </span>
        </div>
        <div style={{ display: 'none' }}>
          <div
            class={componentClassNames.pop}
            ref='wrap'
            style={{ width: `${this.width}px` }}
          >
            <div class='select-list'>
              {this.localList.map(item => (
                <div
                  class={'select-list-item'}
                  key={item.id}
                  onClick={() => this.handleSelectOption(item)}
                >
                  <div onClick={(e: Event) => e.stopPropagation()}>
                    <bk-checkbox
                      value={item.isCheck}
                      onChange={v => this.handleCheckOption(v, item)}
                    ></bk-checkbox>
                  </div>
                  <span
                    class='name'
                    v-bk-overflow-tips
                  >
                    {item.name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </span>
    );
  }
}
