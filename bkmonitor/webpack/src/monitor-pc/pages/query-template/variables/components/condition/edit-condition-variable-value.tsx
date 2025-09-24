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

import ConditionCreator from '../../../components/condition/condition-creator';
import EditVariableValue from '../common-form/edit-variable-value';

import type { IConditionOptionsItem } from '../../../components/type/query-config';
import type { AggCondition, IConditionVariableModel } from '../../../typings';
import type { ConditionVariableModel } from '../../index';

import './edit-condition-variable-value.scss';
interface ConditionValueEvents {
  onBlur: () => void;
  onFocus: () => void;
  onValueChange: (value: AggCondition[]) => void;
}

interface ConditionValueProps {
  variable: ConditionVariableModel;
}

@Component
export default class EditConditionVariableValue extends tsc<ConditionValueProps, ConditionValueEvents> {
  @Prop({ type: Object, required: true }) variable!: ConditionVariableModel;

  @Emit('valueChange')
  handleValueChange(value: IConditionVariableModel['value']) {
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
      <EditVariableValue
        class='condition-value'
        data={this.variable.data}
      >
        <ConditionCreator
          hasVariableOperate={false}
          metricDetail={this.variable.metric}
          options={this.variable.dimensionOptionsMap as IConditionOptionsItem[]}
          showLabel={false}
          value={this.variable.data.value}
          onChange={this.handleValueChange}
          onPopoverShowChange={this.handleSelectToggle}
        />
      </EditVariableValue>
    );
  }
}
