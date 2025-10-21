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

import { VariableTypeEnum } from '../../../constants';
import ConditionSelectDetail from '../condition/condition-select-detail';
import DimensionValueSelectDetail from '../dimension-value/dimension-value-select-detail';
import DimensionSelectDetail from '../dimension/dimension-select-detail';
import FunctionSelectDetail from '../function/function-select-detail';
import MethodSelectDetail from '../method/method-select-detail';

import type {
  ConditionVariableModel,
  DimensionValueVariableModel,
  DimensionVariableModel,
  FunctionVariableModel,
  MethodVariableModel,
  VariableModelType,
} from '../../index';

import './variable-value-detail.scss';

interface VariableValueDetailProps {
  metricFunctions?: any[];
  variable: VariableModelType;
}

@Component
export default class VariableValueDetail extends tsc<VariableValueDetailProps> {
  @Prop({ type: Object, required: true }) variable!: VariableModelType;
  @Prop({ type: Array, default: () => [] }) metricFunctions!: any[];

  renderValue() {
    switch (this.variable.type) {
      case VariableTypeEnum.METHOD:
        return <MethodSelectDetail variable={this.variable as MethodVariableModel} />;
      case VariableTypeEnum.GROUP_BY:
        return <DimensionSelectDetail variable={this.variable as DimensionVariableModel} />;
      case VariableTypeEnum.TAG_VALUES:
        return <DimensionValueSelectDetail variable={this.variable as DimensionValueVariableModel} />;
      case VariableTypeEnum.FUNCTIONS:
      case VariableTypeEnum.EXPRESSION_FUNCTIONS:
        return (
          <FunctionSelectDetail
            metricFunctions={this.metricFunctions}
            variable={this.variable as FunctionVariableModel}
          />
        );
      case VariableTypeEnum.CONDITIONS:
        return <ConditionSelectDetail variable={this.variable as ConditionVariableModel} />;
      default:
        return this.variable.value || '--';
    }
  }

  render() {
    return <div class='variable-value-detail'>{this.renderValue()}</div>;
  }
}
