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

import { Debounce, random } from 'monitor-common/utils';
import { detectOperatingSystem } from 'monitor-common/utils/navigator';

import {
  type IFilterField,
  type IFilterItem,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  ECondition,
  EFieldType,
  EMethod,
  fieldTypeMap,
  getTitleAndSubtitle,
  isNumeric,
} from './utils';
import ValueTagSelector, { type IValue } from './value-tag-selector';

import type { IFieldItem, TGetValueFn } from './value-selector-typing';

import './ui-selector-options.scss';

interface IProps {
  fields: IFilterField[];
  keyword?: string; // 上层传的关键字，用于搜索
  show?: boolean;
  value?: IFilterItem;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onCancel?: () => void;
  onConfirm?: (v: IFilterItem) => void;
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
  @Prop({ type: String, default: '' }) keyword: string;

  @Ref('allInput') allInputRef;
  @Ref('valueSelector') valueSelectorRef: ValueTagSelector;
  @Ref('searchInput') searchInputRef;
  /* 搜索值 */
  searchValue = '';
  searchLocalFields: IFilterField[] = [];
  /* 当前光标选中项 */
  cursorIndex = 0;
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
  rightRefreshKey = random(8);
  rightFocus = false;
  cacheCheckedName = '';
  isMacSystem = false;

  get wildcardItem() {
    return this.checkedItem?.supported_operations?.find(item => item.value === this.method)?.options;
  }

  get isTypeInteger() {
    return this.checkedItem?.type === EFieldType.integer;
  }

  get isIntegerError() {
    return this.isTypeInteger ? this.values.some(v => !isNumeric(v.id)) : false;
  }

  get valueSelectorFieldInfo(): IFieldItem {
    return {
      field: this.checkedItem?.name,
      alias: this.checkedItem?.alias,
      isEnableOptions: !!this.checkedItem?.is_option_enabled,
      methods: this.checkedItem.supported_operations.map(item => ({
        id: item.value,
        name: item.alias,
      })),
      type: this.checkedItem?.type,
    };
  }

  created() {
    this.isMacSystem = detectOperatingSystem() === 'macOS';
  }

