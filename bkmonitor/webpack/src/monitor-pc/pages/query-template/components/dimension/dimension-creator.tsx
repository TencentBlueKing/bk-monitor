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

import SelectWrap from '../utils/select-wrap';

import type { IDimensionOptionsItem, IVariablesItem } from '../type/query-config';

import './dimension-creator.scss';

interface IProps {
  options?: IDimensionOptionsItem[];
  showLabel?: boolean;
  showVariables?: boolean;
  variables?: IVariablesItem[];
}

@Component
export default class DimensionCreator extends tsc<IProps> {
  /* 是否展示左侧标签 */
  @Prop({ default: true }) showLabel: boolean;
  /* 变量列表 */
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  /* 可选项列表 */
  @Prop({ default: () => [] }) options: IDimensionOptionsItem[];
  /* 是否展示变量 */
  @Prop({ default: false }) showVariables: boolean;

  showSelect = false;
  popClickHide = true;

  handleOpenChange(v) {
    this.showSelect = v;
  }

  render() {
    return (
      <div class='template-dimension-creator-component'>
        {this.showLabel && <div class='dimension-label'>{this.$slots?.label || this.$t('聚合维度')}</div>}
        <SelectWrap
          expanded={this.showSelect}
          minWidth={408}
          needPop={true}
          popClickHide={this.popClickHide}
          onOpenChange={this.handleOpenChange}
        >
          <div class='tags-wrap'>
            <div class='tags-item'>
              <span>xasdfas</span>
              <span class='icon-monitor icon-mc-close' />
            </div>
          </div>
          <div
            class='template-dimension-creator-component-options-popover'
            slot='popover'
          >
            asdfasdfasdf
          </div>
        </SelectWrap>
      </div>
    );
  }
}
