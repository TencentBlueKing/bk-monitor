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

import './edit-box.scss';

interface IProps {
  data: {
    key: string;
    method: string;
    value: string[];
  };
}

interface IEmit {
  onChange: (value: IProps['data']) => void;
}

@Component
export default class FilterConditions extends tsc<IProps, IEmit> {
  @Prop({ type: Object, required: true }) readonly data: IProps['data'];

  isFocused = false;

  handleToggle(value: boolean) {
    this.isFocused = value;
  }

  handleChange(value: string[]) {
    this.$emit('change', {
      ...this.data,
      value,
    });
  }

  render() {
    return (
      <div class={{ 'filter-conditions-commonly-used-edit-box': true, 'is-focused': this.isFocused }}>
        <div class='conditions-key'>{this.data.key}</div>
        <div class='conditions-option'>=</div>
        <div class='conditions-value'>
          <bk-select
            allow-create={true}
            clearable={true}
            display-tag={true}
            multiple={true}
            placeholder=' '
            searchable={true}
            trigger='focus'
            value={this.data.value}
            onChange={this.handleChange}
            onToggle={this.handleToggle}
          />
        </div>
      </div>
    );
  }
}
