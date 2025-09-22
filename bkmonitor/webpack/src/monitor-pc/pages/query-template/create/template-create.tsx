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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctions } from 'monitor-api/modules/grafana';
import { createQueryTemplate } from 'monitor-api/modules/model';

import QueryTemplateSet from '../components/query-template-set/query-template-set';
import QueryTemplateView from '../components/query-template-view/query-template-view';
import { VariableTypeEnum } from '../constants';
import { createQueryTemplateQueryConfigsParams } from '../service/metric';
import {
  type AggCondition,
  type AggFunction,
  type BasicInfoData,
  type IVariableModel,
  Expression,
  MetricDetailV2,
  QueryConfig,
} from '../typings';
import {
  type ConditionVariableModel,
  type VariableModelType,
  getVariableModel,
  getVariableSubmitParams,
} from '../variables';
import { isVariableName, variableRegex } from '../variables/template/utils';
import { LETTERS } from '@/common/constant';

import type VariablesManage from '../variables/variables-manage/variables-manage';

import './template-create.scss';

Component.registerHooks(['beforeRouteLeave']);
@Component
export default class TemplateCreate extends tsc<object> {
  @Ref() createContentWrap: HTMLDivElement;
  @Ref('queryTemplateSet') queryTemplateSetRef: QueryTemplateSet;
  @Ref() variablesManage: VariablesManage;

  scene: 'create' | 'edit' = 'create';

  title = this.$t('route-新建查询模板');

  steps = [
    { title: this.$t('模板配置'), icon: 1 },
    { title: this.$t('模板预览'), icon: 2 },
  ];

  curStep = 1;

  basicInfoData: BasicInfoData = {
    name: '',
    description: '',
    alias: '',
    space_scope: [this.$store.getters.bizId],
  };

  metricsList: MetricDetailV2[] = [];
  queryConfigs: QueryConfig[] = [new QueryConfig(null, { alias: 'a' })];
  expressionConfig = new Expression();

  metricFunctions = [];

  variablesList: VariableModelType[] = [];

  submitLoading = false;

  loading = false;

  needCheck = true;

  /** 获取已使用的变量列表 */
  get useVariables() {
    const queryConfigsVariables = JSON.stringify(this.queryConfigs).match(variableRegex) || [];
    const expressionVariables = JSON.stringify(this.expressionConfig).match(variableRegex) || [];
    return [...queryConfigsVariables, ...expressionVariables];
  }

  async beforeRouteLeave(to, _from, next) {
    if (this.needCheck) {
      const needNext = await this.handleCancel();
      next(needNext);
    } else {
      next();
    }
  }

  handleBasicInfoChange(basicInfo) {
    this.basicInfoData = basicInfo;
  }

  handleStepChange(step: number) {
    this.curStep = step;
  }

  /** 是否清除未使用变量 */
  isClearUnUsedVariable() {
    const variable = this.variablesList.find(variable => !this.useVariables.includes(variable.name));
    if (!variable) return false;
    return new Promise(resolve => {
      this.$bkInfo({
        extCls: 'strategy-config-cancel',
        title: this.$t('有未生效的变量，是否清空？'),
        okText: this.$t('是'),
        cancelText: this.$t('否'),
        confirmFn: () => {
          resolve(true);
        },
        cancelFn: () => resolve(false),
      });
    });
  }

  async handleSubmit() {
    const isClear = await this.isClearUnUsedVariable();
    const variablesList = isClear
      ? this.variablesList.filter(variable => this.useVariables.includes(variable.name))
      : this.variablesList;

    const params = {
      name: this.basicInfoData.name,
      alias: this.basicInfoData.alias,
      description: this.basicInfoData.description,
      space_scope: this.basicInfoData.space_scope,
      variables: variablesList.map(variable => getVariableSubmitParams(variable)),
      query_configs: createQueryTemplateQueryConfigsParams(this.queryConfigs),
      expression: this.expressionConfig.expression,
      functions: this.expressionConfig.functions.map(f => {
        if (isVariableName(f.id)) {
          return f.id;
        }
        return f;
      }),
    };
    this.submitLoading = true;
    const data = await createQueryTemplate(params).catch(() => false);
    this.submitLoading = false;
    this.needCheck = false;
    if (!data) return;
    this.$bkMessage({
      theme: 'success',
      message: this.$t('创建查询模板成功'),
    });
    this.$router.push({
      name: 'query-template',
    });
  }

  handleCancel() {
    return new Promise(resolve => {
      this.$bkInfo({
        extCls: 'strategy-config-cancel',
        title: this.$t('是否放弃本次操作？'),
        confirmFn: () => {
          resolve(true);
        },
        cancelFn: () => resolve(false),
      });
    });
  }

  handleBackGotoPage() {
    this.$router.push({ name: 'query-template' });
  }

  init() {
    this.curStep = 1;
    this.basicInfoData = {
      name: '',
      description: '',
      alias: '',
      space_scope: [this.$store.getters.bizId],
    };
    this.metricsList = [];
    this.queryConfigs = [new QueryConfig(null, { alias: 'a' })];
    this.variablesList = [];
    this.needCheck = true;
  }

  async created() {
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
    // 切换指标无需清空已填数据
    const queryConfig = this.queryConfigs[index];
    const oldData = {
      ...(queryConfig.metricDetail
        ? {
            agg_condition: queryConfig.agg_condition,
            agg_dimension: queryConfig.agg_dimension,
            agg_interval: queryConfig.agg_interval,
            agg_method: queryConfig.agg_method,
            functions: queryConfig.functions,
          }
        : {}),
      alias: LETTERS[index],
      metric_id: metric.metric_id,
    };

    this.queryConfigs.splice(index, 1, new QueryConfig(new MetricDetailV2(metric), oldData));
  }

