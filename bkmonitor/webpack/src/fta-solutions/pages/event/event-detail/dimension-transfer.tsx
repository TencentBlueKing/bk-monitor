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

import type { IDimensionItem } from '../typings/event';

import './dimension-transfer.scss';

interface IProps {
  fields: IDimensionItem[];
  value?: string[];
  show?: boolean;
  onConfirm?: (value: IDimensionItem[]) => void;
  onCancel?: () => void;
}

@Component
export default class ResidentSettingTransfer extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IDimensionItem[];
  @Prop({ type: Array, default: () => [] }) value: string[];
  @Prop({ type: Boolean, default: false }) show: boolean;

  localFields: IDimensionItem[] = [];
  searchValue = '';
  searchSelectedValue = '';
  selectedFields: IDimensionItem[] = [];

  // 待选列表数据
  get searchLocalFields() {
    return this.filterFields(this.searchValue, this.localFields);
  }

  // 已选列表数据
  get searchSelectedFields() {
    return this.filterFields(this.searchSelectedValue, this.selectedFields);
  }

  @Watch('show', { immediate: true })
  handleWatchShow() {
    if (this.show) {
      this.searchValue = '';
      this.searchSelectedValue = ''
      const tempSet = new Set(this.value);
      const selectedFields = [];
      const localFields = [];
      const selectedFieldsMap = new Map();
      for (const item of this.fields) {
        if (tempSet.has(item.key)) {
          selectedFields.push(item);
          selectedFieldsMap.set(item.key, item);
        } else {
          localFields.push(item);
        }
      }
      const selected = [];
      for (const v of this.value) {
        const item = selectedFieldsMap.get(v);
        if (item) {
          selected.push(item);
        }
      }
      this.localFields = localFields;
      this.selectedFields = selected;
    }
  }

  @Watch('fields', { immediate: true })
  handleWatchFields() {
    this.handleSetLocalFields();
  }

  filterFields(searchValue, fields) {
    if (!searchValue) return fields;
    const normalizedSearchValue = String(searchValue).toLocaleLowerCase();
    return fields.filter(item => {
      const { display_key: displayKey, key, display_value: displayValue, value } = item;
      const compareValues = [
        `${displayKey}(${displayValue})`.toLocaleLowerCase(),
        `${displayKey}(${value})`.toLocaleLowerCase(),
        `${key}(${displayValue})`.toLocaleLowerCase(),
        `${key}(${value})`.toLocaleLowerCase(),
      ];
      return compareValues.some(val => val.includes(normalizedSearchValue));
    });
  }

  handleCheck(index: number) {
    const item = JSON.parse(JSON.stringify(this.localFields[index]));
    this.localFields.splice(index, 1);
    this.selectedFields.push(item);
  }

  /**
   * @description 点击确定
   */
  handleConfirm() {
    this.$emit('confirm', this.selectedFields);
  }
  handleCancel() {
    this.$emit('cancel');
  }

  handleSetLocalFields() {
    const localFields = [];
    const selectedFields = new Set(this.selectedFields.map(item => item.key));
    for (const item of this.fields) {
      if (!selectedFields.has(item.key)) {
        localFields.push(item);
      }
    }
    this.localFields = localFields;
  }

  handleDelete(targetItem: IDimensionItem) {
    this.selectedFields = this.selectedFields.filter(item => item.key !== targetItem.key);
    this.handleSetLocalFields();
  }

  handleClear() {
    this.selectedFields = [];
    this.localFields = this.fields.slice();
  }

  handleAllAdd() {
    this.localFields = [];
    this.selectedFields = this.fields.slice();
  }

  @Debounce(300)
  handleSearchValueChange(value: string, field: string) {
    this[field === 'local' ? 'searchValue' : 'searchSelectedValue'] = value;
  }

  render() {
    const optionRender = (item: IDimensionItem) => {
      return [
        <span
          key={'02'}
          class='option-name-title'
        >
          {`${item.display_key || item.key}(${item.display_value || item.value})`}
        </span>,
      ];
    };
    return (
      <div class='transfer-component__dimension'>
        <div class='component-top'>
          <div class='component-top-left'>
            <div class='top-header'>
              <span class='header-title'>{`${this.$t('待选列表')}（${this.localFields.length}）`}</span>
              <span
                class='header-btn'
                onClick={this.handleAllAdd}
              >
                {this.$t('全部添加')}
              </span>
            </div>
            <div class='content-wrap'>
              <div class='search-wrap'>
                <bk-input
                  behavior='simplicity'
                  left-icon='bk-icon icon-search'
                  placeholder={this.$t('请输入关键字')}
                  value={this.searchValue}
                  onChange={v => this.handleSearchValueChange(v, 'local')}
                />
              </div>
              <div class='options-wrap'>
                {this.searchLocalFields.map((item, index) => (
                  <div
                    key={item.key}
                    class='option'
                    onClick={() => this.handleCheck(index)}
                  >
                    {optionRender(item)}
                    <span class='icon-monitor icon-back-right' />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div class='component-top-center'>
            <i class='icon-monitor icon-Transfer' />
          </div>
          <div class='component-top-right'>
            <div class='top-header'>
              <span class='header-title'>{`${this.$t('已选列表')}（${this.selectedFields.length}）`}</span>
              <span
                class='header-btn'
                onClick={this.handleClear}
              >
                {this.$t('全部移除')}
              </span>
            </div>
            <div class='content-wrap'>
              <div class='search-wrap'>
                <bk-input
                  behavior='simplicity'
                  left-icon='bk-icon icon-search'
                  placeholder={this.$t('请输入关键字')}
                  value={this.searchSelectedValue}
                  onChange={v => this.handleSearchValueChange(v, 'selected')}
                />
              </div>
              {this.searchSelectedFields.map(item => (
                <div
                  key={item.key}
                  class='option'
                  onClick={() => this.handleDelete(item)}
                >
                  {optionRender(item)}
                  <span class='icon-monitor icon-mc-close' />
                </div>
              ))}
            </div>
          </div>
        </div>
        <div class='component-bottom'>
          <div class='button-wrap'>
            <bk-button
              class='mr-8'
              theme='primary'
              onClick={() => this.handleConfirm()}
            >
              {this.$t('确定')}
            </bk-button>
            <bk-button onClick={() => this.handleCancel()}>{this.$t('取消')}</bk-button>
          </div>
        </div>
      </div>
    );
  }
}
