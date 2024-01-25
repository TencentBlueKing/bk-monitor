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
import { Component, Emit, Model, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './auto-input.scss';

interface ITipsList {
  id: string;
  name: string;
}

interface IAuto {
  value?: string;
  tipsList?: ITipsList[];
  placeholder?: string;
  readonly?: boolean;
}

@Component
export default class AutoInput extends tsc<IAuto> {
  @Model('input', { default: '', type: String }) value: string;
  @Prop({ default: () => [], type: Array }) tipsList: ITipsList[];
  @Prop({ default: '', type: String }) placeholder: string;
  @Prop({ default: false, type: Boolean }) readonly: boolean;

  popoverInstance: any = null;
  offsetX = 0;
  offsetY = 0;
  keyword = '';
  oldVal = '';
  startIndex = 0;
  curIndex = 0;

  get tipsListFiter() {
    return this.tipsList.filter(item => item.id.indexOf(this.keyword) > -1);
  }

  @Ref('tips-list') tipsListEl: HTMLElement;
  @Ref('input') inputEl: HTMLElement;

  @Emit('change')
  @Emit('input')
  emitValue(val) {
    return val;
  }

  // 输入事件
  handleInput(val, evt) {
    this.handleInputEvt(evt);
    if (!this.value || !this.tipsListFiter.length) {
      return this.handleDestroyPopover();
    }
    this.handlePopoverShow();
    this.emitValue(val);
  }

  // 处理输入事件数据
  handleInputEvt(evt) {
    // 最新值
    const { target } = evt;
    const newVal: string = target.value;
    this.getIndex(newVal, this.oldVal);
    this.keyword = this.handleKeyword(newVal);
    this.oldVal = newVal;
    this.emitValue(newVal);
  }

  // 获取光标的位置
  getIndex(newVal: string, oldVal: string): number {
    const tempStr = newVal.length > oldVal.length ? newVal : oldVal;
    let diffIndex = 0;
    tempStr.split('').find((item, idx) => {
      diffIndex = idx;
      return oldVal[idx] !== newVal[idx];
    });
    this.curIndex = diffIndex;
    if (newVal[diffIndex] === '{' && newVal[diffIndex - 1] === '{') {
      this.startIndex = diffIndex - 1;
    }
    // 当出现{{{{
    if (this.curIndex) {
      if (newVal.indexOf('{{{{') > -1) {
        this.curIndex = this.curIndex - 2;
        this.startIndex = this.startIndex - 2;
      }
    }
    return diffIndex;
  }

  // 点击选中
  handleMousedown(item: ITipsList) {
    const paramsArr = this.value.split('');
    paramsArr.splice(this.startIndex, this.curIndex - this.startIndex + 1, `{{${item.id}}}`);
    this.emitValue(paramsArr.join(''));
    this.oldVal = this.value;
    this.keyword = '';
  }

  // 处理关键字
  handleKeyword(newVal: string): string {
    return newVal
      .slice(this.startIndex, this.curIndex + 1)
      .replace(/({)|(})/g, '')
      .trim();
  }

  // 提示列表显示方法
  handlePopoverShow() {
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.inputEl, {
        content: this.tipsListEl,
        arrow: false,
        flip: false,
        flipBehavior: 'bottom',
        trigger: 'manul',
        placement: 'top-start',
        theme: 'light auto-input',
        maxWidth: 520,
        duration: [200, 0],
        offset: `${this.offsetX}, ${this.offsetY}`
      });
    } else {
      // 更新提示的位置
      this.popoverInstance.set({
        offset: `${this.offsetX}, ${this.offsetY}`
      });
    }
    // 显示
    this.popoverInstance.show(100);
  }

  // 隐藏
  handleDestroyPopover(): void {
    if (this.popoverInstance) {
      this.popoverInstance.hide(0);
      this.popoverInstance.destroy?.();
      this.popoverInstance = null;
    }
  }

  protected render() {
    return (
      <div class='auto-input-wrap'>
        <div ref='input'>
          <bk-input
            value={this.value}
            behavior={'simplicity'}
            onInput={this.handleInput}
            readonly={this.readonly}
            placeholder={this.placeholder || this.$t('输入')}
          ></bk-input>
        </div>
        <div style='display: none'>
          <ul
            ref='tips-list'
            class='tips-list-wrap'
          >
            {this.tipsListFiter.map((item, index) => (
              <li
                class='list-item'
                key={index}
                onMousedown={() => this.handleMousedown(item)}
              >
                <span>{item.id}</span>
                <span class='item-desc'>{item.name}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
