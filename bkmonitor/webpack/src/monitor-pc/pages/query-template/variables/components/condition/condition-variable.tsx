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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import ConditionCreator from '../../../components/condition/condition-creator';
import VariableCommonForm from '../common-form/variable-common-form';

import type { ConditionVariableModel } from '../../index';

import './condition-variable.scss';
interface ConditionVariableEvents {
  onDataChange: (data: ConditionVariableModel) => void;
}
interface ConditionVariableProps {
  data: ConditionVariableModel;
}

@Component
export default class ConditionVariable extends tsc<ConditionVariableProps, ConditionVariableEvents> {
  @Prop({ type: Object, required: true }) data!: ConditionVariableModel;

  get nullMetricGroupByList() {
    if (!this.data.metric) return null;
    return this.data.metric.isNullMetric
      ? this.data.metric.agg_dimension.map(item => ({ id: item, name: item, disabled: false }))
      : null;
  }

  get dimensionList() {
    const list = this.nullMetricGroupByList || [];
    return [{ id: 'all', name: '- ALL -', disabled: false }, { id: 1, name: 1 }, ...list];
  }

  handleValueChange(value) {
    this.handleDataChange({
      ...this.data,
      value,
    });
  }

  checkboxDisabled(dimension) {
    const isAllDisabled =
      dimension.id === 'all' && this.data.dimensionOption.length && !this.data.dimensionOption.includes('all');
    const isOtherDisabled = dimension.id !== 'all' && this.data.dimensionOption.includes('all');
    return isAllDisabled || isOtherDisabled;
  }

  handleDimensionChange(value) {
    this.handleDataChange({
      ...this.data,
      dimensionOption: value,
    });
  }

  @Debounce(200)
  handleDataChange(data: ConditionVariableModel) {
    this.$emit('dataChange', data);
  }

  render() {
    return (
      <div class='condition-variable'>
        <VariableCommonForm
          data={this.data}
          onDataChange={this.handleDataChange}
        >
          <bk-form-item
            label={this.$t('关联指标')}
            property='value'
          >
            <bk-input
              value={this.data?.metric?.related_name}
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
              value={this.data.dimensionOption}
              multiple
              onChange={this.handleDimensionChange}
            >
              {this.dimensionList.map(item => (
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
            <ConditionCreator showLabel={false} />
          </bk-form-item>
        </VariableCommonForm>
      </div>
    );
  }
}
