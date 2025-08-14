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

import ConditionCreator from '../../../components/condition/condition-creator';
import { ConditionVariableModel } from '../../index';
import VariableCommonForm from '../common-form/variable-common-form';

import type { IConditionVariableModel } from '../../../typings';

import './condition-variable.scss';
interface ConditionVariableEvents {
  onDataChange: (variable: ConditionVariableModel) => void;
}
interface ConditionVariableProps {
  variable: ConditionVariableModel;
}

@Component
export default class ConditionVariable extends tsc<ConditionVariableProps, ConditionVariableEvents> {
  @Prop({ type: Object, required: true }) variable!: ConditionVariableModel;
  @Ref() variableCommonForm!: VariableCommonForm;

  checkboxDisabled(dimension) {
    const isAllDisabled =
      dimension.id === 'all' && this.variable.dimensionOption.length && !this.variable.dimensionOption.includes('all');
    const isOtherDisabled = dimension.id !== 'all' && this.variable.dimensionOption.includes('all');
    return isAllDisabled || isOtherDisabled;
  }

  handleDimensionChange(value) {
    this.handleDataChange({
      ...this.variable.data,
      dimensionOption: value,
    });
  }

  handleValueChange(value) {
    this.handleDataChange({
      ...this.variable.data,
      value,
    });
  }

  handleDataChange(data: IConditionVariableModel) {
    this.$emit(
      'dataChange',
      new ConditionVariableModel({
        ...data,
      })
    );
  }

  validateForm() {
    return this.variableCommonForm.validateForm();
  }

  render() {
    return (
      <div class='condition-variable'>
        <VariableCommonForm
          ref='variableCommonForm'
          data={this.variable.data}
          onDataChange={this.handleDataChange}
        >
          <bk-form-item
            label={this.$t('关联指标')}
            property='value'
          >
            <bk-input
              value={this.variable?.metric?.related_name}
              readonly
            />
          </bk-form-item>
          <bk-form-item
            label={this.$t('可选维度')}
            property='value'
          >
            <bk-select
              clearable={false}
              selected-style='checkbox'
              value={this.variable.dimensionOption}
              multiple
              onChange={this.handleDimensionChange}
            >
              {this.variable.dimensionList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  disabled={this.checkboxDisabled(item)}
                  name={item.name}
                />
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            label={this.$t('默认值')}
            property='value'
          >
            <ConditionCreator
              hasVariableOperate={false}
              options={this.variable.dimensionOption}
              showLabel={false}
            />
          </bk-form-item>
        </VariableCommonForm>
      </div>
    );
  }
}
