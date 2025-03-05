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

import QsSelectorHelp from './qs-selector-help';
import TextHighlighter from './text-highlighter';
import { EQueryStringTokenType, queryStringColorMap, type IFilterField } from './utils';

import './qs-selector-options.scss';

interface IOptions {
  id: string;
  name: string;
}

interface IProps {
  fields: IFilterField[];
  search?: string;
  type?: EQueryStringTokenType;
  show?: boolean;
  onSelect?: (v: string) => void;
}

@Component
export default class QsSelectorSelector extends tsc<IProps> {
  @Prop({ type: String, default: '' }) search: string;
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({ type: String, default: '' }) type: EQueryStringTokenType;
  @Prop({ type: Boolean, default: false }) show: boolean;

  localOptions: IOptions[] = [];
  favoriteOptions = [
    {
      title: '个人收藏 / 审计数据',
      content: '* AND (xxxx =[xxxxxxxx] AND hostID = [2342345] AND bbaq = [cw3rsdfaasd])',
      keyword: 'xxxx =[xxxxxxxx]',
    },
    {
      title: '个人收藏 / 审计数据',
      content: '* AND (xxxx =[xxxxxxxx] AND hostID = [2342345] AND bbaq = [cw3rsdfaasd])',
      keyword: 'xxxx =[xxxxxxxx]',
    },
    {
      title: '个人收藏 / 审计数据',
      content: '* AND (xxxx =[xxxxxxxx] AND hostID = [2342345] AND bbaq = [cw3rsdfaasd])',
      keyword: 'xxxx =[xxxxxxxx]',
    },
    {
      title: '个人收藏 / 审计数据',
      content: '* AND (xxxx =[xxxxxxxx] AND hostID = [2342345] AND bbaq = [cw3rsdfaasd])',
      keyword: 'xxxx =[xxxxxxxx]',
    },
  ];

  cursorIndex = 0;

  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeydownEvent);
  }

  @Watch('type', { immediate: true })
  handleWatchFieldType() {
    this.handleGetOptions();
  }
  @Watch('search', { immediate: true })
  handleWatchSearch() {
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
  @Debounce(200)
  handleGetOptions() {
    this.cursorIndex = 0;
    if (this.type === EQueryStringTokenType.key) {
      this.localOptions = this.fields.map(item => ({
        id: item.name,
        name: item.name,
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

  render() {
    return (
      <div class='retrieval-filter__qs-selector-options-component'>
        <div class='wrap-left'>
          <div class='options-wrap'>
            {this.localOptions.map((item, index) => (
              <div
                key={item.id}
                class={['option-item', { 'cursor-active': index === this.cursorIndex }]}
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
                <span class='favorite-count'>2</span>
              </i18n>
            </div>
            {this.favoriteOptions.map((item, index) => (
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
            ))}
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
