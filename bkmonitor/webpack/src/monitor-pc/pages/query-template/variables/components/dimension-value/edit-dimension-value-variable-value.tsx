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

import { fetchMetricDimensionValueList } from '../../../service';
import EditVariableValue from '../common-form/edit-variable-value';

import type { DimensionValueVariableModel } from '../../index';

import './dimension-value.scss';

interface DimensionValueValueEvents {
  onBlur: () => void;
  onFocus: () => void;
  onValueChange: (value: string[]) => void;
}

interface DimensionValueValueProps {
  showLabel?: boolean;
  variable: DimensionValueVariableModel;
}

@Component
export default class EditDimensionValueVariableValue extends tsc<DimensionValueValueProps, DimensionValueValueEvents> {
  @Prop({ type: Object, required: true }) variable!: DimensionValueVariableModel;
  @Prop({ default: true }) showLabel!: boolean;

  loading = false;

  valueList = [];

  @Emit('valueChange')
  handleValueChange(value: string[]) {
    return value;
  }

  handleSelectToggle(value: boolean) {
    if (value) {
      this.$emit('focus');
    } else {
      this.$emit('blur');
    }
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
    for (const item of this.variable.value) {
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
      <EditVariableValue
        class='dimension-value'
        data={this.variable.data}
        showLabel={this.showLabel}
      >
        <bk-select
          clearable={false}
          loading={this.loading}
          value={this.variable.data.value}
          allow-create
          collapse-tag
          display-tag
          multiple
          onChange={this.handleValueChange}
          onToggle={this.handleSelectToggle}
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
      </EditVariableValue>
    );
  }
}
