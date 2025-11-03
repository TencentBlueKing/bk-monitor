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

import type { IVariableData } from '../../../typings/variables';

import './edit-variable-value.scss';

interface EditVariableValueProps {
  data: IVariableData;
}

@Component
export default class EditVariableValue extends tsc<EditVariableValueProps> {
  @Prop({ type: Object, required: true }) data!: IVariableData;

  get editVariableLabelTooltips() {
    return [
      { label: this.$tc('变量名'), value: this.data.variableName },
      { label: this.$tc('变量别名'), value: this.data.alias },
      { label: this.$tc('变量描述'), value: this.data.description },
    ];
  }

  render() {
    return (
      <div class='edit-variable-value'>
        <div class='variable-value'>
          <bk-popover
            width={320}
            placement='top'
          >
            <div class='variable-value-label'>
              <span>{this.data.alias || this.data.variableName}</span>
            </div>

            <ul slot='content'>
              {this.editVariableLabelTooltips.map(item => (
                <li key={item.label}>
                  <span class='label'>{item.label}：</span>
                  <span class='value'>{item.value}</span>
                </li>
              ))}
            </ul>
          </bk-popover>

          <div class='variable-value-input'>{this.$slots.default}</div>
        </div>
      </div>
    );
  }
}
