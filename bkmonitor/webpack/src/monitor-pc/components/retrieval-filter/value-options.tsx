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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';
import loadingImg from 'monitor-pc/static/images/svg/spinner.svg';

import EmptyStatus from '../empty-status/empty-status';
import TextHighlighter from './text-highlighter';
import { ECondition, type IFilterField, type IGetValueFnParams, type IWhereValueOptionsItem } from './utils';

import './value-options.scss';

interface IValue {
  id: string;
  name: string;
}

interface IProps {
  search?: string;
  selected?: string[];
  isWildcard?: boolean;
  checkedItem?: IFilterField;
  method?: string;
  show?: boolean;
  isPopover?: boolean;
  onIsChecked?: (v: boolean) => void;
  onSelect?: (item: IValue) => void;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
}

@Component
export default class ValueOptions extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) selected: string[];
  @Prop({ type: String, default: '' }) search: string;
  @Prop({ type: Object, default: () => null }) checkedItem: IFilterField;
  @Prop({ type: Boolean, default: false }) isWildcard: boolean;
  @Prop({ type: String, default: '' }) method: string;
  /* 是否通过popover组件显示 */
  @Prop({ type: Boolean, default: false }) isPopover: boolean;
  /* 如果荣国popover组件显示则需传入此属性 */
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;

  localOptions: IValue[] = [];
  loading = false;
  /* 可选项悬停位置 */
  hoverActiveIndex = -1;
  scrollLoading = false;
  pageSize = 10;
  page = 1;
  isEnd = false;

  get hasCustomOption() {
    return !!this.search;
  }

  @Watch('show')
  async handleWatchShow() {
    if (this.isPopover) {
      if (this.show) {
        this.dataInit();
        const list = await this.getValueData();
        this.localOptions = this.localOptionsFilter(list);
        document.addEventListener('keydown', this.handleKeydownEvent);
      } else {
        document.removeEventListener('keydown', this.handleKeydownEvent);
      }
    } else {
    }
  }

  @Watch('selected')
  handleWatchSelected() {
    if (this.isPopover ? this.show : true) {
      this.localOptions = this.localOptionsFilter(this.localOptions);
    }
  }

  @Debounce(300)
  @Watch('search')
  async handleWatch() {
    if (this.isPopover ? this.show : true) {
      this.dataInit();
      const list = await this.getValueData();
      this.localOptions = this.localOptionsFilter(list);
    }
  }

  async created() {
    if (!this.isPopover) {
      this.dataInit();
      const list = await this.getValueData();
      this.localOptions = this.localOptionsFilter(list);
      document.addEventListener('keydown', this.handleKeydownEvent);
    }
  }

  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeydownEvent);
  }

  dataInit() {
    this.localOptions = [];
    this.hoverActiveIndex = -1;
    this.page = 1;
    this.isEnd = false;
  }

  handleKeydownEvent(event: KeyboardEvent) {
    const min = this.hasCustomOption ? -1 : 0;
    switch (event.key) {
      case 'ArrowUp': {
        event.preventDefault();
        this.hoverActiveIndex -= 1;
        if (this.hoverActiveIndex < min) {
          this.hoverActiveIndex = min;
        }
        this.updateSelection();
        break;
      }
      case 'ArrowDown': {
        event.preventDefault();
        this.hoverActiveIndex += 1;
        if (this.hoverActiveIndex > this.localOptions.length - 1) {
          this.hoverActiveIndex = this.localOptions.length - 1;
        }
        this.updateSelection();
        break;
      }
      case 'Enter': {
        event.preventDefault();
        this.handleOptionsEnter();
        break;
      }
    }
  }

  /**
   * @description 聚焦光标选项
   */
  updateSelection() {
    this.$emit('isChecked', this.hoverActiveIndex >= 0 && this.hoverActiveIndex <= this.localOptions.length - 1);
    this.$nextTick(() => {
      const listEl = this.$el.querySelector('.options-drop-down-wrap.main__wrap');
      const el = this.hasCustomOption
        ? listEl?.children?.[this.hoverActiveIndex + 1]
        : listEl?.children?.[this.hoverActiveIndex];
      if (el) {
        el.scrollIntoView(false);
      }
    });
  }

  handleOptionsEnter() {
    if (this.hoverActiveIndex !== -1) {
      const item = this.localOptions?.[this.hoverActiveIndex];
      if (item) {
        this.handleCheck(item);
      }
    }
  }

  async handleScroll(event) {
    const container = event.target;
    const scrollTop = container.scrollTop;
    const clientHeight = container.clientHeight;
    const scrollHeight = container.scrollHeight;
    if (scrollTop + clientHeight >= scrollHeight - 3) {
      if (!this.scrollLoading && !this.isEnd) {
        this.scrollLoading = true;
        this.page += 1;
        const data = await this.getValueData(true);
        this.localOptions = this.localOptionsFilter(data);
        this.scrollLoading = false;
      }
    }
  }

  handleCheck(item: IValue) {
    this.$emit('select', item);
  }

  /**
   * @description 搜索接口
   * @param item
   * @param method
   * @param value
   */
  async getValueData(isScroll = false) {
    let list = [];
    if (isScroll) {
      this.scrollLoading = true;
    } else {
      this.loading = true;
    }
    if (this.checkedItem?.is_option_enabled) {
      const limit = this.pageSize * this.page;
      const data = await this.getValueFn({
        where: [
          {
            key: this.checkedItem.name,
            method: 'include',
            value: [this.search || ''],
            condition: ECondition.and,
            options: {
              is_wildcard: true,
            },
          },
        ],
        fields: [this.checkedItem.name],
        limit: this.pageSize * this.page,
      });
      list = data.list;
      this.isEnd = limit >= data.count;
    }
    this.scrollLoading = false;
    this.loading = false;
    return list;
  }

  localOptionsFilter(list: IValue[]) {
    const sets = new Set(this.selected);
    const result = list.filter(item => !sets.has(item.id));
    if (!result.length) {
      this.page += 1;
    }
    return result;
  }

  render() {
    return (
      <div class='retrieval-filter__value-options-select-component'>
        {this.loading ? (
          <div class={['options-drop-down-wrap', { 'is-popover': this.isPopover }]}>
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
        ) : !this.localOptions.length && !this.search ? (
          <div class={['options-drop-down-wrap', { 'is-popover': this.isPopover }]}>
            <EmptyStatus type={'empty'} />
          </div>
        ) : (
          <div
            class={['options-drop-down-wrap main__wrap', { 'is-popover': this.isPopover }]}
            onScroll={this.handleScroll}
          >
            {!!this.search && (
              <div
                key={'00'}
                class={['options-item', { 'active-index': this.hoverActiveIndex === -1 }]}
                onClick={e => {
                  e.stopPropagation();
                  this.handleCheck({ id: this.search, name: this.search });
                }}
              >
                <i18n path='生成 "{0}" Tag'>
                  <span class='highlight'>{this.search}</span>
                </i18n>
              </div>
            )}
            {this.localOptions.map((item, index) => (
              <div
                key={index}
                class={['options-item', { 'active-index': this.hoverActiveIndex === index }]}
                onClick={e => {
                  e.stopPropagation();
                  this.handleCheck(item);
                }}
              >
                <TextHighlighter
                  content={item.name}
                  keyword={this.search}
                />
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
  }
}
