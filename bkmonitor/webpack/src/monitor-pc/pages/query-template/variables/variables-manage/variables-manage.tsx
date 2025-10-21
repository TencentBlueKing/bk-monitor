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

import VariablePanel from '../components/variable-panel/variable-panel';
import VariablesGuide from './variable-guide';

import type { VariableModelType } from '../index';

import './variables-manage.scss';

interface VariablesManageEvents {
  onAliasChange: (val: string, index: number) => void;
  onDefaultValueChange: (val: any, index: number) => void;
  onDelete: (index: number) => void;
  onDescChange: (val: string, index: number) => void;
  onNameChange: (val: string, index: number) => void;
  onOptionsChange: (val: string[], index: number) => void;
  onValueChange: (val: any, index: number) => void;
}

interface VariablesManageProps {
  metricFunctions?: any[];
  scene?: 'create' | 'detail' | 'edit';
  /** 已使用的变量列表 */
  useVariables?: string[];
  variablesList: VariableModelType[];
}

const refKey = 'variablePanel';
@Component
export default class VariablesManage extends tsc<VariablesManageProps, VariablesManageEvents> {
  @Prop({ default: () => [] }) variablesList!: VariableModelType[];
  @Prop({ default: () => [] }) metricFunctions!: any[];
  @Prop({ default: 'create' }) scene!: VariablesManageProps['scene'];
  @Prop({ default: () => [] }) useVariables!: string[];

  get showVariableList() {
    return this.variablesList.filter(item =>
      item.name.toLocaleLowerCase().includes(this.searchValue.trim().toLocaleLowerCase())
    );
  }

  searchValue = '';

  handleClear() {
    this.searchValue = '';
  }

  handleNameChange(value: string, index: number) {
    this.$emit('nameChange', value, index);
  }

  handleAliasChange(value: string, index: number) {
    this.$emit('aliasChange', value, index);
  }

  handleDescChange(value: string, index: number) {
    this.$emit('descChange', value, index);
  }

  handleDefaultValueChange(value: any, index: number) {
    this.$emit('defaultValueChange', value, index);
  }

  handleValueChange(value: any, index: number) {
    this.$emit('valueChange', value, index);
  }

  handleOptionsChange(value: string[], index: number) {
    this.$emit('optionsChange', value, index);
  }

  handleDelete(index: number) {
    this.$emit('delete', index);
  }

  validateVariable() {
    return Promise.all(
      this.variablesList.map(variable => (this.$refs[`${refKey}_${variable.id}`] as VariablePanel)?.validateForm())
    );
  }

  render() {
    return (
      <div class={['variables-manage-wrap', this.scene]}>
        {this.scene === 'create' && (
          <div class='variable-manage-header'>
            <div class='manage-title'>{this.$t('变量管理')}</div>
            {this.variablesList.length > 0 && (
              <bk-input
                class='variable-search'
                v-model={this.searchValue}
                placeholder={this.$t('搜索 变量')}
              />
            )}
            <div class='bg-mask-wrap'>
              <div class='bg-mask' />
            </div>
          </div>
        )}
        <div class='variable-manage-content'>
          {this.showVariableList.map((item, index) => [
            <VariablePanel
              key={item.id}
              ref={`${refKey}_${item.id}`}
              isUseVariable={this.useVariables.includes(item.name)}
              metricFunctions={this.metricFunctions}
              scene={this.scene}
              variable={item}
              variableList={this.variablesList}
              onAliasChange={value => {
                this.handleAliasChange(value, index);
              }}
              onDefaultValueChange={value => {
                this.handleDefaultValueChange(value, index);
              }}
              onDelete={() => {
                this.handleDelete(index);
              }}
              onDescChange={value => {
                this.handleDescChange(value, index);
              }}
              onNameChange={value => {
                this.handleNameChange(value, index);
              }}
              onOptionsChange={value => {
                this.handleOptionsChange(value, index);
              }}
              onValueChange={value => {
                this.handleValueChange(value, index);
              }}
            />,
          ])}

          {!this.showVariableList.length && this.scene === 'create' && (
            <VariablesGuide
              mode={this.variablesList.length ? 'search-empty' : 'guide'}
              onClear={this.handleClear}
            />
          )}
        </div>
      </div>
    );
  }
}
