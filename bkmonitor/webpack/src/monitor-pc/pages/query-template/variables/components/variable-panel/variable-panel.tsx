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
import { Component, Prop, ProvideReactive, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { VariableTypeEnum, VariableTypeMap } from '../../../constants';
import ConditionVariableDetail from '../condition/condition-variable-detail';
import CreateConditionVariable from '../condition/create-condition-variable';
import EditConditionVariableValue from '../condition/edit-condition-variable-value';
import ConstantVariableDetail from '../constant/constant-variable-detail';
import CreateConstantVariable from '../constant/create-constant-variable';
import EditConstantVariableValue from '../constant/edit-constant-variable-value';
import CreateDimensionValueVariable from '../dimension-value/create-dimension-value-variable';
import DimensionValueVariableDetail from '../dimension-value/dimension-value-variable-detail';
import EditDimensionValueVariableValue from '../dimension-value/edit-dimension-value-variable-value';
import CreateDimensionVariable from '../dimension/create-dimension-variable';
import DimensionVariableDetail from '../dimension/dimension-variable-detail';
import EditDimensionVariableValue from '../dimension/edit-dimension-variable-value';
import CreateFunctionVariable from '../function/create-function-variable';
import EditFunctionVariableValue from '../function/edit-function-variable-value';
import FunctionVariableDetail from '../function/function-variable-detail';
import CreateMethodVariable from '../method/create-method-variable';
import EditMethodVariableValue from '../method/edit-method-variable-value';
import MethodVariableDetail from '../method/method-variable-detail';

import type { IVariableFormEvents } from '../../../typings/variables';
import type {
  ConditionVariableModel,
  ConstantVariableModel,
  DimensionValueVariableModel,
  DimensionVariableModel,
  FunctionVariableModel,
  MethodVariableModel,
  VariableModelType,
} from '../../index';

import './variable-panel.scss';

interface VariablePanelEvents extends IVariableFormEvents {
  onDelete: () => void;
}

interface VariablePanelProps {
  /** 变量是否使用 */
  isUseVariable?: boolean;
  metricFunctions?: any[];
  scene?: 'create' | 'detail' | 'edit';
  showConditionTag?: boolean;
  showLabel?: boolean;
  variable: VariableModelType;
  variableList?: VariableModelType[];
}

@Component
export default class VariablePanel extends tsc<VariablePanelProps, VariablePanelEvents> {
  @Prop() variable: VariableModelType;
  @Prop({ default: 'create', type: String }) scene: VariablePanelProps['scene'];
  @Prop({ default: () => [] }) metricFunctions: any[];
  /** 变量是否使用 */
  @Prop({ default: false, type: Boolean }) isUseVariable: boolean;
  @Prop({ default: true }) showLabel!: boolean;
  /** condition类型是否展示and/or tag */
  @Prop({ default: false, type: Boolean }) showConditionTag: boolean;
  /** 变量列表,目前用于判断变量名是否重复 */
  @ProvideReactive('variableList')
  @Prop({ type: Array, default: () => [] })
  variableList: VariableModelType[];
  @Ref() variableForm: any;

  get title() {
    return VariableTypeMap[this.variable.type];
  }

  handleNameChange(value: string) {
    this.$emit('nameChange', value);
  }

  handleAliasChange(value: string) {
    this.$emit('aliasChange', value);
  }

  handleDescChange(value: string) {
    this.$emit('descChange', value);
  }

  handleDefaultValueChange(value: any) {
    this.$emit('defaultValueChange', value);
  }

  handleValueChange(value: any) {
    this.$emit('valueChange', value);
  }

  handleOptionsChange(value: string[]) {
    this.$emit('optionsChange', value);
  }

  handleDelete() {
    if (this.isUseVariable) return;
    this.$emit('delete');
  }

  /** 变量详情 */
  renderVariableDetail() {
    switch (this.variable.type) {
      case VariableTypeEnum.METHOD:
        return <MethodVariableDetail variable={this.variable as MethodVariableModel} />;
      case VariableTypeEnum.GROUP_BY:
        return <DimensionVariableDetail variable={this.variable as DimensionVariableModel} />;
      case VariableTypeEnum.TAG_VALUES:
        return <DimensionValueVariableDetail variable={this.variable as DimensionValueVariableModel} />;
      case VariableTypeEnum.FUNCTIONS:
      case VariableTypeEnum.EXPRESSION_FUNCTIONS:
        return (
          <FunctionVariableDetail
            metricFunctions={this.metricFunctions}
            variable={this.variable as FunctionVariableModel}
          />
        );
      case VariableTypeEnum.CONDITIONS:
        return <ConditionVariableDetail variable={this.variable as ConditionVariableModel} />;
      default:
        return <ConstantVariableDetail variable={this.variable as ConstantVariableModel} />;
    }
  }

  /** 新增变量表单 */
  renderVariableForm() {
    switch (this.variable.type) {
      case VariableTypeEnum.METHOD:
        return (
          <CreateMethodVariable
            ref='variableForm'
            variable={this.variable as MethodVariableModel}
            onAliasChange={this.handleAliasChange}
            onDefaultValueChange={this.handleDefaultValueChange}
            onDescChange={this.handleDescChange}
            onNameChange={this.handleNameChange}
            onValueChange={this.handleValueChange}
          />
        );
      case VariableTypeEnum.GROUP_BY:
        return (
          <CreateDimensionVariable
            ref='variableForm'
            variable={this.variable as DimensionVariableModel}
            onAliasChange={this.handleAliasChange}
            onDefaultValueChange={this.handleDefaultValueChange}
            onDescChange={this.handleDescChange}
            onNameChange={this.handleNameChange}
            onOptionsChange={this.handleOptionsChange}
            onValueChange={this.handleValueChange}
          />
        );
      case VariableTypeEnum.TAG_VALUES:
        return (
          <CreateDimensionValueVariable
            ref='variableForm'
            variable={this.variable as DimensionValueVariableModel}
            onAliasChange={this.handleAliasChange}
            onDefaultValueChange={this.handleDefaultValueChange}
            onDescChange={this.handleDescChange}
            onNameChange={this.handleNameChange}
            onValueChange={this.handleValueChange}
          />
        );
      case VariableTypeEnum.FUNCTIONS:
      case VariableTypeEnum.EXPRESSION_FUNCTIONS:
        return (
          <CreateFunctionVariable
            ref='variableForm'
            metricFunctions={this.metricFunctions}
            variable={this.variable as FunctionVariableModel}
            onAliasChange={this.handleAliasChange}
            onDefaultValueChange={this.handleDefaultValueChange}
            onDescChange={this.handleDescChange}
            onNameChange={this.handleNameChange}
            onValueChange={this.handleValueChange}
          />
        );
      case VariableTypeEnum.CONDITIONS:
        return (
          <CreateConditionVariable
            ref='variableForm'
            variable={this.variable as ConditionVariableModel}
            onAliasChange={this.handleAliasChange}
            onDefaultValueChange={this.handleDefaultValueChange}
            onDescChange={this.handleDescChange}
            onNameChange={this.handleNameChange}
            onOptionsChange={this.handleOptionsChange}
            onValueChange={this.handleValueChange}
          />
        );
      default:
        return (
          <CreateConstantVariable
            ref='variableForm'
            variable={this.variable as ConstantVariableModel}
            onAliasChange={this.handleAliasChange}
            onDefaultValueChange={this.handleDefaultValueChange}
            onDescChange={this.handleDescChange}
            onNameChange={this.handleNameChange}
            onValueChange={this.handleValueChange}
          />
        );
    }
  }

  renderEditVariableValue() {
    switch (this.variable.type) {
      case VariableTypeEnum.METHOD:
        return (
          <EditMethodVariableValue
            showLabel={this.showLabel}
            variable={this.variable as MethodVariableModel}
            onBlur={this.handleEditValueBlur}
            onFocus={this.handleEditValueFocus}
            onValueChange={this.handleValueChange}
          />
        );
      case VariableTypeEnum.GROUP_BY:
        return (
          <EditDimensionVariableValue
            showLabel={this.showLabel}
            variable={this.variable as DimensionVariableModel}
            onBlur={this.handleEditValueBlur}
            onFocus={this.handleEditValueFocus}
            onValueChange={this.handleValueChange}
          />
        );
      case VariableTypeEnum.TAG_VALUES:
        return (
          <EditDimensionValueVariableValue
            showLabel={this.showLabel}
            variable={this.variable as DimensionValueVariableModel}
            onBlur={this.handleEditValueBlur}
            onFocus={this.handleEditValueFocus}
            onValueChange={this.handleValueChange}
          />
        );
      case VariableTypeEnum.FUNCTIONS:
      case VariableTypeEnum.EXPRESSION_FUNCTIONS:
        return (
          <EditFunctionVariableValue
            metricFunctions={this.metricFunctions}
            showLabel={this.showLabel}
            variable={this.variable as FunctionVariableModel}
            onBlur={this.handleEditValueBlur}
            onFocus={this.handleEditValueFocus}
            onValueChange={this.handleValueChange}
          />
        );
      case VariableTypeEnum.CONDITIONS:
        return (
          <EditConditionVariableValue
            showConditionTag={this.showConditionTag}
            showLabel={this.showLabel}
            variable={this.variable as ConditionVariableModel}
            onBlur={this.handleEditValueBlur}
            onFocus={this.handleEditValueFocus}
            onValueChange={this.handleValueChange}
          />
        );
      default:
        return (
          <EditConstantVariableValue
            showLabel={this.showLabel}
            variable={this.variable as ConstantVariableModel}
            onBlur={this.handleEditValueBlur}
            onFocus={this.handleEditValueFocus}
            onValueChange={this.handleValueChange}
          />
        );
    }
  }

  handleEditValueFocus() {
    const queryTemplateViewDom = document.querySelector('.query-template-view');
    const variableDom = queryTemplateViewDom?.querySelectorAll(`#${this.variable.variableName}`);
    if (variableDom) {
      for (const element of Array.from(variableDom)) {
        element.classList.add('variable-tag-active');
      }
    }
  }

  handleEditValueBlur() {
    const queryTemplateViewDom = document.querySelector('.query-template-view');
    const variableDom = queryTemplateViewDom?.querySelectorAll(`#${this.variable.variableName}`);
    if (variableDom) {
      for (const element of Array.from(variableDom)) {
        element.classList.remove('variable-tag-active');
      }
    }
  }

  validateForm() {
    return this.variableForm?.validateForm?.();
  }

  render() {
    if (this.scene === 'edit') return this.renderEditVariableValue();

    return (
      <div class={['variable-panel', this.scene]}>
        <div class='variable-panel-header'>
          <div class='variable-type-title'>{this.title}</div>
          {this.scene === 'create' && (
            <i
              class={['icon-monitor icon-mc-delete-line', { disabled: this.isUseVariable }]}
              v-bk-tooltips={{
                content: this.$t('该变量有被使用，暂不可删除'),
                placements: ['right', 'top-end'],
                disabled: !this.isUseVariable,
              }}
              onClick={this.handleDelete}
            />
          )}
        </div>
        <div class='variable-form'>
          {this.scene === 'detail' ? this.renderVariableDetail() : this.renderVariableForm()}
        </div>
      </div>
    );
  }
}
