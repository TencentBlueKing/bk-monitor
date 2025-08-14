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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import { VariableTypeEnum, VariableTypeMap } from '../../../constants';
import ConditionDetail from '../condition/condition-detail';
import ConditionValue from '../condition/condition-value';
import ConditionVariable from '../condition/condition-variable';
import ConstantDetail from '../constant/constant-detail';
import ConstantValue from '../constant/constant-value';
import ConstantVariable from '../constant/constant-variable';
import DimensionValueDetail from '../dimension-value/dimension-value-detail';
import DimensionValueValue from '../dimension-value/dimension-value-value';
import DimensionValueVariable from '../dimension-value/dimension-value-variable';
import DimensionDetail from '../dimension/dimension-detail';
import DimensionValue from '../dimension/dimension-value';
import DimensionVariable from '../dimension/dimension-variable';
import FunctionDetail from '../function/function-detail';
import FunctionValue from '../function/function-value';
import FunctionVariable from '../function/function-variable';
import MethodDetail from '../method/method-detail';
import MethodValue from '../method/method-value';
import MethodVariable from '../method/method-variable';

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
}

interface VariablePanelProps {
  metricFunctions?: any[];
  scene?: 'create' | 'detail' | 'edit';
  variable: VariableModelType;
}

@Component
export default class VariablePanel extends tsc<VariablePanelProps, VariablePanelEvents> {
  @Prop() variable: VariableModelType;
  @Prop({ default: 'create', type: String }) scene: VariablePanelProps['scene'];
  @Prop({ default: () => [] }) metricFunctions: any[];
  @Ref() variableForm: any;

  get title() {
    return VariableTypeMap[this.variable.type];
  }

  @Debounce(200)
  handleDataChange(value: VariableModelType) {
    this.$emit('dataChange', value);
  }

  /** 变量详情 */
  renderVariableDetail() {
    switch (this.variable.type) {
      case VariableTypeEnum.METHOD:
        return <MethodDetail variable={this.variable as MethodVariableModel} />;
      case VariableTypeEnum.DIMENSION:
        return <DimensionDetail variable={this.variable as DimensionVariableModel} />;
      case VariableTypeEnum.DIMENSION_VALUE:
        return <DimensionValueDetail variable={this.variable as DimensionValueVariableModel} />;
      case VariableTypeEnum.FUNCTION:
        return <FunctionDetail variable={this.variable as FunctionVariableModel} />;
      case VariableTypeEnum.CONDITION:
        return <ConditionDetail variable={this.variable as ConditionVariableModel} />;
      default:
        return <ConstantDetail variable={this.variable as ConstantVariableModel} />;
    }
  }

  /** 新增变量表单 */
  renderVariableForm() {
    switch (this.variable.type) {
      case VariableTypeEnum.METHOD:
        return (
          <MethodVariable
            ref='variableForm'
            variable={this.variable as MethodVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.DIMENSION:
        return (
          <DimensionVariable
            ref='variableForm'
            variable={this.variable as DimensionVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.DIMENSION_VALUE:
        return (
          <DimensionValueVariable
            ref='variableForm'
            variable={this.variable as DimensionValueVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.FUNCTION:
        return (
          <FunctionVariable
            ref='variableForm'
            metricFunctions={this.metricFunctions}
            variable={this.variable as FunctionVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.CONDITION:
        return (
          <ConditionVariable
            ref='variableForm'
            variable={this.variable as ConditionVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      default:
        return (
          <ConstantVariable
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
          <MethodValue
            variable={this.variable as MethodVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      case VariableTypeEnum.DIMENSION:
        return (
          <DimensionValue
            variable={this.variable as DimensionVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      case VariableTypeEnum.DIMENSION_VALUE:
        return (
          <DimensionValueValue
            variable={this.variable as DimensionValueVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      case VariableTypeEnum.FUNCTION:
        return (
          <FunctionValue
            metricFunctions={this.metricFunctions}
            variable={this.variable as FunctionVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      case VariableTypeEnum.CONDITION:
        return (
          <ConditionValue
            variable={this.variable as ConditionVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
      default:
        return (
          <ConstantValue
            variable={this.variable as ConstantVariableModel}
            onBlur={this.handleEditValueBlur}
            onChange={this.handleDataChange}
            onFocus={this.handleEditValueFocus}
          />
        );
    }
  }

  handleEditValueBlur() {}

  handleEditValueFocus() {}

  validateForm() {
    return this.variableForm?.validateForm?.();
  }

  render() {
    if (this.scene === 'edit') return this.renderEditVariableValue();

    return (
      <div class={['variable-panel', this.scene]}>
        <div class='variable-type-title'>{this.title}</div>
        <div class='variable-form'>
          {this.scene === 'detail' ? this.renderVariableDetail() : this.renderVariableForm()}
        </div>
      </div>
    );
  }
}
