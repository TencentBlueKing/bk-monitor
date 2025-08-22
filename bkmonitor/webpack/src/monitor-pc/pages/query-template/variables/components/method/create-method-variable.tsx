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

import { MethodVariableModel } from '../../index';
import VariableCommonForm from '../common-form/variable-common-form';

import type { IMethodVariableModel } from '../../../typings';

interface MethodVariableEvents {
  onDataChange: (variable: MethodVariableModel) => void;
}
interface MethodVariableProps {
  variable: MethodVariableModel;
}

@Component
export default class CreateMethodVariable extends tsc<MethodVariableProps, MethodVariableEvents> {
  @Prop({ type: Object, required: true }) variable!: MethodVariableModel;
  @Ref() variableCommonForm!: VariableCommonForm;

  handleValueChange(defaultValue: string) {
    let value = this.variable.value || '';
    if (!this.variable.isValueEditable) {
      value = defaultValue;
    }

    this.handleDataChange({
      ...this.variable.data,
      defaultValue,
      value,
    });
  }

  handleDataChange(data: IMethodVariableModel) {
    this.$emit('dataChange', new MethodVariableModel({ ...data }));
  }

  validateForm() {
    return this.variableCommonForm.validateForm();
  }

  render() {
    return (
      <div class='method-variable'>
        <VariableCommonForm
          ref='variableCommonForm'
          data={this.variable.data}
          onDataChange={this.handleDataChange}
        >
          <bk-form-item
            label={this.$t('默认值')}
            property='defaultValue'
          >
            <bk-select
              clearable={false}
              value={this.variable.defaultValue}
              onChange={this.handleValueChange}
            >
              {this.variable.metric.methodList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </bk-form-item>
        </VariableCommonForm>
      </div>
    );
  }
}
