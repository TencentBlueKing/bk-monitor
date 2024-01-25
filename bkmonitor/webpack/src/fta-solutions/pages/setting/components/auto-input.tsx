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

import './auto-input.scss';

interface IAutoInput {
  tipsData?: { id: string; name: string }[];
  value?: string;
}
interface IAutoInputEvent {
  onChange?: string;
}

@Component({
  name: 'AutoInput'
})
export default class AutoInput extends tsc<IAutoInput, IAutoInputEvent> {
  @Prop({ type: Array, default: () => [] }) tipsData: IAutoInput['tipsData'];
  @Prop({ type: String }) value: string;

  @Ref('list') listRef: HTMLDivElement;

  offsetX = 0; // 补全提示列表offsetX/offsetY
  offsetY = 0;
  oldVal = ''; // 输入旧值
  keyword = ''; // 关键词
  params = ''; // 对外输出参数
  startIndex = 0; // 光标在关键字的起始位置
  curIndex = 0; // 光标的当前位置
  popoverInstance = null;

  @Watch('value', { immediate: true })
  handleValue(v) {
    this.params = v;
  }

  @Emit('input')
  emitData(val): void {
    return val;
  }
  @Emit('change')
  handleChange(val) {
    return val;
  }

  // 计算补全列表的offsetX
  getOffset(): void {
    this.$nextTick(() => {
      const ref: any = this.$refs.input;
      const bkInputLeft = ref.$el.getBoundingClientRect().left;
      const inputRectLeft = ref.$el.getElementsByTagName('input')[0].getBoundingClientRect().left;
      this.offsetX = inputRectLeft - bkInputLeft;
    });
  }

  // 处理输入
  handleInput(val: string, evt: any): void {
    this.handleInputEvt(evt);
    this.getOffset();
    if (!this.params || !this.tipsData.find(item => item.id.includes(this.keyword))) {
      return this.handleDestroyPopover();
    }
    this.handlePopoverShow();
  }
  // 处理输入事件数据
  handleInputEvt(evt): void {
    // 最新值
    const { target } = evt;
    const newVal: string = target.value;
    this.getIndex(newVal, this.oldVal);
    this.keyword = this.handleKeyword();
    this.oldVal = newVal;
    this.emitData(newVal);
    this.handleChange(newVal);
  }

  // 处理关键字
  handleKeyword(): string {
    return this.params
      .slice(this.startIndex, this.curIndex + 1)
      .replace(/({{)|(}})/g, '')
      .trim();
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

  // 提示列表显示方法
  handlePopoverShow(): void {
    if (!this.listRef) return;
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.$el, {
        content: this.listRef,
        arrow: false,
        flip: false,
        flipBehavior: 'bottom',
        trigger: 'manul',
        placement: 'top-start',
        theme: 'light auto-input-component-list-warp',
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
    this.popoverInstance?.show(100);
  }

  // 隐藏
  handleDestroyPopover(): void {
    if (this.popoverInstance) {
      this.popoverInstance.hide(0);
      this.popoverInstance.destroy?.();
      this.popoverInstance = null;
    }
  }

  // 点击选中
  handleMousedown(item): void {
    const paramsArr = this.params.split('');
    paramsArr.splice(this.startIndex, this.curIndex - this.startIndex + 1, `{{${item.id}}}`);
    this.params = `${paramsArr.join('')}`;
    this.emitData(this.params);
    this.handleChange(this.params);
    this.oldVal = this.params;
  }

  render() {
    return (
      <div class='auto-input-component-setting'>
        <bk-input
          v-model={this.params}
          type='text'
          ref='input'
          behavior={'simplicity'}
          on-input={this.handleInput}
        ></bk-input>
        <div style={{ display: 'none' }}>
          <ul
            ref='list'
            class='auto-input-component-list'
          >
            {this.tipsData.map((item, index) => (
              <li
                class='list-item'
                on-mousedown={() => this.handleMousedown(item)}
                key={item.id + index}
                style={{
                  display: !this.params || item.id.includes(this.keyword) ? 'flex' : 'none',
                  position: 'relative'
                }}
              >
                {item.id}
                <span class='item-desc'>{item.name}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
