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

import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { VariableTypeEnum } from '../../../../query-template/constants';
import FunctionCreator from '../../../components/function/function-creator';
import EditVariableValue from '../common-form/edit-variable-value';

import type { AggFunction } from '../../../../query-template/typings';
import type { FunctionVariableModel } from '../../index';

interface FunctionValueEvents {
  onBlur: () => void;
  onFocus: () => void;
  onValueChange: (value: AggFunction[]) => void;
}

interface FunctionValueProps {
  metricFunctions: any[];
  variable: FunctionVariableModel;
}

@Component
export default class EditFunctionVariableValue extends tsc<FunctionValueProps, FunctionValueEvents> {
  @Prop({ type: Object, required: true }) variable!: FunctionVariableModel;
  @Prop({ default: () => [] }) metricFunctions!: any[];

  get isUseExpression() {
    return this.variable.type === VariableTypeEnum.EXPRESSION_FUNCTIONS;
  }

  @Emit('valueChange')
  handleValueChange(value: AggFunction[]) {
    return value;
  }

  handleSelectToggle(value: boolean) {
    if (value) {
      this.$emit('focus');
    } else {
      this.$emit('blur');
    }
  }

  render() {
    return (
      <EditVariableValue data={this.variable.data}>
        <FunctionCreator
          isExpSupport={this.isUseExpression}
          needClear={false}
          options={this.metricFunctions}
          showLabel={false}
          showVariables={false}
          value={this.variable.data.value}
          onChange={this.handleValueChange}
          onOpenChange={this.handleSelectToggle}
        />
      </EditVariableValue>
    );
  }
}
