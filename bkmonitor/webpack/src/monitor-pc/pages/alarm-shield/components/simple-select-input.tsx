/* eslint-disable no-nested-ternary */
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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from '../../../../monitor-common/utils/utils';

import './simple-select-input.scss';

interface IProps {
  value?: string;
  list?: {
    id: string;
    name: string;
  }[];
  placeholder?: string;
  nodataMsg?: string;
}

interface IEvents {
  onChange?: string;
}

@Component
export default class SimpleSelectInput extends tsc<IProps, IEvents> {
  @Prop({ default: '', type: String }) value: string;
  @Prop({ default: () => [], type: Array }) list: { id: string; name: string }[];
  @Prop({ default: window.i18n.t('输入'), type: String }) placeholder: string;
  @Prop({ default: window.i18n.t('无数据'), type: String }) nodataMsg: string;
  @Ref('list') listRef: HTMLDivElement;
  @Ref('inputWrap') inputWrapRef: HTMLDivElement;
  @Ref('input') inputRef: any;

  popoverInstance = null;
  isShowPop = false;

  /* 输入完毕，关闭弹出层时 下次弹出全部选项 */
  isSelected = true;

  get searchList() {
    if (this.value) {
      const isCheck = this.list.some(item => item.name === this.value || item.id === this.value) && this.isSelected;
      return this.list.filter(
        item => item.name.indexOf(this.value) > -1 || item.id.indexOf(this.value) > -1 || isCheck
      );
    }
    return this.list;
  }

  handleShowPopover(e: Event) {
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.listRef,
        arrow: false,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor',
        boundary: 'window',
        maxWidth: 520,
        duration: [200, 0],
        distance: 1,
        onHidden: () => {
          this.popoverInstance.destroy();
          this.popoverInstance = null;
          this.isShowPop = false;
          setTimeout(() => {
            this.isSelected = true;
          }, 50);
        }
      });
    }
    this.isShowPop = true;
    this.popoverInstance?.show(100);
  }

  handleBlur() {
    //
  }

  // 提交，click 和 blur 统一调一个方法
  handleCommit(item) {
    this.handleChange(item.name);
    this.isSelected = false;
  }

  @Debounce(300)
  @Emit('change')
  handleChange(value) {
    this.popoverInstance?.show(100);
    return value;
  }

  render() {
    return (
      <span class='simple-select-input-component'>
        <span
          onClick={event => this.handleShowPopover(event)}
          ref='inputWrap'
        >
          <bk-input
            class='input-wrap'
            value={this.value}
            ref='input'
            placeholder={this.placeholder}
            onInput={value => {
              this.handleChange(value);
              this.isSelected = false;
            }}
            onBlur={this.handleBlur}
          />
        </span>
        <div style={{ display: 'none' }}>
          <div
            ref='list'
            class='simple-select-input-component-list-wrap'
          >
            {this.list.length ? (
              <ul class='list-wrap'>
                {this.searchList.map(item => (
                  <li
                    key={item.id}
                    v-bk-tooltips={{
                      content: item.id,
                      placement: 'right',
                      zIndex: 9999,
                      boundary: document.body,
                      appendTo: document.body,
                      allowHTML: false
                    }}
                    onClick={() => this.handleCommit(item)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            ) : this.value === '' ? (
              <div class='no-data-msg'>{this.nodataMsg}</div>
            ) : undefined}
            {this.$slots?.extension}
          </div>
        </div>
      </span>
    );
  }
}
