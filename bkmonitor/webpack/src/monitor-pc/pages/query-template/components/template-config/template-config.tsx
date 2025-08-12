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

import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctions } from 'monitor-api/modules/grafana';

import ExpressionPanel from '../expression-panel/expression-panel';
import QueryPanel from '../query-panel/query-panel';
import {
  type IFunctionOptionsItem,
  type IScenarioItem,
  type IVariablesItem,
  TConfigType,
  TVariableType,
} from '../type/query-config';

import './template-config.scss';

@Component
export default class TemplateConfig extends tsc<object> {
  scenarioList: IScenarioItem[] = [];

  variablesList: IVariablesItem[] = [
    {
      name: 'var1',
      type: TVariableType.METHOD,
    },
    {
      name: 'var2',
      type: TVariableType.DIMENSION,
    },
    {
      name: 'var3',
      type: TVariableType.FUNCTION,
    },
  ];

  metricFunctions: IFunctionOptionsItem[] = [];

  configs = [
    {
      type: TConfigType.QUERY_CONFIG,
    },
    {
      type: TConfigType.EXPRESSION_CONFIG,
    },
  ];

  created() {
    this.handleGetMetricFunctions();
  }

  handleCreateVariable(val: IVariablesItem) {
    if (this.variablesList.find(item => item.name === val.name)) {
      return;
    }
    this.variablesList.push(val);
  }

  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
    console.log(this.metricFunctions);
  }

  handleAdd(index: number) {
    this.configs.splice(index, 0, {
      type: TConfigType.QUERY_CONFIG,
    });
  }
  handleDelete(index: number) {
    this.configs.splice(index, 1);
  }

  render() {
    return (
      <div class='template-config-wrap-component'>
        <div class='template-config-title'>{this.$t('模板配置')}</div>
        <div class='template-config-content'>
          {this.configs.map((item, index) =>
            item.type === TConfigType.QUERY_CONFIG ? (
              <QueryPanel
                key={index}
                hasAdd={index === this.configs.length - 2}
                hasDelete={this.configs.length >= 3}
                metricFunctions={this.metricFunctions}
                variables={this.variablesList}
                onAdd={() => this.handleAdd(index)}
                onCreateVariable={this.handleCreateVariable}
                onDelete={() => this.handleDelete(index)}
              />
            ) : (
              <ExpressionPanel key={index} />
            )
          )}
        </div>
      </div>
    );
  }
}
