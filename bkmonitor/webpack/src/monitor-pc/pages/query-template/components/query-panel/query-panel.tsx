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

import QueryConfigCreator from '../query-config/query-config-creator';

import type { AggCondition, AggFunction } from '../../typings';
import type { IVariableModel, MetricDetailV2, QueryConfig } from '../../typings';
import type { VariableModelType } from '../../variables';
import type { IGetMetricListData, IGetMetricListParams } from '../metric/components/types';
import type { IFunctionOptionsItem } from '../type/query-config';

import './query-panel.scss';

interface IProps {
  hasAdd?: boolean;
  hasDelete?: boolean;
  hasVariableOperate?: boolean;
  metricFunctions?: IFunctionOptionsItem[];
  queryConfig?: QueryConfig;
  variables?: VariableModelType[];
  getMetricList: (params: IGetMetricListParams) => Promise<IGetMetricListData>;
  onAdd?: () => void;
  onChangeCondition?: (val: AggCondition[]) => void;
  onChangeDimension?: (val: string[]) => void;
  onChangeFunction?: (val: AggFunction[]) => void;
  onChangeInterval?: (val: number | string) => void;
  onChangeMethod?: (val: string) => void;
  onCreateVariable?: (val: IVariableModel) => void;
  onDelete?: () => void;
  onSelectMetric?: (metric: MetricDetailV2) => void;
}
export const QueryPanelEmits = [
  'createVariable',
  'add',
  'delete',
  'selectMetric',
  'changeMethod',
  'changeDimension',
  'changeFunction',
  'changeInterval',
  'changeCondition',
];

@Component
export default class QueryPanel extends tsc<IProps> {
  @Prop({ default: () => [] }) variables: VariableModelType[];
  @Prop({ default: () => [] }) metricFunctions: IFunctionOptionsItem[];
  @Prop({ default: false }) hasDelete: boolean;
  @Prop({ default: false }) hasAdd: boolean;
  @Prop({ default: () => null }) queryConfig: QueryConfig;
  @Prop({ required: true, type: Function }) getMetricList: (
    params: IGetMetricListParams
  ) => Promise<IGetMetricListData>;
  @Prop({ default: false }) hasVariableOperate: boolean;
  handleCreateVariable(val: IVariableModel) {
    this.$emit('createVariable', val);
  }

  handleAdd() {
    this.$emit('add');
  }

  handleDelete() {
    this.$emit('delete');
  }

  handleSelectMetric(metric) {
    this.$emit('selectMetric', metric);
  }

  handleChangeMethod(val: string) {
    this.$emit('changeMethod', val);
  }
  handleDimensionChange(val: string[]) {
    this.$emit('changeDimension', val);
  }
  handleChangeFunction(val: AggFunction[]) {
    this.$emit('changeFunction', val);
  }
  handleChangeInterval(val: number | string) {
    this.$emit('changeInterval', val);
  }
  handleChangeCondition(val: AggCondition[]) {
    this.$emit('changeCondition', val);
  }

  render() {
    return (
      <div class='template-query-panel-component'>
        <QueryConfigCreator
          getMetricList={this.getMetricList}
          metricFunctions={this.metricFunctions}
          queryConfig={this.queryConfig}
          variables={this.variables}
          onChangeCondition={this.handleChangeCondition}
          onChangeDimension={this.handleDimensionChange}
          onChangeFunction={this.handleChangeFunction}
          onChangeInterval={this.handleChangeInterval}
          onChangeMethod={this.handleChangeMethod}
          onCreateVariable={this.handleCreateVariable}
          onSelectMetric={this.handleSelectMetric}
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
