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

import QueryConfigCreator from '../query-config/query-config-creator';

import type { VariableModelType } from '../../variables';
import type { IFunctionOptionsItem, IVariablesItem } from '../type/query-config';

import './query-panel.scss';

interface IProps {
  hasAdd?: boolean;
  hasDelete?: boolean;
  metricFunctions?: IFunctionOptionsItem[];
  variables?: VariableModelType[];
  onAdd?: () => void;
  onCreateVariable?: (val: IVariablesItem) => void;
  onDelete?: () => void;
}

@Component
export default class QueryPanel extends tsc<IProps> {
  @Prop({ default: () => [] }) variables: VariableModelType[];
  @Prop({ default: () => [] }) metricFunctions: IFunctionOptionsItem[];
  @Prop({ default: false }) hasDelete: boolean;
  @Prop({ default: false }) hasAdd: boolean;

  handleCreateVariable(val: VariableModelType) {
    this.$emit('createVariable', val);
  }

  handleAdd() {
    this.$emit('add');
  }

  handleDelete() {
    this.$emit('delete');
  }

  render() {
    return (
      <div class='template-query-panel-component'>
        <QueryConfigCreator
          metricFunctions={this.metricFunctions}
          variables={this.variables}
          onCreateVariable={this.handleCreateVariable}
        />

        <div class='query-panel-operator'>
          {this.hasAdd && (
            <div
              class='add-btn'
              onClick={this.handleAdd}
            >
              <span class='icon-monitor icon-mc-add' />
            </div>
          )}
          {this.hasDelete && (
            <div
              class='del-btn'
              onClick={this.handleDelete}
            >
              <span class='icon-monitor icon-mc-delete-line' />
            </div>
          )}
        </div>
      </div>
    );
  }
}
