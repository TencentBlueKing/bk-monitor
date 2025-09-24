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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AddVariableWrap from '../utils/add-variable-wrap';
import VariableName from '../utils/variable-name';

import type { IFunctionOptionsItem, IVariablesItem } from '../type/query-config';

import './function-creator-pop.scss';

interface IProps {
  allVariables?: { name: string }[];
  hasCreateVariable?: boolean;
  isExpSupport?: boolean;
  options?: IFunctionOptionsItem[];
  selected?: IFunctionOptionsItem[];
  variables?: IVariablesItem[];
  onAddVar?: (val: string) => void;
  onCancel?: () => void;
  onSelect?: (val: IFunctionOptionsItem) => void;
  onSelectVar?: (val: IVariablesItem) => void;
}

@Component
export default class FunctionCreatorPop extends tsc<IProps> {
  /* 变量列表 */
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  @Prop({ default: true }) hasCreateVariable: boolean;
  /* 可选项列表 */
  @Prop({ default: () => [] }) options: IFunctionOptionsItem[];
  /** 只展示支持表达式的函数 */
  @Prop({ default: false, type: Boolean }) readonly isExpSupport: boolean;
  @Prop({ default: () => [] }) selected: IFunctionOptionsItem[];
  /* 所有变量，用于校验变量名是否重复 */
  @Prop({ default: () => [] }) allVariables: { name: string }[];

  /* 搜索关键词 */
  keyword = '';
  /* 当前选中的函数类型 */
  activeFuncType = '';
  /* 当前选中的函数id */
  activeFuncId = '';
  /* 当前选中的函数 */
  activeItem = null;
  /* 是否点击了创建变量 */
  isCreateVar = false;
  varName = '';

  get filterList() {
    if (!this.keyword) return this.options;
    return this.options.filter(func =>
      func?.children?.some(item => item.name.toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()))
    );
  }
  get activeFuncList() {
    return (
      this.filterList
        .find(item => item.id === this.activeFuncType)
        ?.children?.filter(item => (this.isExpSupport ? item.support_expression : true)) || []
    );
  }

  get getVariables() {
    return this.variables
      .filter(item => !this.selectedVars.includes(item.name))
      .map(item => ({
        ...item,
        id: item.name,
        isVariable: true,
      }));
  }

  get selectedVars() {
    return this.selected.filter(item => item.isVariable).map(item => item.id);
  }

  handleKeywordChange(v: string) {
    this.keyword = v;
  }
  handleFuncMouseenter(item) {
    this.activeFuncId = item?.id || '';
    this.activeItem = item;
  }

  handleClickCreateVar() {
    this.isCreateVar = true;
    this.activeFuncType = '';
    this.activeFuncId = '';
    this.activeItem = null;
  }

  handleVarNameChange(val) {
    this.varName = val;
  }

  handleClickVar(item: IVariablesItem) {
    this.$emit('selectVar', item);
  }

  handleFuncTypeMouseenter(item) {
    this.activeFuncType = item?.id || '';
    this.activeFuncId = '';
    this.activeItem = item;
    this.isCreateVar = false;
  }

  handleSelectFunc(item) {
    this.$emit('select', item);
  }

  handleAddVar() {
    this.$emit('addVar', this.varName);
  }

  handleCancelCreateVar() {
    this.$emit('cancel');
  }

  render() {
    return (
      <div
        ref='menuPanel'
        class='template-function-creator-component-popover'
        slot='popover'
      >
        <bk-input
          class='panel-search'
          behavior='simplicity'
          placeholder={this.$t('搜索函数')}
          rightIcon='bk-icon icon-search'
          value={this.keyword}
          on-change={this.handleKeywordChange}
        />
        <div class='panel-list'>
          <ul class='panel-item'>
            {this.hasCreateVariable && (
              <li
                key={'create'}
                class={['list-item', { 'item-active': this.isCreateVar }]}
                onClick={() => this.handleClickCreateVar()}
              >
                {this.$t('创建变量')}
                {'${}'}
                <i class='icon-monitor icon-arrow-right arrow-icon' />
              </li>
            )}
            {this.getVariables.map((item, index) => (
              <li
                key={index}
                class={['list-item']}
                onClick={() => this.handleClickVar(item)}
              >
                <VariableName name={item.name} />
                {/* <i class='icon-monitor icon-arrow-right arrow-icon' /> */}
              </li>
            ))}
            {this.filterList.map(item => (
              <li
                key={item.id}
                class={['list-item', { 'item-active': item.id === this.activeFuncType }]}
                on-mouseenter={() => this.handleFuncTypeMouseenter(item)}
              >
                {item.name}
                <i class='icon-monitor icon-arrow-right arrow-icon' />
              </li>
            ))}
          </ul>
          {this.activeFuncList?.length > 0 && (
            <ul class='panel-item'>
              {this.activeFuncList.map(
                item =>
                  item.id.toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()) && (
                    <li
                      key={item.id}
                      class={['list-item', { 'item-active': item.id === this.activeFuncId }]}
                      on-click={() => this.handleSelectFunc(item)}
                      on-mouseenter={() => this.handleFuncMouseenter(item)}
                    >
                      {item.name.slice(0, item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()))}
                      <span style='color: #FF9C00'>
                        {item.name.slice(
                          item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()),
                          item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()) + this.keyword.length
                        )}
                      </span>
                      {item.name.slice(
                        item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()) + this.keyword.length,
                        item.name.length
                      )}
                    </li>
                  )
              )}
            </ul>
          )}
          {(this.activeFuncId || this.activeFuncType) && (
            <div class='panel-desc'>
              <div class='desc-title'>{this.activeItem.name}</div>
              <div class='desc-content'>{this.activeItem.description}</div>
            </div>
          )}
          {(!this.filterList?.length || !this.activeFuncList?.length) && (
            <div class='panel-desc'>
              {this.isCreateVar ? (
                <AddVariableWrap
                  allVariables={this.allVariables}
                  notPop={true}
                  show={this.isCreateVar}
                  value={this.varName}
                  onAdd={this.handleAddVar}
                  onCancel={this.handleCancelCreateVar}
                  onChange={this.handleVarNameChange}
                />
              ) : (
                this.$t('查无数据')
              )}
            </div>
          )}
        </div>
      </div>
    );
  }
}
