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

import { Debounce } from 'monitor-common/utils';
import loadingImg from 'monitor-pc/static/images/svg/spinner.svg';

import EmptyStatus from '../empty-status/empty-status';
import QsSelectorHelp from './qs-selector-help';
import { getQueryStringMethods, QUERY_STRING_CONDITIONS, queryStringColorMap } from './query-string-utils';
import TextHighlighter from './text-highlighter';
import {
  type IFavoriteListItem,
  type IFilterField,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  EQueryStringTokenType,
} from './utils';

import './qs-selector-options.scss';

const descMap = {
  ':': [
    { type: 'tag', text: window.i18n.tc('等于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  ':*': [
    { type: 'tag', text: window.i18n.tc('存在') },
    { type: 'text', text: window.i18n.tc('任意形式') },
  ],
  '>': [
    { type: 'tag', text: window.i18n.tc('大于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  '<': [
    { type: 'tag', text: window.i18n.tc('小于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  '>=': [
    { type: 'tag', text: window.i18n.tc('大于或等于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  '<=': [
    { type: 'tag', text: window.i18n.tc('小于或等于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  AND: [
    { type: 'text', text: window.i18n.tc('需要') },
    { type: 'tag', text: window.i18n.tc('两个参数都') },
    { type: 'text', text: window.i18n.tc('为真') },
  ],
  OR: [
    { type: 'text', text: window.i18n.tc('需要') },
    { type: 'tag', text: window.i18n.tc('一个或多个参数') },
    { type: 'text', text: window.i18n.tc('为真') },
  ],
  'AND NOT': [
    { type: 'text', text: window.i18n.tc('需要') },
    { type: 'tag', text: window.i18n.tc('一个或多个参数') },
    { type: 'text', text: window.i18n.tc('为真') },
  ],
};

interface IOptions {
  desc?: string;
  id: string;
  name: string;
}

interface IProps {
  favoriteList?: IFavoriteListItem[];
  field?: string;
  fields: IFilterField[];
  queryString?: string;
  search?: string;
  show?: boolean;
  type?: EQueryStringTokenType;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onSelect?: (v: string) => void;
  onSelectFavorite?: (v: string) => void;
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
  @Prop({ type: Array, default: () => [] }) favoriteList: IFavoriteListItem[];
  @Prop({ type: String, default: '' }) queryString: string;

  @Ref('options') optionsRef: HTMLDivElement;

  localOptions: IOptions[] = [];
  favoriteOptions: { content: string; keyword: string; title: string }[] = [];
  cursorIndex = -1;

  loading = false;
  pageSize = 5;
  page = 1;
  isEnd = false;
  scrollLoading = false;

  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeydownEvent);
  }

  @Watch('type', { immediate: true })
  handleWatchFieldType() {
    this.localOptions = [];
    this.handleGetOptionsProxy();
  }
  @Watch('search', { immediate: true })
  handleWatchSearch() {
    this.handleGetOptionsProxy();
  }
  @Watch('show', { immediate: true })
  handleWatchShow() {
    if (this.show) {
      this.localOptions = [];
      this.handleGetOptionsProxy();
      document.addEventListener('keydown', this.handleKeydownEvent);
    } else {
      document.removeEventListener('keydown', this.handleKeydownEvent);
    }
  }

  @Watch('queryString', { immediate: true })
  handleWatchQueryString() {
    this.getSearchFavoriteOptions();
  }

  @Debounce(100)
  getSearchFavoriteOptions() {
    const favoriteOptions = [];
    if (this.queryString && !/^\s*$/.test(this.queryString)) {
      const keyword = this.queryString.replace(/^\s+|\s+$/g, '').toLocaleLowerCase();
      for (const item of this.favoriteList) {
        const favorites = item?.favorites || [];
        for (const favoriteItem of favorites) {
          const content = favoriteItem?.config?.queryConfig?.query_string || '';
          if (content?.toLocaleLowerCase().includes(keyword)) {
            favoriteOptions.push({
              title: `${item.name} / ${favoriteItem.name}`,
              content,
              keyword,
            });
          }
        }
      }
    }
    this.favoriteOptions = favoriteOptions;
  }

  async handleGetOptions() {
    this.pageInit();
    this.cursorIndex = -1;
    let fieldItem: IFilterField = null;
    for (const item of this.fields) {
      if (item.name === this.field) {
        fieldItem = item;
        break;
      }
    }
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
          const data = await this.getValueData(false, !!fieldItem?.is_dimensions);
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

  @Debounce(500)
  async handleGetOptionsDebounce() {
    this.handleGetOptions();
  }

  handleGetOptionsProxy() {
    if (this.type === EQueryStringTokenType.value) {
      this.handleGetOptionsDebounce();
    } else {
      this.handleGetOptions();
    }
  }

  handleKeydownEvent(event: KeyboardEvent) {
    switch (event.key) {
      case 'ArrowUp': {
        // 按下上箭头键
        event.preventDefault();
        this.cursorIndex -= 1;
        if (this.cursorIndex < -1) {
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
    const listEl = this.$el.querySelector('.wrap-left .options-wrap');
    const el = listEl?.children?.[this.cursorIndex] as HTMLDivElement;
    el?.focus();
  }

  /**
   * @description 搜索接口
   * @param item
   * @param method
   * @param value
   */
  async getValueData(isScroll = false, isDimensions = false) {
    let list = [];
    if (isScroll) {
      this.scrollLoading = true;
    } else {
      this.loading = true;
    }

    if (this.field) {
      const limit = this.page * this.pageSize;
      const data = await this.getValueFn({
        queryString: `${isDimensions ? 'dimensions.' : ''}${this.field} : ${this.search || '*'}`,
        fields: [this.field],
        limit: limit,
      });
      this.isEnd = limit >= data.count;
      list = data.list;
    }
    this.loading = false;
    this.scrollLoading = false;
    return list;
  }

  pageInit() {
    this.page = 1;
    this.isEnd = false;
  }

  async handleScroll() {
    const container = this.optionsRef;
    const scrollTop = container.scrollTop;
    const clientHeight = container.clientHeight;
    const scrollHeight = container.scrollHeight;
    if (scrollTop + clientHeight >= scrollHeight - 3) {
      if (!this.scrollLoading && !this.isEnd && this.type === EQueryStringTokenType.value) {
        this.scrollLoading = true;
        this.page += 1;
        const data = await this.getValueData(true);
        this.localOptions = data;
        this.scrollLoading = false;
      }
    }
  }

  handleSelectFavorite(item) {
    this.$emit('selectFavorite', item.content);
  }

  getSubtitle(id: string) {
    if ([EQueryStringTokenType.method, EQueryStringTokenType.condition].includes(this.type)) {
      const items = descMap?.[id] || [];
      return (
        <span class='subtitle-text'>
          {items.map(item => {
            if (item.type === 'text') {
              return item.text;
            }
            if (item.type === 'tag') {
              return <span class='subtitle-text-tag'>{item.text}</span>;
            }
          })}
        </span>
      );
    }
    return undefined;
  }

  render() {
    return (
      <div class='retrieval-filter__qs-selector-options-component'>
        <div class='wrap-left'>
          <div
            ref='options'
            class='options-wrap'
            onScroll={this.handleScroll}
          >
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
                    tabindex={0}
                    onClick={e => {
                      e.stopPropagation();
                      this.handleSelect(item.id);
                    }}
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
                    {this.getSubtitle(item.id)}
                  </div>
                ))}
            {this.scrollLoading && (
              <div class='option-item  scroll-loading'>
                <img
                  alt=''
                  src={loadingImg}
                />
              </div>
            )}
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
                  onClick={e => {
                    e.stopPropagation();
                    this.handleSelectFavorite(item);
                  }}
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
