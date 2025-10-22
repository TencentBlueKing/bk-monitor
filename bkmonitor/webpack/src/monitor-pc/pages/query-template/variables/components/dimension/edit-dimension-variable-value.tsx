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

import EditVariableValue from '../common-form/edit-variable-value';

import type { DimensionVariableModel } from '../../index';

interface DimensionValueEvents {
  onBlur: () => void;
  onFocus: () => void;
  onValueChange: (value: string[]) => void;
}

interface DimensionValueProps {
  showLabel?: boolean;
  variable: DimensionVariableModel;
}

@Component
export default class EditDimensionVariableValue extends tsc<DimensionValueProps, DimensionValueEvents> {
  @Prop({ type: Object, required: true }) variable!: DimensionVariableModel;
  @Prop({ default: true }) showLabel!: boolean;

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

  render() {
    return (
      <EditVariableValue
        data={this.variable.data}
        showLabel={this.showLabel}
      >
        <bk-select
          clearable={false}
          value={this.variable.data.value}
          collapse-tag
          display-tag
          multiple
          searchable
          onChange={this.handleValueChange}
          onToggle={this.handleSelectToggle}
        >
          {this.variable.dimensionOptionsMap.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              name={item.name}
            />
          ))}
        </bk-select>
      </EditVariableValue>
    );
  }
}
