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
import { Component, Mixins, Prop, Ref } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import { VariableTypeEnum } from '../../../../query-template/constants';
import FunctionCreator from '../../../components/function/function-creator';
import VariableFormMixin from '../../mixins/VariableFormMixin';
import VariableCommonForm from '../common-form/variable-common-form';

import type { AggFunction, IVariableFormEvents } from '../../../typings';
import type { FunctionVariableModel } from '../../index';
interface FunctionVariableEvents extends IVariableFormEvents {
  onDefaultValueChange: (val: AggFunction[]) => void;
  onValueChange: (val: AggFunction[]) => void;
}
interface FunctionVariableProps {
  metricFunctions: any[];
  variable: FunctionVariableModel;
}

@Component
class CreateFunctionVariable extends Mixins(VariableFormMixin) {
  @Prop({ type: Object, required: true }) variable!: FunctionVariableModel;
  @Prop({ default: () => [] }) metricFunctions!: any[];
  @Ref() variableCommonForm!: VariableCommonForm;

  get isUseExpression() {
    return this.variable.type === VariableTypeEnum.EXPRESSION_FUNCTIONS;
  }

  defaultValueChange(defaultValue: AggFunction[]) {
    let value = this.variable.value || [];
    if (!this.variable.isValueEditable) {
      value = defaultValue;
    }
    this.handleDefaultValueChange(defaultValue);
    this.handleValueChange(value);
  }

  validateForm() {
    return this.variableCommonForm.validateForm();
  }

  render() {
    return (
      <div class='function-variable'>
        <VariableCommonForm
          ref='variableCommonForm'
          data={this.variable.data}
          onAliasChange={this.handleAliasChange}
          onDescChange={this.handleDescChange}
          onNameChange={this.handleNameChange}
        >
          <bk-form-item
            label={this.$t('默认值')}
            property='defaultValue'
          >
            <FunctionCreator
              isExpSupport={this.isUseExpression}
              needClear={false}
              options={this.metricFunctions}
              showLabel={false}
              showVariables={false}
              value={this.variable.defaultValue}
              onChange={this.defaultValueChange}
            />
          </bk-form-item>
        </VariableCommonForm>
      </div>
    );
  }
}

export default tsx.ofType<FunctionVariableProps, FunctionVariableEvents>().convert(CreateFunctionVariable);
