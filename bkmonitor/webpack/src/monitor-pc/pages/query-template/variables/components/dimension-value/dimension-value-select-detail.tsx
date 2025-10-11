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

import { fetchMetricDimensionValueList } from '../../../service';

import type { DimensionValueVariableModel } from '../../index';

interface DimensionValueSelectProps {
  variable: DimensionValueVariableModel;
}

/** 维度值变量已选值详情 */
@Component
export default class DimensionValueSelectDetail extends tsc<DimensionValueSelectProps> {
  @Prop({ type: Object, required: true }) variable!: DimensionValueVariableModel;

  valueList = [];

  get valueMap() {
    return this.variable.data.value.map(
      item => this.valueList.find(i => i.value === item) || { value: item, label: item }
    );
  }

  mounted() {
    this.getValueList();
  }

  async getValueList() {
    if (!this.variable.metric) return;
    const data = await fetchMetricDimensionValueList(this.variable.related_tag, {
      data_source_label: this.variable.metric.data_source_label,
      data_type_label: this.variable.metric.data_type_label,
      result_table_id: this.variable.metric.result_table_id,
      metric_field: this.variable.metric.metric_field,
    }).catch(() => []);
    this.valueList = data;
  }

  render() {
    return (
      <div class='tag-list'>
        {this.valueMap.length
          ? this.valueMap.map(item => (
              <div
                key={item.value}
                class='tag-item'
              >
                {item.label}
              </div>
            ))
          : '--'}
      </div>
    );
  }
}
