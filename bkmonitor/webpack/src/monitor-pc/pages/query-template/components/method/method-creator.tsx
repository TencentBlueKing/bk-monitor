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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SelectWrap from '../utils/select-wrap';

import type { IMethodOptionsItem, IVariablesItem } from '../type/query-config';

import './method-creator.scss';

interface IProps {
  options?: IMethodOptionsItem[];
  variables?: IVariablesItem[];
}

@Component
export default class MethodCreator extends tsc<IProps> {
  @Prop({ default: true }) showLabel: boolean;
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  @Prop({ default: () => [] }) options: IMethodOptionsItem[];

  showSelect = false;
  /* 所有可选项（包含变量） */
  allOptions: IMethodOptionsItem[] = [];

  @Watch('options', { immediate: true })
  handleWatchOptions() {
    this.getAllOptions();
  }

  @Watch('variables', { immediate: true })
  handleWatchVariables() {
    this.getAllOptions();
  }

  getAllOptions() {
    this.allOptions = [
      ...this.variables.map(item => ({
        id: item.name,
        ...item,
      })),
      ...this.options,
    ];
  }

  handleOpenChange(val: boolean) {
    this.showSelect = val;
  }

  render() {
    return (
      <div class='template-method-creator-component'>
        {this.showLabel && <div class='method-label'>{this.$slots?.label || this.$t('汇聚方法')}</div>}
        <SelectWrap
          active={this.showSelect}
          minWidth={127}
          needPop={true}
          onOpenChange={this.handleOpenChange}
        >
          <span class='method-name'>avg</span>
          <div
            class='template-method-creator-component-options-popover'
            slot='popover'
          >
            {this.allOptions.map((item, index) => (
              <div
                key={index}
                class='options-item'
              >
                {item.name}
              </div>
            ))}
          </div>
        </SelectWrap>
      </div>
    );
  }
}