  mounted() {
    document.addEventListener('keydown', this.handleKeydownEvent);
  }
  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeydownEvent);
  }

  @Watch('fields', { immediate: true })
  handleWatchFields() {
    this.handleSearchChange();
  }

  @Watch('show', { immediate: true })
  handleWatchShow() {
    if (!this.show) {
      this.initData();
    }
    if (this.show) {
      if (this.value) {
        const id = this.value.key.id;
        for (const item of this.fields) {
          if (item.name === id) {
            const checkedItem = JSON.parse(JSON.stringify(item));
            this.handleCheck(
              checkedItem,
              this.value.method.id,
              this.value.value,
              !!this.value?.options?.is_wildcard,
              true
            );
            break;
          }
        }
      } else {
        this.handleCheck(this.fields[0]);
        setTimeout(() => {
          this.searchInputRef?.focus();
        }, 200);
      }
    }
  }

  initData() {
    this.searchValue = '';
    this.cursorIndex = 0;
    this.checkedItem = null;
    this.queryString = '';
    this.method = '';
    this.values = [];
    this.isWildcard = false;
    this.rightFocus = false;
    this.cacheCheckedName = '';
    this.handleWatchFields();
  }

  /**
   * @description 选中
   * @param item
   */
  handleCheck(item: IFilterField, method = '', value = [], isWildcard = false, isFocus = false) {
    this.checkedItem = JSON.parse(JSON.stringify(item));
    this.values = value || [];
    this.method = method || item?.supported_operations?.[0]?.value || '';
    this.isWildcard = isWildcard;
    const index = this.searchLocalFields.findIndex(f => f.name === item.name) || 0;
    if (this.checkedItem.name === '*') {
      this.queryString = value[0]?.id || '';
    } else {
      if (this.cacheCheckedName !== item.name) {
        this.rightRefreshKey = random(8);
      }
      this.cacheCheckedName = item.name;
      if (isFocus) {
        this.$nextTick(() => {
          this.valueSelectorRef?.focusFn?.();
          this.rightFocus = true;
        });
      }
    }
    this.cursorIndex = index;
  }

  /**
   * @description 点击确定
   */
  handleConfirm() {
    if (this.checkedItem.name === '*' && this.queryString) {
      const value: IFilterItem = {
        key: { id: this.checkedItem.name, name: this.$tc('全文') },
        method: { id: EMethod.include, name: this.$tc('包含') },
        value: [{ id: this.queryString, name: this.queryString }],
        condition: { id: ECondition.and, name: 'AND' },
      };
      this.$emit('confirm', value);
      return;
    }
    if (this.values.length) {
      const methodName = this.checkedItem.supported_operations.find(item => item.value === this.method)?.alias;
      const value: IFilterItem = {
        key: { id: this.checkedItem.name, name: this.checkedItem.alias },
        method: { id: this.method as any, name: methodName || '=' },
        value: this.values,
        condition: { id: ECondition.and, name: 'AND' },
        options: this.isWildcard
          ? {
              is_wildcard: true,
            }
          : undefined,
      };
      this.$emit('confirm', value);
    } else {
      this.$emit('confirm', null);
    }
  }
  handleCancel() {
    this.$emit('cancel');
  }

  /**
   * @description 检索值更新
   * @param v
   */
  handleValueChange(v: IValue[]) {
    this.values = v;
  }

  // /**
  //  * @description 是否通配符
  //  */
  // handleIsWildcardChange() {
  //   this.handleChange();
  // }

  // handleChange() {
  //   if (this.values.length) {
  //     const methodName = this.checkedItem.supported_operations.find(item => item.value === this.method)?.alias;
  //     const value: IFilterItem = {
  //       key: { id: this.checkedItem.name, name: this.checkedItem.alias },
  //       method: { id: this.method as any, name: methodName },
  //       value: this.values,
  //       condition: { id: ECondition.and, name: 'AND' },
  //       options: this.isWildcard
  //         ? {
  //             is_wildcard: true,
  //           }
  //         : undefined,
  //     };
  //     this.$emit('change', value);
  //   }
  // }

  /**
   * @description 监听键盘事件
   * @param event
   * @returns
   */
  handleKeydownEvent(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.handleCancel();
    } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      if (!this.isIntegerError) {
        this.handleConfirm();
      }
      return;
    }
    if (this.rightFocus) {
      return;
    }
    switch (event.key) {
      case 'ArrowUp': {
        // 按下上箭头键
        event.preventDefault();
        this.cursorIndex -= 1;
        if (this.cursorIndex < 0) {
          this.cursorIndex = this.searchLocalFields.length - 1;
        }
        this.updateSelection();
        this.enterSelectionDebounce();
        break;
      }

      case 'ArrowDown': {
        event.preventDefault();
        this.cursorIndex += 1;
        if (this.cursorIndex > this.searchLocalFields.length) {
          this.cursorIndex = 0;
        }
        this.updateSelection();
        this.enterSelectionDebounce();
        break;
      }
      case 'Enter': {
        event.preventDefault();
        this.enterSelectionDebounce(true);
        break;
      }
    }
  }
  /**
   * @description 聚焦选中项
   */
  updateSelection() {
    this.$nextTick(() => {
      const listEl = this.$el.querySelector('.component-top-left .options-wrap');
      const el = listEl?.children?.[this.cursorIndex];
      if (el) {
        el.scrollIntoView(false);
      }
    });
  }
  /**
   * @description 回车选中项
   */
  enterSelection(isFocus = false) {
    const item = this.searchLocalFields[this.cursorIndex];
    if (item) {
      if (item.name === '*') {
        if (!this.keyword) this.allInputRef?.focus();
      } else {
        this.queryString = '';
        this.handleCheck(item, '', [], false, isFocus);
      }
    }
  }

  @Debounce(500)
  enterSelectionDebounce(isFocus = false) {
    this.enterSelection(isFocus);
  }

  handleSearchChange() {
    this.cursorIndex = -1;
    if (!this.searchValue) {
      this.searchLocalFields = this.fields.slice();
    }
    this.searchLocalFields = this.fields.filter(item => {
      if (!this.searchValue) {
        return true;
      }
      if (item.alias.toLocaleLowerCase().includes(this.searchValue.toLocaleLowerCase())) {
        return true;
      }
      if (item.name.toLocaleLowerCase().includes(this.searchValue.toLocaleLowerCase())) {
        return true;
      }
      return false;
    });
  }

  @Debounce(300)
  handleSearchChangeDebounce() {
    this.handleSearchChange();
  }

  handleValueSelectorBlur() {
    this.rightFocus = false;
  }
  handleSelectorFocus() {
    this.rightFocus = true;
  }

  getValueFnProxy(params: { field: string; limit: number; search: string }): any | TGetValueFn {
    return new Promise((resolve, _reject) => {
      this.getValueFn({
        where: params.search
          ? [
              {
                key: params.field,
                method: this.checkedItem?.type === EFieldType.integer ? 'eq' : 'include',
                value: [params.search],
                condition: ECondition.and,
                options: {
                  is_wildcard: true,
                },
              },
            ]
          : [],
        fields: [params.field],
        limit: params.limit,
        isInit__: params?.isInit__ || false,
      })
        .then(data => {
          resolve(data);
        })
        .catch(() => {
          resolve({
            count: 0,
            list: [],
          });
        });
    });
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
                ref={'allInput'}
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
              // onClick={e => e.stopPropagation()}
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
                {!!this.wildcardItem && (
                  <span class='right'>
                    <bk-checkbox
                      v-model={this.isWildcard}
                      // onChange={this.handleIsWildcardChange}
                    >
                      {this.wildcardItem?.label || '使用通配符'}
                    </bk-checkbox>
                  </span>
                )}
              </div>
              <div class='form-item-content mt-6'>
                <ValueTagSelector
                  key={this.rightRefreshKey}
                  ref='valueSelector'
                  fieldInfo={this.valueSelectorFieldInfo}
                  getValueFn={this.getValueFnProxy}
                  value={this.values}
                  autoFocus
                  onChange={this.handleValueChange}
                  onSelectorBlur={this.handleValueSelectorBlur}
                  onSelectorFocus={this.handleSelectorFocus}
                />
              </div>
              {this.isIntegerError ? <div class='error-msg'>{this.$tc('仅支持输入数值类型')}</div> : undefined}
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
                ref='searchInput'
                v-model={this.searchValue}
                behavior='simplicity'
                left-icon='bk-icon icon-search'
                placeholder={this.$t('请输入关键字')}
                onChange={this.handleSearchChangeDebounce}
              />
            </div>
            <div class='options-wrap'>
              {this.searchLocalFields.map((item, index) => {
                const { title, subtitle } = getTitleAndSubtitle(item.alias);
                return (
                  <div
                    key={item.name}
                    class={[
                      'option',
                      { checked: this.checkedItem?.name === item.name },
                      { cursor: index === this.cursorIndex },
                    ]}
                    onClick={() => {
                      this.handleCheck(item, '', [], false, true);
                    }}
                  >
                    <span
                      style={{
                        background: fieldTypeMap[item.type].bgColor,
                        color: fieldTypeMap[item.type].color,
                      }}
                      class='option-icon'
                    >
                      <span class={[fieldTypeMap[item.type].icon, 'option-icon-icon']} />
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
            <span class='desc-item-box'>{`${this.isMacSystem ? 'Cmd' : 'Ctrl'}+Enter`}</span>
            <span class='desc-item-name'>{this.$t('提交查询')}</span>
          </span>
          <div class='operate-btns'>
            <bk-button
              class='mr-8'
              disabled={this.isIntegerError}
              theme='primary'
              onClick={() => this.handleConfirm()}
            >
              {`${this.$t('确定')} ${this.isMacSystem ? 'Cmd' : 'Ctrl'} + Enter`}
            </bk-button>
            <bk-button onClick={() => this.handleCancel()}>{`${this.$t('取消')}`}</bk-button>
          </div>
        </div>
      </div>
    );
  }
}
