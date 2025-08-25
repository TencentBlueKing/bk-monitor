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
import { Component, Prop, ProvideReactive, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

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

interface VariablePanelEvents {
  onDataChange: (variable: VariableModelType) => void;
  onDelete: () => void;
}

interface VariablePanelProps {
  /** 变量是否使用 */
  isUseVariable?: boolean;
  metricFunctions?: any[];
  scene?: 'create' | 'detail' | 'edit';
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

  @ProvideReactive('variableList')
  @Prop({ type: Array, default: () => [] })
  variableList: VariableModelType[];
  @Ref() variableForm: any;

  get title() {
    return VariableTypeMap[this.variable.type];
  }

  @Debounce(200)
  handleDataChange(value: VariableModelType) {
    this.$emit('dataChange', value);
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
      case VariableTypeEnum.DIMENSION:
        return <DimensionVariableDetail variable={this.variable as DimensionVariableModel} />;
      case VariableTypeEnum.DIMENSION_VALUE:
        return <DimensionValueVariableDetail variable={this.variable as DimensionValueVariableModel} />;
      case VariableTypeEnum.FUNCTION:
        return (
          <FunctionVariableDetail
            metricFunctions={this.metricFunctions}
            variable={this.variable as FunctionVariableModel}
          />
        );
      case VariableTypeEnum.CONDITION:
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
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.DIMENSION:
        return (
          <CreateDimensionVariable
            ref='variableForm'
            variable={this.variable as DimensionVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.DIMENSION_VALUE:
        return (
          <CreateDimensionValueVariable
            ref='variableForm'
            variable={this.variable as DimensionValueVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.FUNCTION:
        return (
          <CreateFunctionVariable
            ref='variableForm'
            metricFunctions={this.metricFunctions}
            variable={this.variable as FunctionVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.CONDITION:
        return (
          <CreateConditionVariable
            ref='variableForm'
            variable={this.variable as ConditionVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      default:
        return (
          <CreateConstantVariable
            ref='variableForm'
            variable={this.variable as ConstantVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
    }
  }

  renderEditVariableValue() {
    switch (this.variable.type) {
      case VariableTypeEnum.METHOD:
        return (
          <EditMethodVariableValue
            variable={this.variable as MethodVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      case VariableTypeEnum.DIMENSION:
        return (
          <EditDimensionVariableValue
            variable={this.variable as DimensionVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      case VariableTypeEnum.DIMENSION_VALUE:
        return (
          <EditDimensionValueVariableValue
            variable={this.variable as DimensionValueVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      case VariableTypeEnum.FUNCTION:
        return (
          <EditFunctionVariableValue
            metricFunctions={this.metricFunctions}
            variable={this.variable as FunctionVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      case VariableTypeEnum.CONDITION:
        return (
          <EditConditionVariableValue
            variable={this.variable as ConditionVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      default:
        return (
          <EditConstantVariableValue
            variable={this.variable as ConstantVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
    }
  }

  handleEditValueFocus() {
    const queryTemplateViewDom = document.querySelector('.query-template-view');
    const variableDom = queryTemplateViewDom?.querySelectorAll(`#${this.variable.variableName}`);
    console.log(variableDom);
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
