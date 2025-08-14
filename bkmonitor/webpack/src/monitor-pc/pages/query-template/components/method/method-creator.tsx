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

import AddVariableOption from '../utils/add-variable-option';
import SelectWrap from '../utils/select-wrap';
import VariableName from '../utils/variable-name';

import type { IMethodOptionsItem, IVariablesItem } from '../type/query-config';

import './method-creator.scss';

interface IProps {
  options?: IMethodOptionsItem[];
  showLabel?: boolean;
  showVariables?: boolean;
  variables?: IVariablesItem[];
  onChange?: (val: string) => void;
  onCreateVariable?: (val: string) => void;
}

@Component
export default class MethodCreator extends tsc<IProps> {
  /* 是否展示左侧标签 */
  @Prop({ default: true }) showLabel: boolean;
  /* 变量列表 */
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  /* 可选项列表 */
  @Prop({ default: () => [] }) options: IMethodOptionsItem[];
  /* 是否展示变量 */
  @Prop({ default: false }) showVariables: boolean;

  showSelect = false;
  /* 所有可选项（包含变量） */
  allOptions: IMethodOptionsItem[] = [];

  popClickHide = true;

  curValue: IMethodOptionsItem = null;

  @Watch('options', { immediate: true })
  handleWatchOptions() {
    this.getAllOptions();
  }

  @Watch('variables', { immediate: true })
  handleWatchVariables() {
    this.getAllOptions();
  }

  getAllOptions() {
    this.allOptions = [
      ...this.variables.map(item => ({
        ...item,
        id: item.name,
        isVariable: true,
      })),
      ...this.options,
    ];
  }

  handleOpenChange(val: boolean) {
    this.showSelect = val;
  }

  handleAddVariableOpenChange(val: boolean) {
    this.popClickHide = !val;
  }

  handleSelect(item: IMethodOptionsItem) {
    if (!this.popClickHide) {
      return;
    }
    this.curValue = item;
    this.$emit('change', item);
    this.showSelect = false;
  }

  handleAddVar(val) {
    console.log(val);
    this.$emit('createVariable', val);
  }

  render() {
    return (
      <div class='template-method-creator-component'>
        {this.showLabel && <div class='method-label'>{this.$slots?.label || this.$t('汇聚方法')}</div>}
        <SelectWrap
          expanded={this.showSelect}
          minWidth={127}
          needPop={true}
          popClickHide={this.popClickHide}
          onOpenChange={this.handleOpenChange}
        >
          <span class='method-name'>
            {this.curValue?.isVariable ? <VariableName name={this.curValue.name} /> : this.curValue?.name}
            {!this.curValue && <p class='placeholder'>{this.$t('请选择')}</p>}
          </span>
          <div
            class='template-method-creator-component-options-popover'
            slot='popover'
          >
            {this.showVariables && (
              <AddVariableOption
                onAdd={this.handleAddVar}
                onOpenChange={this.handleAddVariableOpenChange}
              />
            )}

            {this.allOptions.map((item, index) => (
              <div
                key={index}
                class='options-item'
                onClick={() => this.handleSelect(item)}
              >
                {item.isVariable ? (
                  <span class='options-item-name'>
                    <VariableName name={item.name} />
                  </span>
                ) : (
                  <span class='options-item-name'>{item.name}</span>
                )}
              </div>
            ))}
          </div>
        </SelectWrap>
      </div>
    );
  }
}
