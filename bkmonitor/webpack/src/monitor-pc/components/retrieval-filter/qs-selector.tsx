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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';

import QsSelectorSelector from './qs-selector-options';
import {
  queryStringColorMap,
  EQueryStringTokenType,
  type IFilterField,
  type IStrItem,
  onClickOutside,
  parseQueryString,
  QUERY_STRING_DATA_TYPES,
} from './utils';

import './qs-selector.scss';

const defaultColor = '#313238';

interface IProps {
  value?: string;
  fields: IFilterField[];
  qsSelectorOptionsWidth?: number;
}

@Component
export default class QsSelector extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({ type: String, default: '' }) value: string;
  @Prop({ type: Number, default: 0 }) qsSelectorOptionsWidth: number;

  @Ref('select') selectRef: HTMLDivElement;

  localValue = '';
  strList: IStrItem[] = [];

  /* 弹层实例 */
  popoverInstance = null;
  showSelector = false;

  curTokenType: EQueryStringTokenType = EQueryStringTokenType.key;

  onClickOutsideFn = () => {};

  beforeDestroy() {
    this.onClickOutsideFn?.();
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    this.localValue =
      'asdsf : (asdfas AND "asdf" ) AND XX >= (XXX AND ASDFF ) OR asd < [asdf and asdf] OR ASDF :* FASD';
    this.setParseQueryString();
    // if (this.localValue !== this.value) {
    //   this.localValue = this.value;
    //   this.setParseQueryString();
    // }
  }

  async handleShowSelect(event: MouseEvent) {
    if (this.popoverInstance) {
      this.destroyPopoverInstance();
      return;
    }
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectRef,
      trigger: 'click',
      hideOnClick: false,
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      boundary: 'window',
      distance: 20,
      zIndex: 998,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
    this.showSelector = true;
    this.onClickOutsideFn = onClickOutside(
      [this.$el, document.querySelector('.retrieval-filter__qs-selector-component__popover')],
      () => {
        this.destroyPopoverInstance();
      },
      { once: true }
    );
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.showSelector = false;
  }

  handleInput(e) {
    console.log(e);
  }

  handleCursorPosition() {
    const selection = window.getSelection();
    if (selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    const startNode = range.startContainer;
    // 方法1：通过最近的父<span>确定位置
    const targetSpan = startNode.parentElement.closest('span');
    if (targetSpan) {
      const info = targetSpan.id.split('__');
      const target = {
        key: info[0],
        type: info[1],
        value: targetSpan.textContent,
      };
      if (QUERY_STRING_DATA_TYPES.includes(target.type)) {
        this.curTokenType = target.type as EQueryStringTokenType;
      }
      return;
    }
    // 若光标在<span>之间（如末尾空白区域），返回null或插入新节点
    console.log('光标位于子元素间隙');
  }

  handleClick(e: MouseEvent) {
    this.handleCursorPosition();
    e.stopPropagation();
    if (this.popoverInstance) {
      this.popoverInstance?.show();
      return;
    }
    const customEvent = {
      ...e,
      target: e.currentTarget,
    };
    this.handleShowSelect(customEvent);
  }

  handleSelectOption(str: string) {
    if (this.localValue) {
      //
    } else {
      this.localValue = str;
    }
    this.setParseQueryString();
    const type = this.getLastTokenType();
    if (type === EQueryStringTokenType.key) {
      this.localValue = `${this.localValue} `;
      this.curTokenType = EQueryStringTokenType.method;
      this.setParseQueryString();
    }
  }

  setParseQueryString() {
    const tokens = parseQueryString(this.localValue);
    this.strList = tokens.map(item => ({
      ...item,
      key: random(8),
    }));
  }

  getLastTokenType() {
    let type = '';
    const len = this.strList.length;
    for (let i = len - 1; i >= 0; i--) {
      const target = this.strList[i];
      if (QUERY_STRING_DATA_TYPES.includes(target.type)) {
        type = target.type;
        break;
      }
    }
    return type;
  }

  render() {
    return (
      <div
        class='retrieval-filter__qs-selector-component'
        contenteditable={true}
        onClick={this.handleClick}
        onInput={this.handleCursorPosition}
      >
        {this.strList.map(item => (
          <span
            id={`${item.key}__${item.type}`}
            key={item.key}
            style={{
              color: queryStringColorMap[item.type]?.color || defaultColor,
            }}
            class='str-item'
          >
            {item.value}
          </span>
        ))}
        <div style='display: none;'>
          <div
            ref='select'
            style={{
              ...(this.qsSelectorOptionsWidth ? { width: `${this.qsSelectorOptionsWidth}px` } : {}),
            }}
            class='retrieval-filter__qs-selector-component__popover'
          >
            <QsSelectorSelector
              fields={this.fields}
              show={this.showSelector}
              type={this.curTokenType}
              onSelect={this.handleSelectOption}
            />
          </div>
        </div>
      </div>
    );
  }
}