  handleChangeMethod(val: { index: number; value: string }) {
    const { value, index } = val;
    this.queryConfigs[index].agg_method = value;
  }
  handleDimensionChange(val: { index: number; value: string[] }) {
    const { value, index } = val;
    this.queryConfigs[index].agg_dimension = value;
  }
  handleChangeFunction(val: { index: number; value: AggFunction[] }) {
    const { value, index } = val;
    this.queryConfigs[index].functions = value;
  }
  handleChangeInterval(val: { index: number; value: number | string }) {
    const { value, index } = val;
    this.queryConfigs[index].agg_interval = value;
  }
  handleChangeCondition(val: { index: number; value: AggCondition[] }) {
    const { value, index } = val;
    this.queryConfigs[index].agg_condition = value;
  }
  handleChangeExpression(val: string) {
    this.expressionConfig.expression = val;
  }
  handleChangeExpressionFunction(val: AggFunction[]) {
    this.expressionConfig.functions = val;
  }

  handleVariableNameChange(val: string, index: number) {
    const currVariable = this.variablesList[index];
    const oldName = currVariable.name;
    currVariable.name = val;
    if (currVariable.type === VariableTypeEnum.CONSTANTS) {
      this.expressionConfig.expression = this.expressionConfig.expression.replaceAll(oldName, val);
    } else if (currVariable.type === VariableTypeEnum.FUNCTIONS) {
      for (const queryConfig of this.queryConfigs) {
        queryConfig.functions = JSON.parse(JSON.stringify(queryConfig.functions).replaceAll(oldName, val));
      }
      this.expressionConfig.functions = JSON.parse(
        JSON.stringify(this.expressionConfig.functions).replaceAll(oldName, val)
      );
    } else {
      for (const queryConfig of this.queryConfigs) {
        switch (currVariable.type) {
          case VariableTypeEnum.METHOD: {
            queryConfig.agg_method = queryConfig.agg_method.replace(oldName, val);
            break;
          }
          case VariableTypeEnum.GROUP_BY: {
            queryConfig.agg_dimension = JSON.parse(JSON.stringify(queryConfig.agg_dimension).replace(oldName, val));
            break;
          }
          case VariableTypeEnum.CONDITIONS: {
            queryConfig.agg_condition = JSON.parse(JSON.stringify(queryConfig.agg_condition).replaceAll(oldName, val));
            break;
          }
          case VariableTypeEnum.TAG_VALUES: {
            queryConfig.agg_condition = JSON.parse(JSON.stringify(queryConfig.agg_condition).replaceAll(oldName, val));
            break;
          }
        }
      }
    }
  }

  handleVariableAliasChange(val: string, index: number) {
    this.variablesList[index].alias = val;
  }

  handleVariableDescChange(val: string, index: number) {
    this.variablesList[index].description = val;
  }

  handleVariableOptionsChange(val: string[], index: number) {
    (this.variablesList[index] as ConditionVariableModel).options = val;
  }

  handleDeleteVariable(index: number) {
    this.variablesList.splice(index, 1);
  }

  handleVariableDefaultValueChange(val: any, index: number) {
    this.variablesList[index].defaultValue = val;
  }

  handleVariableValueChange(val: any, index: number, isValueEditable?: boolean) {
    this.variablesList[index].value = val;
    if (isValueEditable) {
      this.variablesList[index].isValueEditable = true;
    }
  }

  render() {
    return (
      <div class='template-create'>
        <div class='template-create-nav'>
          <div class='template-create-nav-title'>
            <span
              class='icon-monitor icon-back-left navigation-bar-back'
              onClick={this.handleBackGotoPage}
            />
            <span class='title'>{this.title}</span>
          </div>
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
              loading={this.loading}
              metricFunctions={this.metricFunctions}
              queryConfigs={this.queryConfigs}
              scene={this.scene}
              useVariables={this.useVariables}
              variablesList={this.variablesList}
              onAddQueryConfig={this.handleAdd}
              onBasicInfoChange={this.handleBasicInfoChange}
              onCancel={this.handleBackGotoPage}
              onChangeCondition={this.handleChangeCondition}
              onChangeDimension={this.handleDimensionChange}
              onChangeExpression={this.handleChangeExpression}
              onChangeExpressionFunction={this.handleChangeExpressionFunction}
              onChangeFunction={this.handleChangeFunction}
              onChangeInterval={this.handleChangeInterval}
              onChangeMethod={this.handleChangeMethod}
              onCreateVariable={this.handleCreateVariable}
              onDeleteQueryConfig={this.handleDelete}
              onDeleteVariable={this.handleDeleteVariable}
              onSelectMetric={this.handleSelectMetric}
              onStepChange={this.handleStepChange}
              onVariableAliasChange={this.handleVariableAliasChange}
              onVariableDefaultValueChange={this.handleVariableDefaultValueChange}
              onVariableDescChange={this.handleVariableDescChange}
              onVariableNameChange={this.handleVariableNameChange}
              onVariableOptionsChange={this.handleVariableOptionsChange}
              onVariableValueChange={(val, index) => {
                this.handleVariableValueChange(val, index);
              }}
            />
          ) : (
            <QueryTemplateView
              basicInfo={this.basicInfoData}
              expressionConfig={this.expressionConfig}
              metricFunctions={this.metricFunctions}
              queryConfigs={this.queryConfigs.filter(item => !!item.metricDetail)}
              submitLoading={this.submitLoading}
              variablesList={this.variablesList}
              onCancel={this.handleBackGotoPage}
              onStepChange={this.handleStepChange}
              onSubmit={this.handleSubmit}
              onVariableValueChange={(val, index) => {
                this.handleVariableValueChange(val, index, true);
              }}
            />
          )}
        </div>
      </div>
    );
  }
}
