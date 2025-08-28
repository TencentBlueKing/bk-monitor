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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import VariablePanel from '../components/variable-panel/variable-panel';
import VariablesGuide from './variable-guide';

import type { VariableModelType } from '../index';

import './variables-manage.scss';

interface VariablesManageEvents {
  onChange: (value: VariableModelType[]) => void;
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
    return this.variablesList.filter(item => item.name.includes(this.searchValue));
  }

  searchValue = '';

  handleClear() {
    this.searchValue = '';
  }

  handleDataChange(value: VariableModelType, index: number) {
    const list = [...this.variablesList];
    list[index] = value;
    this.$emit('change', [...list]);
    this.validateVariable();
  }

  handleDelete(index: number) {
    const list = [...this.variablesList];
    list.splice(index, 1);
    this.$emit('change', [...list]);
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
              onDataChange={value => {
                this.handleDataChange(value, index);
              }}
              onDelete={() => {
                this.handleDelete(index);
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
