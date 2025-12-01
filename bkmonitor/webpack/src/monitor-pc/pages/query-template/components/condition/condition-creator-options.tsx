/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  ECondition,
  getTitleAndSubtitle,
  isNumeric,
} from '../../../../components/retrieval-filter/utils';
import AddVariableWrap from '../../components/utils/add-variable-wrap';
import VariableName from '../../components/utils/variable-name';
import { type IFieldItem, type IFilterField, type IFilterItem, EFieldType } from './typing';
import ValueTagSelector, { type IValue } from './value-tag-selector';

import type { TGetValueFn } from '../../../../components/retrieval-filter/value-selector-typing';

import './condition-creator-options.scss';

interface IProps {
  allVariables?: { name: string }[];
  dimensionValueVariables?: { name: string }[];
  fields: IFilterField[];
  hasVariableOperate?: boolean;
  isEnterSelect?: boolean;
  keyword?: string; // 上层传的关键字，用于搜索
  show?: boolean;
  value?: IFilterItem;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onAddVariableOpenChange?: (val: boolean) => void;
  onCancel?: () => void;
  onConfirm?: (v: IFilterItem) => void;
  onCreateValueVariable?: (val: { name: string; related_tag: string }) => void;
  onCreateVariable?: (variableName: string) => void;
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
  /* 是否含有变量操作模式 */
  @Prop({ type: Boolean, default: false }) hasVariableOperate: boolean;
  /* 快捷键操作中是否需要按下enter键才能选择项目 */
  @Prop({ type: Boolean, default: false }) isEnterSelect: boolean;
  @Prop({ type: Array, default: () => [] }) dimensionValueVariables: { name: string }[];
  /* 所有变量，用于校验变量名是否重复 */
  @Prop({ default: () => [] }) allVariables: { name: string }[];

  @Ref('allInput') allInputRef;
  @Ref('valueSelector') valueSelectorRef: ValueTagSelector;
  @Ref('searchInput') searchInputRef;
  @Ref('addVariableWrap') addVariableWrapRef: AddVariableWrap;
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

  /* 当前是否选中的创建变量选项 */
  isCreateVariable = false;
  variableName = '';

  showCreateVariablePop = false;

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
        const item = this.fields.filter(f => ![EFieldType.custom_operator, EFieldType.variable].includes(f.type))?.[0];
        if (item) {
          this.handleCheck(item, '', [], false, true);
        }
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
    this.isCreateVariable = false;
  }

  /**
   * @description 点击确定
   */
  handleConfirm() {
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
    } else if (this.isCreateVariable && this.variableName) {
      const err = this.addVariableWrapRef?.handleAdd?.() || '';
      if (err) {
        return;
      }
      this.$emit('createVariable', this.variableName);
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
        if (!this.isEnterSelect) {
          this.enterSelectionDebounce();
        }
        break;
      }

      case 'ArrowDown': {
        event.preventDefault();
        this.cursorIndex += 1;
        if (this.cursorIndex > this.searchLocalFields.length) {
          this.cursorIndex = 0;
        }
        this.updateSelection();
        if (!this.isEnterSelect) {
          this.enterSelectionDebounce();
        }

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
      const el = listEl?.children?.[this.hasVariableOperate ? this.cursorIndex + 1 : this.cursorIndex];
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
      } else if (item.type === EFieldType.custom_operator) {
        this.handleClickCreateVariable();
      } else if (item.type === EFieldType.variable) {
        this.handleSelectVariable(item);
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

  handleClickCreateVariable() {
    this.isCreateVariable = true;
    this.cursorIndex = 0;
  }

  handleVariableNameChange(val) {
    this.variableName = val;
  }

  handleSelectVariable(item: IFilterField) {
    const value: IFilterItem = {
      key: { id: item.name, name: item.alias },
      method: { id: '', name: '' },
      value: [],
      condition: { id: ECondition.and, name: 'AND' },
      options: {
        isVariable: true,
      },
    };
    this.$emit('confirm', value);
  }

  handleAddVariableOpenChange(val: boolean) {
    this.showCreateVariablePop = val;
    this.$emit('addVariableOpenChange', val);
  }

  handleCreateValueVariable(val: string) {
    this.$emit('createValueVariable', {
      related_tag: this.checkedItem?.name,
      name: val,
    });
  }

  render() {
    const rightRender = () => {
      if (this.isCreateVariable) {
        return (
          <AddVariableWrap
            ref='addVariableWrap'
            class='mt-16'
            allVariables={this.allVariables}
            hasOperate={false}
            notPop={true}
            show={this.isCreateVariable}
            value={this.variableName}
            onChange={this.handleVariableNameChange}
          />
        );
      }
      return this.checkedItem && this.checkedItem.type !== EFieldType.variable
        ? [
            <div
              key={'method'}
              class='form-item mt-34'
              // onClick={e => e.stopPropagation()}
            >
              <div class='form-item-label'>{this.$t('运算符')}</div>
              <div class='form-item-content mt-6'>
                <bk-select
                  ext-cls={`method-select ${this.method}`}
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
                <span class='left'>{this.$t('筛选值')}</span>
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
                  allVariables={this.allVariables}
                  fieldInfo={this.valueSelectorFieldInfo}
                  getValueFn={this.getValueFnProxy}
                  hasVariableOperate={this.hasVariableOperate}
                  value={this.values}
                  autoFocus
                  onAddVariableOpenChange={this.handleAddVariableOpenChange}
                  onChange={this.handleValueChange}
                  onCreateVariable={this.handleCreateValueVariable}
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
      <div class='retrieval-filter__condition-creator-options-component'>
        <div class='component-top'>
          <div class='component-top-left'>
            <div class='search-wrap'>
              <bk-input
                ref='searchInput'
                v-model={this.searchValue}
                behavior='simplicity'
                left-icon='bk-icon icon-search'
                placeholder={this.$t('请输入 关键字')}
                onChange={this.handleSearchChangeDebounce}
              />
            </div>
            <div class='options-wrap'>
              {this.searchLocalFields.map((item, index) => {
                if (item.type === EFieldType.custom_operator) {
                  return (
                    <div
                      key={'variable-operate'}
                      class={['option', { checked: this.isCreateVariable }, { cursor: index === this.cursorIndex }]}
                      onClick={this.handleClickCreateVariable}
                    >
                      <span class='option-name-title'>
                        {this.$t('创建变量')}
                        {'${}'}
                      </span>
                    </div>
                  );
                }
                if (item.type === EFieldType.variable) {
                  return (
                    <div
                      key={`${index}_variable_${item.name}`}
                      class={[
                        'option',
                        { checked: this.checkedItem?.name === item.name && !this.isCreateVariable },
                        { cursor: index === this.cursorIndex },
                      ]}
                      onClick={() => this.handleSelectVariable(item)}
                    >
                      <VariableName name={item.name}> </VariableName>
                    </div>
                  );
                }
                const { title, subtitle } = getTitleAndSubtitle(item?.alias || '');
                return (
                  <div
                    key={item.name}
                    class={[
                      'option',
                      { checked: this.checkedItem?.name === item.name && !this.isCreateVariable },
                      { cursor: index === this.cursorIndex },
                    ]}
                    onClick={() => {
                      this.handleCheck(item, '', [], false, true);
                    }}
                  >
                    {/* <span
                      style={{
                        background: fieldTypeMap[item.type].bgColor,
                        color: fieldTypeMap[item.type].color,
                      }}
                      class='option-icon'
                    >
                      <span class={[fieldTypeMap[item.type].icon, 'option-icon-icon']} />
                    </span> */}
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
