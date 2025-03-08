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

import EmptyStatus from '../empty-status/empty-status';
import QsSelectorHelp from './qs-selector-help';
import { getQueryStringMethods, QUERY_STRING_CONDITIONS, queryStringColorMap } from './query-string-utils';
import TextHighlighter from './text-highlighter';
import { EQueryStringTokenType, type IGetValueFnParams, type IWhereValueOptionsItem, type IFilterField } from './utils';

import './qs-selector-options.scss';

interface IOptions {
  id: string;
  name: string;
  desc?: string;
}

interface IProps {
  fields: IFilterField[];
  field?: string;
  search?: string;
  type?: EQueryStringTokenType;
  show?: boolean;
  onSelect?: (v: string) => void;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
}

@Component
export default class QsSelectorSelector extends tsc<IProps> {
  /* 当前输入的值 */
  @Prop({ type: String, default: '' }) search: string;
  /* 所有字段 */
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  /* 当前选项类型 */
  @Prop({ type: String, default: '' }) type: EQueryStringTokenType;
  /* 是否展示 */
  @Prop({ type: Boolean, default: false }) show: boolean;
  /* 获取value选项时的当前的key */
  @Prop({ type: String, default: '' }) field: string;
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;

  loading = false;

  localOptions: IOptions[] = [];
  favoriteOptions: { title: string; content: string; keyword: string }[] = [];

  cursorIndex = 0;

  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeydownEvent);
  }

  @Watch('type', { immediate: true })
  handleWatchFieldType() {
    console.log(this.type, 'type------------');
    this.handleGetOptions();
  }
  @Watch('search', { immediate: true })
  handleWatchSearch() {
    console.log(this.search, 'search--------------');
    this.handleGetOptions();
  }
  @Watch('show', { immediate: true })
  handleWatchShow() {
    if (this.show) {
      this.handleGetOptions();
      document.addEventListener('keydown', this.handleKeydownEvent);
    } else {
      document.removeEventListener('keydown', this.handleKeydownEvent);
    }
  }
  @Debounce(300)
  async handleGetOptions() {
    this.cursorIndex = 0;
    let fieldItem: IFilterField = null;
    for (const item of this.fields) {
      if (item.name === this.field) {
        fieldItem = item;
        break;
      }
    }
    console.log(this.field, this.type, fieldItem);
    if (this.type === EQueryStringTokenType.key) {
      this.localOptions = this.fields
        .filter(item => {
          if (!this.search) {
            return true;
          }
          if (item.alias.toLocaleLowerCase().includes(this.search.toLocaleLowerCase())) {
            return true;
          }
          if (item.name.toLocaleLowerCase().includes(this.search.toLocaleLowerCase())) {
            return true;
          }
          return false;
        })
        .map(item => ({
          id: item.name,
          name: item.name,
        }));
    } else if (this.type === EQueryStringTokenType.method) {
      this.localOptions = getQueryStringMethods(fieldItem?.type).map(item => ({
        id: item.id,
        name: item.id,
        desc: item.name,
      }));
    } else if (this.type === EQueryStringTokenType.value) {
      if (fieldItem?.is_option_enabled) {
        if (!this.loading) {
          const data = await this.getValueData();
          this.localOptions = data;
        }
      } else {
        this.localOptions = [];
      }
    } else if (this.type === EQueryStringTokenType.condition) {
      this.localOptions = QUERY_STRING_CONDITIONS.map(item => ({
        id: item.id,
        name: item.id,
        desc: item.name,
      }));
    }
  }

  handleKeydownEvent(event: KeyboardEvent) {
    switch (event.key) {
      case 'ArrowUp': {
        // 按下上箭头键
        event.preventDefault();
        this.cursorIndex -= 1;
        if (this.cursorIndex < 0) {
          this.cursorIndex = this.localOptions.length - 1;
        }
        this.updateSelection();
        break;
      }

      case 'ArrowDown': {
        event.preventDefault();
        this.cursorIndex += 1;
        if (this.cursorIndex > this.localOptions.length) {
          this.cursorIndex = 0;
        }
        this.updateSelection();
        break;
      }
      case 'Enter': {
        event.preventDefault();
        this.enterSelection();
        break;
      }
    }
  }

  enterSelection() {
    const item = this.localOptions[this.cursorIndex];
    if (item) {
      this.$emit('select', item.id);
    }
  }

  handleSelect(str: string) {
    this.$emit('select', str);
  }

  /**
   * @description 聚焦选中项
   */
  updateSelection() {
    this.$nextTick(() => {
      const listEl = this.$el.querySelector('.wrap-left .options-wrap');
      const el = listEl?.children?.[this.cursorIndex];
      if (el) {
        el.scrollIntoView(false);
      }
    });
  }

  /**
   * @description 搜索接口
   * @param item
   * @param method
   * @param value
   */
  async getValueData() {
    let list = [];
    this.loading = true;
    if (this.field) {
      const data = await this.getValueFn({
        queryString: `${this.field} : *`,
        fields: [this.field],
        limit: 5,
      });
      list = data.list;
    }
    this.loading = false;
    return list;
  }

  render() {
    return (
      <div class='retrieval-filter__qs-selector-options-component'>
        <div class='wrap-left'>
          <div class='options-wrap'>
            {this.loading
              ? new Array(3).fill(null).map((_item, index) => (
                  <div
                    key={index}
                    class='option-item skeleton-item'
                  >
                    <div class='skeleton-element h-16' />
                  </div>
                ))
              : this.localOptions.map((item, index) => (
                  <div
                    key={item.id}
                    class={['option-item main-item', { 'cursor-active': index === this.cursorIndex }]}
                    onClick={() => this.handleSelect(item.id)}
                  >
                    <span
                      style={{
                        backgroundColor: queryStringColorMap[this.type]?.background || '#E6F2F1',
                        color: queryStringColorMap[this.type]?.color || '#02776E',
                      }}
                      class='option-item-icon'
                    >
                      <span class={['icon-monitor', queryStringColorMap[this.type]?.icon || '']} />
                    </span>
                    <span class='option-item-name'>{item.name}</span>
                  </div>
                ))}
          </div>
          <div class='favorite-wrap'>
            <div class='favorite-wrap-title'>
              <i18n path={'联想到以下 {0} 个收藏：'}>
                <span class='favorite-count'>{this.favoriteOptions.length}</span>
              </i18n>
            </div>
            {this.favoriteOptions.length ? (
              this.favoriteOptions.map((item, index) => (
                <div
                  key={index}
                  class='favorite-item'
                >
                  <span class='favorite-item-name'>{item.title}</span>
                  <span class='favorite-item-content'>
                    <TextHighlighter
                      content={item.content}
                      keyword={item.keyword}
                    />
                  </span>
                </div>
              ))
            ) : (
              <EmptyStatus
                textMap={{
                  empty: this.$tc('暂未匹配到符合条件的收藏项'),
                }}
                type={'empty'}
              />
            )}
          </div>
          <div class='key-help'>
            <span class='desc-item'>
              <span class='desc-item-icon mr-2'>
                <span class='icon-monitor icon-mc-arrow-down up' />
              </span>
              <span class='desc-item-icon'>
                <span class='icon-monitor icon-mc-arrow-down' />
              </span>
              <span class='desc-item-name'>{this.$t('移动光标')}</span>
            </span>
            <span class='desc-item'>
              <span class='desc-item-box'>Enter</span>
              <span class='desc-item-name'>{this.$t('确认结果')}</span>
            </span>
          </div>
        </div>
        <div class='wrap-right'>
          <QsSelectorHelp />
        </div>
      </div>
    );
  }
}
