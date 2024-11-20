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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';

import TextListOverview from './text-list-overview';
import { EGroupBy, GROUP_OPTIONS } from './utils';

import './filter-by-condition.scss';

enum ETagType {
  add = 'add',
  condition = 'condition',
  kv = 'kv',
}

interface IValueItem {
  id: string;
  name: string;
}

interface ITagListItem {
  key: string;
  id: string;
  name: string;
  values: IValueItem[];
  type: ETagType;
}

interface IGroupOptionsItem {
  id: string;
  name: string;
  count: number;
}
interface IValueItem {
  id: string;
  name: string;
  checked: boolean;
  count?: number;
  list?: {
    id: string;
    name: string;
    checked: boolean;
  }[];
}

@Component
export default class FilterByCondition extends tsc<object> {
  @Ref('selector') selectorRef: HTMLDivElement;
  // tags
  tagList: ITagListItem[] = [];
  popoverInstance = null;

  groupOptions: IGroupOptionsItem[] = [];
  groupSelected: EGroupBy | string = '';
  valueOptions: IValueItem[] = [];
  valueCategoryOptions: IValueItem[] = [];
  searchValue = '';

  created() {
    this.tagList = [
      {
        type: ETagType.add,
        key: random(8),
        id: '',
        name: '',
        values: [],
      },
    ];
    this.groupSelected = GROUP_OPTIONS[0].id;
    this.valueOptions = GROUP_OPTIONS[0].list.map(item => ({ ...item, checked: false }));
    this.groupOptions = GROUP_OPTIONS.map(item => ({
      ...item,
      list: [],
    }));
  }

  async handleAdd(event: MouseEvent) {
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectorRef,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      boundary: 'window',
      distance: 20,
      zIndex: 9999,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  handleSelectGroup(option: IGroupOptionsItem) {
    if (this.groupSelected !== option.id) {
      this.groupSelected = option.id;
      if (this.groupSelected === EGroupBy.workload) {
        const groupValues = GROUP_OPTIONS.find(item => item.id === this.groupSelected)?.list || [];
        this.valueCategoryOptions = groupValues.map(item => ({ ...item, checked: false }));
        this.valueOptions = this.valueCategoryOptions?.[0]?.list?.map(item => ({ ...item, checked: false })) || [];
      } else {
        this.valueCategoryOptions = [];
        const groupValues = GROUP_OPTIONS.find(item => item.id === this.groupSelected)?.list || [];
        this.valueOptions = groupValues.map(item => ({ ...item, checked: false }));
      }
    }
  }

  handleSearchChange(value: string) {
    this.searchValue = value;
  }

  handleCheck(item: IValueItem) {
    item.checked = !item.checked;
  }

  valuesWrap() {
    return (
      <div class='value-items'>
        {this.valueOptions.map(item => (
          <div
            key={item.id}
            class={['value-item', { checked: item.checked }]}
            onClick={() => this.handleCheck(item)}
          >
            <span class='value-item-name'>{item.name}</span>
            <span class='value-item-checked'>{item.checked && <span class='icon-monitor icon-mc-check-small' />}</span>
          </div>
        ))}
      </div>
    );
  }

  render() {
    return (
      <div class='filter-by-condition-component'>
        {this.tagList.map(item => {
          if (item.type === ETagType.condition) {
            return (
              <span
                key={item.key}
                class='filter-by-condition-tag'
              >
                AND
              </span>
            );
          }
          if (item.type === ETagType.add) {
            return (
              <span
                key={item.key}
                class='filter-by-condition-tag type-add'
                onClick={this.handleAdd}
              >
                <span class='icon-monitor icon-plus-line' />
              </span>
            );
          }
          return (
            <span
              key={item.key}
              class='filter-by-condition-tag'
            >
              <span>{item.name}</span>
              <span>=</span>
              <span>
                <TextListOverview textList={item.values} />
              </span>
            </span>
          );
        })}
        <div
          style={{
            display: 'none',
          }}
        >
          <div
            ref='selector'
            class='filter-by-condition-component-popover'
          >
            <div class='filter-by-condition-component-popover-header'>
              {this.groupOptions.map(option => (
                <div
                  key={option.id}
                  class={['group-item', { active: this.groupSelected === option.id }]}
                  onClick={() => this.handleSelectGroup(option)}
                >
                  <span class='group-item-name'>{option.name}</span>
                  <span class='group-item-count'>{option.count}</span>
                </div>
              ))}
            </div>
            <div class='filter-by-condition-component-popover-content'>
              <div class='values-search'>
                <bk-input
                  behavior='simplicity'
                  left-icon='bk-icon icon-search'
                  placeholder={this.$t('请输入关键字')}
                  value={this.searchValue}
                  onChange={this.handleSearchChange}
                />
              </div>
              {this.valueCategoryOptions.length ? (
                <div class='value-items-wrap'>
                  <div class='left-wrap'>
                    {this.valueCategoryOptions.map(item => (
                      <div
                        key={item.id}
                        class='cate-item'
                      >
                        <span class='cate-item-name'>
                          <span class='name'>{item.name}</span>
                          <span class='count'>{item.count}</span>
                        </span>
                        <span class='cate-item-right'>
                          <span class='icon-monitor icon-arrow-right' />
                        </span>
                      </div>
                    ))}
                  </div>
                  {this.valuesWrap()}
                </div>
              ) : (
                this.valuesWrap()
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }
}
