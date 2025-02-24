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

import {
  fieldTypeMap,
  getTitleAndSubtitle,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  type IFilterField,
  ECondition,
  type IFilterItem,
} from './utils';
import ValueTagSelector, { type IValue } from './value-tag-selector';

import './ui-selector-options.scss';

interface IProps {
  fields: IFilterField[];
  value?: IFilterItem;
  show?: boolean;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onConfirm?: (v: IFilterItem) => void;
  onCancel?: () => void;
}
@Component
export default class UiSelectorOptions extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  @Prop({ type: Object, default: () => null }) value: IFilterItem;
  @Prop({ type: Boolean, default: false }) show: boolean;
  /* 搜索值 */
  searchValue = '';
  /* 当前 */
  localFields: IFilterField[] = [];
  /* 当前光标选中项 */
  cursorIndex = -1;
  /* 当前选中项 */
  checkedItem: IFilterField = null;
  /* 全文检索检索内容 */
  queryString = '';
  /* 当前选择的条件 */
  method = '';
  /* 当前选择的检索值 */
  values = [];
  /* 是否使用通配符 */
  isWildcard = false;
  /* 检索值loading */
  valueLoading = false;
  /* 检索值候选项 */
  valueOptions = [];

  get wildcardItem() {
    return this.checkedItem?.supported_operations?.find(item => item.value === this.method)?.options;
  }

  @Watch('fields', { immediate: true })
  handleWatchFields() {
    this.localFields = this.fields;
    if (this.localFields.length) {
      this.handleCheck(this.localFields[0]);
    }
  }

  @Watch('show', { immediate: true })
  handleWatchShow() {
    if (this.show && this.value) {
      const id = this.value.key.id;
      for (const item of this.localFields) {
        if (item.name === id) {
          const checkedItem = JSON.parse(JSON.stringify(item));
          this.handleCheck(checkedItem, this.value.method.id, this.value.value);
          break;
        }
      }
    }
  }

  /**
   * @description 选中
   * @param item
   */
  handleCheck(item: IFilterField, method = '', value = []) {
    this.checkedItem = JSON.parse(JSON.stringify(item));
    this.values = value || [];
    this.valueOptions = [];
    this.valueLoading = true;
    if (this.checkedItem?.name !== '*') {
      this.method = method || this.checkedItem?.supported_operations?.[0]?.value || '';
      this.getValueFn({
        where: [
          {
            key: this.checkedItem.name,
            method: this.method,
            value: this.values,
            condition: ECondition.and,
          },
        ],
        fields: [this.checkedItem.name],
        limit: 5,
      })
        .then(data => {
          this.valueOptions = data.list;
        })
        .finally(() => {
          this.valueLoading = false;
        });
    }
  }

  /**
   * @description 点击确定
   */
  handleConfirm() {
    if (this.values.length) {
      const methodName = this.checkedItem.supported_operations.find(item => item.value === this.method)?.alias;
      const value: IFilterItem = {
        key: { id: this.checkedItem.name, name: this.checkedItem.alias },
        method: { id: this.method as any, name: methodName },
        value: this.values,
        condition: { id: ECondition.and, name: 'AND' },
      };
      this.$emit('confirm', value);
    } else {
      this.$emit('confirm', null);
    }
  }
  handleCancel() {
    this.$emit('cancel');
  }

  handleValueChange(v: IValue[]) {
    this.values = v;
  }

  handleChange() {
    if (this.values.length) {
      const methodName = this.checkedItem.supported_operations.find(item => item.value === this.method)?.alias;
      const value: IFilterItem = {
        key: { id: this.checkedItem.name, name: this.checkedItem.alias },
        method: { id: this.method as any, name: methodName },
        value: this.values,
        condition: { id: ECondition.and, name: 'AND' },
      };
      this.$emit('change', value);
    }
  }

  render() {
    const rightRender = () => {
      if (this.checkedItem?.name === '*') {
        return [
          <div
            key={'all'}
            class='form-item'
          >
            <div class='form-item-label mt-16'>{this.$t('检索内容')}</div>
            <div class='form-item-content mt-8'>
              <bk-input
                v-model={this.queryString}
                placeholder={this.$t('请输入')}
                rows={15}
                type={'textarea'}
              />
            </div>
          </div>,
        ];
      }
      return this.checkedItem
        ? [
            <div
              key={'method'}
              class='form-item mt-34'
              onClick={e => e.stopPropagation()}
            >
              <div class='form-item-label'>{this.$t('条件')}</div>
              <div class='form-item-content mt-6'>
                <bk-select
                  ext-cls={'method-select'}
                  v-model={this.method}
                  popover-options={{
                    appendTo: 'parent',
                  }}
                  clearable={false}
                >
                  {this.checkedItem.supported_operations.map(item => (
                    <bk-option
                      id={item.value}
                      key={item.value}
                      name={item.alias}
                    />
                  ))}
                </bk-select>
              </div>
            </div>,
            <div
              key={'value'}
              class='form-item mt-16'
            >
              <div class='form-item-label'>
                <span class='left'>{this.$t('检索值')}</span>
                <span class='right'>
                  <bk-checkbox v-model={this.isWildcard}>{this.wildcardItem?.label || '使用通配符'}</bk-checkbox>
                </span>
              </div>
              <div class='form-item-content mt-6'>
                <ValueTagSelector
                  loading={this.valueLoading}
                  options={this.valueOptions}
                  value={this.values}
                  onChange={this.handleValueChange}
                />
              </div>
            </div>,
          ]
        : undefined;
    };
    return (
      <div class='retrieval-filter__ui-selector-options-component'>
        <div class='component-top'>
          <div class='component-top-left'>
            <div class='search-wrap'>
              <bk-input
                v-model={this.searchValue}
                behavior='simplicity'
                left-icon='bk-icon icon-search'
                placeholder={this.$t('请输入关键字')}
              />
            </div>
            <div class='options-wrap'>
              {this.localFields.map(item => {
                const { title, subtitle } = getTitleAndSubtitle(item.alias);
                return (
                  <div
                    key={item.name}
                    class={['option', { checked: this.checkedItem?.name === item.name }]}
                    onClick={() => this.handleCheck(item)}
                  >
                    <span
                      style={{
                        background: fieldTypeMap[item.type].bgColor,
                        color: fieldTypeMap[item.type].color,
                      }}
                      class='option-icon'
                    >
                      {item.name === '*' ? (
                        <span class='option-icon-xing'>*</span>
                      ) : (
                        <span class={[fieldTypeMap[item.type].icon, 'option-icon-icon']} />
                      )}
                    </span>
                    <span class='option-name-title'>{title}</span>
                    {!!subtitle && <span class='option-name-subtitle'>（{subtitle}）</span>}
                  </div>
                );
              })}
            </div>
          </div>
          <div class='component-top-right'>{rightRender()}</div>
        </div>
        <div class='component-bottom'>
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
            <span class='desc-item-name'>{this.$t('选中')}</span>
          </span>
          <span class='desc-item'>
            <span class='desc-item-box'>Esc</span>
            <span class='desc-item-name'>{this.$t('收起查询')}</span>
          </span>
          <span class='desc-item'>
            <span class='desc-item-box'>Ctrl+Enter</span>
            <span class='desc-item-name'>{this.$t('提交查询')}</span>
          </span>
          <div class='operate-btns'>
            <bk-button
              class='mr-8'
              theme='primary'
              onClick={() => this.handleConfirm()}
            >
              {`${this.$t('确定')} Ctrl+ Enter`}
            </bk-button>
            <bk-button onClick={() => this.handleCancel()}>{`${this.$t('取消')}`}</bk-button>
          </div>
        </div>
      </div>
    );
  }
}
