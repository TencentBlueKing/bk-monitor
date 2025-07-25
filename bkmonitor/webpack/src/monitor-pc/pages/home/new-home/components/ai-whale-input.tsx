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

import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import aiWhaleSrc from '../../../../static/images/png/new-page/aiWhale.png';

import './ai-whale-input.scss';

interface IAiWhaleInputEvent {
  onKeyDown: KeyboardEvent;
}

interface IAiWhaleInputProps {
  categoriesHasTwoRows: boolean;
}

@Component
export default class AiWhaleInput extends tsc<IAiWhaleInputProps, IAiWhaleInputEvent> {
  /* 是否为两列布局 */
  @Prop({ default: false, type: Boolean }) categoriesHasTwoRows: boolean;
  // @Prop({ default: false, type: Boolean }) showPlaceholder: boolean;

  /* 展示Placeholder */
  showPlaceholder = true;
  /* AI小鲸 placeHolder 内容  */
  placeholderText = window.i18n.tc('有问题就问 AI 小鲸');

  // 插入回车符
  insertLineBreakAndMoveCursor() {
    const selection = window.getSelection();
    if (!selection.rangeCount) return;

    const range = selection.getRangeAt(0);
    range.deleteContents();

    // 创建一个换行元素
    const br = document.createElement('br');

    // 插入换行符
    range.insertNode(br);

    // 移动光标到换行符之后
    range.setStartAfter(br);
    range.setEndAfter(br);
    selection.removeAllRanges();
    selection.addRange(range);

    this.ensureCursorVisible(br);
  }

  // 光标切换至可视区域
  ensureCursorVisible(node) {
    // 使用 scrollIntoView 方法确保节点可见
    if (node && typeof node.scrollIntoView === 'function') {
      node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // 点击placeholder
  focusDiv() {
    // 使用 this.$refs 访问可编辑的 div
    const editableDiv = this.$refs.editableDiv;
    editableDiv.focus();

    // 确保光标在内容的末尾
    const range = document.createRange();
    range.selectNodeContents(editableDiv);
    range.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  // 展开文本域操作
  expandTextarea(event) {
    this.showPlaceholder = false;
    event.target.style.maxHeight = '96px';
    event.target.style.overflowY = 'auto';
    event.target.style.whiteSpace = 'normal';
    this.focusDiv();
  }

  // 收起文本域操作
  shrinkTextarea(event) {
    if (this.categoriesHasTwoRows) return;
    const content = event.target.innerText.trim();
    this.showPlaceholder = content === '' || content === this.placeholderText;
    if (content === '') {
      event.target.innerText = content;
    }
    event.target.style.maxHeight = '32px';
    event.target.style.overflow = 'hidden';
    event.target.style.whiteSpace = 'nowrap';
  }

  @Emit('keyDown')
  handleKeyDown(event: KeyboardEvent) {
    return event;
  }

  render() {
    return (
      <div class={`${this.categoriesHasTwoRows ? 'max-height' : ''} ai-whale-input`}>
        <div class='editable-div-wrapper'>
          <div
            ref='editableDiv'
            class={{
              'editable-div': true,
              animated: !this.categoriesHasTwoRows,
              'placeholder-visible': this.showPlaceholder,
            }}
            contenteditable={true}
            tabindex={0}
            onBlur={this.shrinkTextarea}
            onFocus={this.expandTextarea}
            onKeydown={this.handleKeyDown}
          >
            {this.showPlaceholder && <span class='placeholder'>{this.placeholderText}</span>}
          </div>
          <img
            class='icon'
            alt='icon'
            src={aiWhaleSrc}
          />
        </div>
      </div>
    );
  }
}
