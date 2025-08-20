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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctions } from 'monitor-api/modules/grafana';

import QueryTemplateSet from '../components/query-template-set/query-template-set';
import QueryTemplateView from '../components/query-template-view/query-template-view';
import {
  type AggCondition,
  type AggFunction,
  type IVariableModel,
  Expression,
  MetricDetailV2,
  QueryConfig,
} from '../typings';
import { type VariableModelType, getVariableModel } from '../variables';
import { LETTERS } from '@/common/constant';

import type { MetricDetail } from '../components/type/query-config';
import type VariablesManage from '../variables/variables-manage/variables-manage';

import './template-create.scss';

@Component
export default class TemplateCreate extends tsc<object> {
  @Ref() createContentWrap: HTMLDivElement;
  @Ref('queryTemplateSet') queryTemplateSetRef: QueryTemplateSet;
  @Ref() variablesManage: VariablesManage;

  title = this.$t('新建查询模板');

  steps = [
    { title: this.$t('模板配置'), icon: 1 },
    { title: this.$t('模板预览'), icon: 2 },
  ];

  curStep = 1;

  basicInfoData = {
    name: '',
    desc: '',
    effect: [this.$store.getters.bizId],
  };

  metricsList: MetricDetail[] = [];
  queryConfigs: QueryConfig[] = [new QueryConfig(null, { alias: 'a' })];
  expressionConfig = new Expression();

  metricFunctions = [];

  variablesList: VariableModelType[] = [];

  handleBasicInfoChange(basicInfo) {
    this.basicInfoData = basicInfo;
  }

  handleVariablesChange(variablesList: VariableModelType[]) {
    console.log(variablesList);
    this.variablesList = variablesList;
  }

  handleStepChange(step: number) {
    this.curStep = step;
  }

  handleSubmit() {}

  handleBackGotoPage() {
    this.$router.push({ name: 'query-template' });
  }

  init() {
    this.curStep = 1;
    this.basicInfoData = {
      name: 'test',
      desc: '',
      effect: [this.$store.getters.bizId],
    };
    this.metricsList = [];
    this.queryConfigs = [new QueryConfig(null, { alias: 'a' })];
    this.variablesList = [];
  }

  async activated() {
    this.init();
    this.handleGetMetricFunctions();
  }

  handleCreateVariable(val: IVariableModel) {
    if (this.variablesList.find(item => item.name === val.name)) {
      return;
    }
    this.variablesList.push(getVariableModel(val));
  }

  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }

  handleAdd(index: number) {
    this.queryConfigs.splice(
      index + 1,
      0,
      new QueryConfig(null, {
        alias: LETTERS[index + 1],
      })
    );
  }
  handleDelete(index: number) {
    this.queryConfigs.splice(index, 1);
    let i = -1;
    for (const q of this.queryConfigs) {
      i += 1;
      q.alias = LETTERS[i];
    }
  }

  handleSelectMetric(index: number, metric: MetricDetailV2) {
    this.queryConfigs.splice(index, 1, new QueryConfig(new MetricDetailV2(metric), { alias: LETTERS[index] }));
  }

  handleChangeMethod(val: { index: number; value: string }) {
    console.log(val);
    const { value, index } = val;
    this.queryConfigs[index].agg_method = value;
  }
  handleDimensionChange(val: { index: number; value: string[] }) {
    console.log(val);
    const { value, index } = val;
    this.queryConfigs[index].agg_dimension = value;
  }
  handleChangeFunction(val: { index: number; value: AggFunction[] }) {
    console.log(val);
    const { value, index } = val;
    this.queryConfigs[index].functions = value;
  }
  handleChangeInterval(val: { index: number; value: number | string }) {
    console.log(val);
    const { value, index } = val;
    this.queryConfigs[index].agg_interval = value;
  }
  handleChangeCondition(val: { index: number; value: AggCondition[] }) {
    console.log(val);
    const { value, index } = val;
    this.queryConfigs[index].agg_condition = value;
  }
  handleChangeExpression(val: string) {
    console.log(val);
    this.expressionConfig.expression = val;
  }
  handleChangeExpressionFunction(val: AggFunction[]) {
    console.log(val);
    this.expressionConfig.functions = val;
  }

  render() {
    return (
      <div class='template-create'>
        <div class='template-create-nav'>
          <span
            class='icon-monitor icon-back-left navigation-bar-back'
            onClick={() => this.handleBackGotoPage()}
          />
          <span class='title'>{this.title}</span>
          <bk-steps
            class='template-steps'
            cur-step={this.curStep}
            lineType='solid'
            steps={this.steps}
          />
        </div>
        <div class='template-create-content'>
          {this.curStep === 1 ? (
            <QueryTemplateSet
              ref='queryTemplateSet'
              basicInfo={this.basicInfoData}
              expressionConfig={this.expressionConfig}
              metricFunctions={this.metricFunctions}
              queryConfigs={this.queryConfigs}
              variablesList={this.variablesList}
              onAddQueryConfig={this.handleAdd}
              onBackGotoPage={this.handleBackGotoPage}
              onBasicInfoChange={this.handleBasicInfoChange}
              onChangeCondition={this.handleChangeCondition}
              onChangeDimension={this.handleDimensionChange}
              onChangeExpression={this.handleChangeExpression}
              onChangeExpressionFunction={this.handleChangeExpressionFunction}
              onChangeFunction={this.handleChangeFunction}
              onChangeInterval={this.handleChangeInterval}
              onChangeMethod={this.handleChangeMethod}
              onCreateVariable={this.handleCreateVariable}
              onDeleteQueryConfig={this.handleDelete}
              onSelectMetric={this.handleSelectMetric}
              onStepChange={this.handleStepChange}
              onVariablesChange={this.handleVariablesChange}
            />
          ) : (
            <QueryTemplateView
              chartTitle={this.basicInfoData.name}
              expressionConfig={this.expressionConfig}
              metricFunctions={this.metricFunctions}
              queryConfigs={this.queryConfigs}
              variablesList={this.variablesList}
              onBackGotoPage={this.handleBackGotoPage}
              onStepChange={this.handleStepChange}
              onSubmit={this.handleSubmit}
              onVariablesChange={this.handleVariablesChange}
            />
          )}
        </div>
      </div>
    );
  }
}
