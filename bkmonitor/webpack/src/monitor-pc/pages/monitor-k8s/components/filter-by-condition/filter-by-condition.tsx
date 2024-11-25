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

import { Debounce, random } from 'monitor-common/utils';

import KvTag from './kv-tag';
import { EGroupBy, GROUP_OPTIONS } from './utils';

import './filter-by-condition.scss';

interface IValue {
  id: string;
  name: string;
}

interface ITagListItem {
  key: string;
  id: string;
  name: string;
  values: IValue[];
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
  // 头部group选项
  groupOptions: IGroupOptionsItem[] = [];
  // 当前选择的group
  groupSelected: EGroupBy | string = '';
  // 当前选择的group下的value选项
  valueOptions: IValueItem[] = [];
  // 当前选择的value下的value选项 (二级分类)
  valueCategoryOptions: IValueItem[] = [];
  valueCategorySelected = '';
  // 搜索框输入的值
  searchValue = '';
  searchValueOptions = [];
  searchValueCategoryOptions = [];
  // 当前点击的tag
  updateActive = '';
  // 溢出的数量
  overflowCount = 0;
  // 当前溢出的下标
  overflowIndex = 0;
  // 展开tagList
  isExpand = false;

  created() {
    this.tagList = [];
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
        this.setTagList();
        this.updateActive = '';
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

  handleSelectGroup(id: string) {
    if (this.groupSelected !== id) {
      this.groupSelected = id;
      const checkedSet = new Set();
      for (const tag of this.tagList) {
        if (tag.id === id) {
          for (const v of tag.values) {
            checkedSet.add(v.id);
          }
          break;
        }
      }
      if (this.groupSelected === EGroupBy.workload) {
        const groupValues = GROUP_OPTIONS.find(item => item.id === this.groupSelected)?.list || [];
        this.valueCategoryOptions = groupValues.map(item => ({
          ...item,
          checked: false,
          list:
            item?.list?.map(l => ({
              ...l,
              checked: checkedSet.has(l.id),
            })) || [],
        }));
        if (this.valueCategorySelected) {
          this.valueOptions =
            this.valueCategoryOptions.find(item => item.id === this.valueCategorySelected)?.list || [];
        } else {
          this.valueCategorySelected = this.valueCategoryOptions[0]?.id || '';
          this.valueOptions = this.valueCategoryOptions?.[0]?.list || [];
        }
      } else {
        this.valueCategoryOptions = [];
        const groupValues = GROUP_OPTIONS.find(item => item.id === this.groupSelected)?.list || [];
        this.valueOptions = groupValues.map(item => ({ ...item, checked: checkedSet.has(item.id) }));
      }
    }
  }

  @Debounce(300)
  handleSearchChange(value: string) {
    this.searchValue = value;
  }

  handleCheck(item: IValueItem) {
    item.checked = !item.checked;
    if (this.groupSelected === EGroupBy.workload) {
      for (const option of this.valueCategoryOptions) {
        for (const l of option.list) {
          if (l.id === item.id) {
            l.checked = item.checked;
          }
        }
      }
    }
  }

  setTagList() {
    const curSelected = [];
    if (this.groupSelected === EGroupBy.workload) {
      for (const option of this.valueCategoryOptions) {
        for (const l of option.list) {
          if (l.checked) {
            curSelected.push(l);
          }
        }
      }
    } else {
      for (const value of this.valueOptions) {
        if (value.checked) {
          curSelected.push(value);
        }
      }
    }
    let has = false;
    if (!curSelected.length) {
      const delIndex = this.tagList.findIndex(item => item.id === this.groupSelected);
      if (delIndex > -1) {
        this.tagList.splice(delIndex, 1);
      }
    } else {
      for (const tag of this.tagList) {
        if (tag.id === this.groupSelected) {
          tag.values = curSelected.map(item => ({
            id: item.id,
            name: item.name,
          }));
          has = true;
          break;
        }
      }
      if (!has) {
        const groupItem = this.groupOptions.find(item => item.id === this.groupSelected);
        const obj = {
          key: random(8),
          id: groupItem.id,
          name: groupItem.name,
          values: curSelected.map(item => ({
            id: item.id,
            name: item.name,
          })),
        };
        this.tagList.push(obj);
      }
    }
    this.overflowCountRender();
  }

  handleAddTag(event: MouseEvent) {
    this.setGroupOptions();
    this.handleAdd(event);
  }

  handleUpdateTag(target: any, item: ITagListItem) {
    this.updateActive = item.key;
    this.setGroupOptions();
    this.handleAdd({ target } as any);
  }

  // 切换workload 分类
  handleSelectCategory(item: IValueItem) {
    this.valueCategorySelected = item.id;
    const values = this.valueCategoryOptions.find(item => item.id === this.valueCategorySelected)?.list || [];
    this.valueOptions = values;
  }

  // 计算溢出个数
  async overflowCountRender() {
    setTimeout(() => {
      const wrapWidth = this.$el.clientWidth - 32;
      const visibleWrap = this.$el.querySelector('.tag-list-wrap-visible');
      let index = 0;
      let w = 0;
      let count = 0;
      for (const item of Array.from(visibleWrap.children)) {
        w += item.clientWidth;
        if (w > wrapWidth) {
          break;
        }
        index += 1;
        if (index % 2) {
          count += 1;
        }
      }
      this.overflowIndex = index;
      this.overflowCount = this.tagList.length - count;
      if (!this.overflowCount) {
        this.isExpand = false;
      }
    }, 100);
  }

  handleExpand() {
    this.isExpand = !this.isExpand;
  }

  setGroupOptions() {
    const groupsSet = new Set();
    let updateActiveId = '';
    for (const tag of this.tagList) {
      groupsSet.add(tag.id);
      if (tag.key === this.updateActive) {
        updateActiveId = tag.id;
      }
    }
    const groupOptions = [];
    for (const item of GROUP_OPTIONS) {
      if (!groupsSet.has(item.id) || updateActiveId === item.id) {
        groupOptions.push({
          ...item,
          list: [],
        });
      }
    }
    this.groupOptions = groupOptions;
    this.handleSelectGroup(updateActiveId || groupOptions?.[0]?.id);
  }

  handleDeleteTag(item: ITagListItem) {
    this.tagList = this.tagList.filter(tag => tag.key !== item.key);
    this.overflowCountRender();
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

  tagsWrap(isVisible = false) {
    if (isVisible) {
      return this.tagList.map((item, index) => {
        return [
          index >= 1 && (
            <span
              key={`and_${item.key}`}
              class='filter-by-condition-tag type-condition'
            >
              AND
            </span>
          ),
          <KvTag
            key={item.key}
            active={this.updateActive === item.key}
            value={item}
          />,
        ];
      });
    }
    const list = [];
    let i = 0;
    for (const tag of this.tagList) {
      if (i > 0) {
        list.push({
          name: 'AND',
          id: '__and__',
          key: random(8),
          values: [],
        });
      }
      list.push(tag);
      i += 1;
    }
    return [
      list.map((item, index) => {
        if (!this.isExpand && index >= this.overflowIndex && this.overflowCount > 0) {
          return undefined;
        }
        if (item.id === '__and__') {
          return (
            <span
              key={`and_${item.key}`}
              class='filter-by-condition-tag type-condition'
            >
              AND
            </span>
          );
        }
        return (
          <KvTag
            key={item.key}
            active={this.updateActive === item.key}
            value={item}
            onClickTag={target => this.handleUpdateTag(target, item)}
            onDeleteTag={() => this.handleDeleteTag(item)}
          />
        );
      }),
      this.overflowCount && !this.isExpand ? (
        <span
          key={'__count__'}
          class='filter-by-condition-tag type-count'
          onClick={() => this.handleExpand()}
        >
          <span class='count-text'>{this.overflowCount}</span>
          <span class='icon-monitor icon-arrow-down' />
        </span>
      ) : this.groupOptions.length ? (
        <span
          key='__add__'
          class='filter-by-condition-tag type-add'
          onClick={this.handleAddTag}
        >
          <span class='icon-monitor icon-plus-line' />
        </span>
      ) : undefined,
      this.isExpand && (
        <span
          key={'__count__'}
          class='filter-by-condition-tag type-expand'
          onClick={() => this.handleExpand()}
        >
          <span class='count-text'>{this.$t('收起')}</span>
          <span class='icon-monitor icon-arrow-up' />
        </span>
      ),
    ];
  }

  render() {
    return (
      <div class={['filter-by-condition-component', { 'expand-tags': this.isExpand }]}>
        <div class='tag-list-wrap'>{this.tagsWrap()}</div>
        <div class='tag-list-wrap-visible'>{this.tagsWrap(true)}</div>
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
                  onClick={() => this.handleSelectGroup(option.id)}
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
                        class={['cate-item', { active: this.valueCategorySelected === item.id }]}
                        onClick={() => this.handleSelectCategory(item)}
                      >
                        <span class='cate-item-name'>{item.name}</span>
                        <span class='cate-item-count'>({item.count})</span>
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
