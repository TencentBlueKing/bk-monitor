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

import { fetchMetricDimensionValueList } from '../../../service';
import VariableFormMixin from '../../mixins/VariableFormMixin';
import VariableCommonForm from '../common-form/variable-common-form';

import type { IVariableFormEvents } from '../../../typings/variables';
import type { DimensionValueVariableModel } from '../../index';

import './dimension-value.scss';

interface DimensionValueVariableEvents extends IVariableFormEvents {
  onDefaultValueChange: (val: string[]) => void;
  onValueChange: (val: string[]) => void;
}
interface DimensionValueVariableProps {
  variable: DimensionValueVariableModel;
}

@Component
class CreateDimensionValueVariable extends Mixins(VariableFormMixin) {
  @Prop({ type: Object, required: true }) variable!: DimensionValueVariableModel;

  @Ref() variableCommonForm!: VariableCommonForm;

  loading = false;

  valueList = [];

  defaultValueChange(defaultValue: string[]) {
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

  mounted() {
    this.getValueList();
  }

  async getValueList() {
    if (!this.variable.metric) return;
    this.loading = true;
    const data = await fetchMetricDimensionValueList(this.variable.related_tag, {
      data_source_label: this.variable.metric.data_source_label,
      data_type_label: this.variable.metric.data_type_label,
      result_table_id: this.variable.metric.result_table_id,
      metric_field: this.variable.metric.metric_field,
    }).catch(() => []);
    this.valueList = data;
    for (const item of this.variable.defaultValue) {
      if (!this.valueList.find(v => v.value === item)) {
        this.valueList.push({
          label: item,
          value: item,
          customCreate: true,
        });
      }
    }
    this.loading = false;
  }

  render() {
    return (
      <div class='dimension-value-variable dimension-value'>
        <VariableCommonForm
          ref='variableCommonForm'
          data={this.variable.data}
          onAliasChange={this.handleAliasChange}
          onDescChange={this.handleDescChange}
          onNameChange={this.handleNameChange}
        >
          <bk-form-item label={this.$t('关联指标')}>
            <bk-input
              value={this.variable.metric.metric_id}
              readonly
            />
          </bk-form-item>
          <bk-form-item
            label={this.$t('关联维度')}
            property='related_tag'
          >
            <bk-input
              value={this.variable.related_tag}
              readonly
            />
          </bk-form-item>
          <bk-form-item
            label={this.$t('默认值')}
            property='defaultValue'
          >
            <bk-select
              clearable={false}
              loading={this.loading}
              value={this.variable.defaultValue}
              allow-create
              collapse-tag
              display-tag
              multiple
              onChange={this.defaultValueChange}
            >
              {this.valueList.map(item => (
                <bk-option
                  id={item.value}
                  key={item.value}
                  style={{ display: item.customCreate ? 'none' : 'block' }}
                  name={item.label}
                />
              ))}
            </bk-select>
          </bk-form-item>
        </VariableCommonForm>
      </div>
    );
  }
}

export default tsx
  .ofType<DimensionValueVariableProps, DimensionValueVariableEvents>()
  .convert(CreateDimensionValueVariable);
