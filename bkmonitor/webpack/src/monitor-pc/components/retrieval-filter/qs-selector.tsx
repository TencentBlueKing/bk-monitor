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

import QsSelectorSelector from './qs-selector-options';
import { QueryStringEditor } from './query-string-utils';
import {
  EQueryStringTokenType,
  type IFilterField,
  onClickOutside,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
} from './utils';

import './qs-selector.scss';

interface IProps {
  value?: string;
  fields: IFilterField[];
  qsSelectorOptionsWidth?: number;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onChange?: (v: string) => void;
  onQueryStringChange?: (v: string) => void;
}

@Component
export default class QsSelector extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({ type: String, default: '' }) value: string;
  @Prop({ type: Number, default: 0 }) qsSelectorOptionsWidth: number;
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;

  @Ref('select') selectRef: HTMLDivElement;

  localValue = '';
  /* 弹层实例 */
  popoverInstance = null;
  /* 是否弹出选项框 */
  showSelector = false;
  /* 当前需要弹出的选项类型 */
  curTokenType: EQueryStringTokenType = EQueryStringTokenType.key;
  /* 当前输入的文字 */
  search = '';
  /* 主动刷新token列表 */
  tokenRefreshKey = '';
  /* 当前片段的key */
  curTokenField = '';

  queryStringEditor: QueryStringEditor = null;

  onClickOutsideFn = () => {};

  beforeDestroy() {
    this.onClickOutsideFn?.();
    this.destroyPopoverInstance();
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.localValue !== this.value) {
      this.localValue = this.value;
      this.handleInit();
    }
  }

  mounted() {
    this.handleInit();
  }

  handleInit() {
    this.$nextTick(() => {
      if (this.queryStringEditor) {
        this.queryStringEditor.setQueryString(this.localValue);
      } else {
        const el = this.$el.querySelector('.retrieval-filter__qs-selector-component');
        this.queryStringEditor = new QueryStringEditor({
          target: el,
          value: this.localValue,
          popUpFn: this.handlePopUp,
          onSearch: this.handleSearch,
          popDownFn: this.destroyPopoverInstance,
          onChange: this.handleChange,
          onQuery: this.handleQuery,
        });
      }
    });
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
      distance: 15,
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
    this.onClickOutsideFn?.();
  }

  /**
   * @description 弹出选项框
   * @param type
   * @param field
   * @returns
   */
  handlePopUp(type, field) {
    console.log('PopUp', type, field);
    this.curTokenType = type;
    this.curTokenField = field;
    const customEvent = {
      target: this.$el,
    };
    if (this.popoverInstance) {
      this.popoverInstance?.show();
      return;
    }
    this.handleShowSelect(customEvent as any);
  }

  /**
   * @description 下拉选项选择
   * @param str
   */
  handleSelectOption(str: string) {
    this.queryStringEditor.setToken(str, this.curTokenType);
  }

  handleSearch(value) {
    this.search = value;
  }

  handleChange(str: string) {
    this.localValue = str;
    this.$emit('queryStringChange', str);
  }

  handleQuery() {
    this.$emit('change', this.localValue);
  }

  render() {
    return (
      <div>
        <div
          class='retrieval-filter__qs-selector-component'
          contenteditable={true}
        />
        <div style='display: none;'>
          <div
            ref='select'
            style={{
              ...(this.qsSelectorOptionsWidth ? { width: `${this.qsSelectorOptionsWidth}px` } : {}),
            }}
            class='retrieval-filter__qs-selector-component__popover'
          >
            <QsSelectorSelector
              field={this.curTokenField}
              fields={this.fields}
              getValueFn={this.getValueFn}
              search={this.search}
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
