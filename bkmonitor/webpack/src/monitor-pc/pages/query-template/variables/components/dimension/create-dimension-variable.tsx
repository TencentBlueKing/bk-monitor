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

import { DimensionVariableModel } from '../../index';
import VariableCommonForm from '../common-form/variable-common-form';

import type { IDimensionVariableModel } from '../../../typings';
interface DimensionVariableEvents {
  onDataChange: (variable: DimensionVariableModel) => void;
}
interface DimensionVariableProps {
  variable: DimensionVariableModel;
}

@Component
export default class CreateDimensionVariable extends tsc<DimensionVariableProps, DimensionVariableEvents> {
  @Prop({ type: Object, required: true }) variable!: DimensionVariableModel;
  @Ref() variableCommonForm!: VariableCommonForm;

  rules = {
    options: [
      {
        required: true,
        message: this.$t('可选维度值必选'),
        trigger: 'blur',
      },
    ],
  };

  checkboxDisabled(dimensionId: string) {
    const isAllDisabled = dimensionId === 'all' && this.variable.options.length && !this.variable.isAllDimensionOptions;
    const isOtherDisabled = dimensionId !== 'all' && this.variable.isAllDimensionOptions;
    return isAllDisabled || isOtherDisabled;
  }

  handleDimensionChange(value: string[]) {
    let defaultValue = this.variable.data.defaultValue;
    if (value.includes('all')) {
      defaultValue = defaultValue || [this.variable.dimensionList[0].id];
    } else {
      defaultValue = defaultValue.filter(item => value.includes(item));
      defaultValue = defaultValue.length ? defaultValue : [value[0]];
    }

    this.handleDataChange({
      ...this.variable.data,
      options: value,
      defaultValue,
    });
  }

  handleValueChange(value: string[]) {
    this.handleDataChange({
      ...this.variable.data,
      defaultValue: value,
    });
  }

  handleDataChange(data: IDimensionVariableModel) {
    this.$emit(
      'dataChange',
      new DimensionVariableModel({
        ...data,
      })
    );
  }

  validateForm() {
    return this.variableCommonForm.validateForm();
  }

  render() {
    return (
      <div class='dimension-variable'>
        <VariableCommonForm
          ref='variableCommonForm'
          data={this.variable.data}
          rules={this.rules}
          onDataChange={this.handleDataChange}
        >
          <bk-form-item label={this.$t('关联指标')}>
            <bk-input
              value={this.variable.metric.metric_id}
              readonly
            />
          </bk-form-item>
          <bk-form-item
            error-display-type='normal'
            label={this.$t('可选维度')}
            property='options'
            required
          >
            <bk-select
              clearable={false}
              selected-style='checkbox'
              value={this.variable.options}
              multiple
              onChange={this.handleDimensionChange}
            >
              <bk-option
                id='all'
                disabled={this.checkboxDisabled('all')}
                name='- ALL -'
              />
              {this.variable.dimensionList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  disabled={this.checkboxDisabled(item.id)}
                  name={item.name}
                />
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            label={this.$t('默认值')}
            property='defaultValue'
          >
            <bk-select
              clearable={false}
              value={this.variable.defaultValue}
              collapse-tag
              display-tag
              multiple
              onChange={this.handleValueChange}
            >
              {this.variable.dimensionOptionsMap.map(item => (
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
