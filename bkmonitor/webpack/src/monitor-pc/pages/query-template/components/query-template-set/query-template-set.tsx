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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { variableRegex } from '../../variables/template/utils';
import VariablesManage from '../../variables/variables-manage/variables-manage';
import BasicInfoCreate from '../basic-info/basic-info-create';
import ExpressionPanel from '../expression-panel/expression-panel';
import QueryPanel from '../query-panel/query-panel';

import type {
  AggCondition,
  AggFunction,
  Expression,
  IBasicInfoData,
  IVariableModel,
  MetricDetailV2,
  QueryConfig,
} from '../../typings';
import type { VariableModelType } from '../../variables';

import './query-template-set.scss';

interface QueryConfigSetEvents {
  onAddQueryConfig: (index: number) => void;
  onBasicInfoChange: (basicInfo: IBasicInfoData) => void;
  onCancel: () => void;
  onChangeCondition?: (val: { index: number; value: AggCondition[] }) => void;
  onChangeDimension?: (val: { index: number; value: string[] }) => void;
  onChangeExpression?: (val: string) => void;
  onChangeExpressionFunction?: (val: AggFunction[]) => void;
  onChangeFunction?: (val: { index: number; value: AggFunction[] }) => void;
  onChangeInterval?: (val: { index: number; value: number | string }) => void;
  onChangeMethod?: (val: { index: number; value: string }) => void;
  onCreateVariable: (variable: IVariableModel) => void;
  onDeleteQueryConfig: (index: number) => void;
  onSelectMetric: (index: number, metric: MetricDetailV2) => void;
  onStepChange: (step: number) => void;

  onVariablesChange: (variablesList: VariableModelType[]) => void;
}

interface QueryConfigSetProps {
  basicInfo: IBasicInfoData;
  expressionConfig: Expression;
  metricFunctions: any[];
  queryConfigs: QueryConfig[];
  variablesList: VariableModelType[];
}

@Component
export default class QueryTemplateSet extends tsc<QueryConfigSetProps, QueryConfigSetEvents> {
  @Prop() basicInfo: IBasicInfoData;
  @Prop({ default: () => [] }) queryConfigs: QueryConfig[];
  @Prop() expressionConfig: Expression;
  @Prop({ default: () => [] }) metricFunctions: any[];
  @Prop({ default: () => [] }) variablesList: VariableModelType[];
  @Ref('basicInfo') basicInfoRef: BasicInfoCreate;
  @Ref('createContainer') createContainerRef: HTMLDivElement;
  @Ref('variablesManage') variablesManageRef: VariablesManage;

  resizeObserver = null;
  isSticky = false;

  get getNextStepDisabled() {
    return !this.queryConfigs.some(item => item.metricDetail);
  }

  /** 获取已使用的变量列表 */
  get useVariables() {
    const queryConfigsVariables = JSON.stringify(this.queryConfigs).match(variableRegex) || [];
    const expressionVariables = JSON.stringify(this.expressionConfig).match(variableRegex) || [];
    return [...queryConfigsVariables, ...expressionVariables];
  }

  @Emit('basicInfoChange')
  handleBasicInfoChange(basicInfo: IBasicInfoData) {
    return basicInfo;
  }

  @Emit('addQueryConfig')
  handleAddQueryConfig(index: number) {
    return index;
  }

  @Emit('deleteQueryConfig')
  handleDeleteQueryConfig(index: number) {
    return index;
  }

  @Emit('createVariable')
  handleCreateVariable(variable: IVariableModel) {
    return variable;
  }

  @Emit('variablesChange')
  handleVariablesChange(variablesList: VariableModelType[]) {
    return variablesList;
  }

  handleSelectMetric(index: number, metric: MetricDetailV2) {
    this.$emit('selectMetric', index, metric);
  }

  handleChangeMethod(val: string, index: number) {
    this.$emit('changeMethod', { value: val, index });
  }
  handleDimensionChange(val: string[], index: number) {
    this.$emit('changeDimension', { value: val, index });
  }
  handleChangeFunction(val: AggFunction[], index: number) {
    this.$emit('changeFunction', { value: val, index });
  }
  handleChangeInterval(val: number | string, index: number) {
    this.$emit('changeInterval', { value: val, index });
  }
  handleChangeExpression(val: string) {
    this.$emit('changeExpression', val);
  }
  handleChangeExpressionFunction(val: AggFunction[]) {
    this.$emit('changeExpressionFunction', val);
  }
  handleChangeCondition(val: AggCondition[], index: number) {
    this.$emit('changeCondition', { value: val, index });
  }

  handleNextStep() {
    Promise.all([this.variablesManageRef.validateVariable(), this.basicInfoRef.validate()]).then(() => {
      this.$emit('stepChange', 2);
    });
  }

  @Emit('cancel')
  handleCancel() {}

  observerCreateConfigResize() {
    this.resizeObserver = new ResizeObserver(() => {
      this.isSticky = this.createContainerRef.scrollHeight > this.createContainerRef.clientHeight;
    });
    this.resizeObserver.observe(this.createContainerRef);
  }

  mounted() {
    this.observerCreateConfigResize();
  }

  beforeDestroy() {
    this.resizeObserver.unobserve(this.createContainerRef);
  }

  render() {
    return (
      <div class='query-template-set'>
        <div
          ref='createContainer'
          class='left-create-container'
        >
          <div class='create-content-wrap'>
            <BasicInfoCreate
              ref='basicInfo'
              formData={this.basicInfo}
              onChange={this.handleBasicInfoChange}
            />
            <div class='template-config-wrap-component panel'>
              <div class='template-config-title'>{this.$t('模板配置')}</div>
              <div class='template-config-content'>
                {this.queryConfigs.map((item, index) => (
                  <QueryPanel
                    key={item.key}
                    hasAdd={index === this.queryConfigs.length - 1}
                    hasDelete={this.queryConfigs.length >= 2}
                    metricFunctions={this.metricFunctions}
                    queryConfig={item}
                    variables={this.variablesList}
                    onAdd={() => this.handleAddQueryConfig(index)}
                    onChangeCondition={val => this.handleChangeCondition(val, index)}
                    onChangeDimension={val => this.handleDimensionChange(val, index)}
                    onChangeFunction={val => this.handleChangeFunction(val, index)}
                    onChangeInterval={val => this.handleChangeInterval(val, index)}
                    onChangeMethod={val => this.handleChangeMethod(val, index)}
                    onCreateVariable={this.handleCreateVariable}
                    onDelete={() => this.handleDeleteQueryConfig(index)}
                    onSelectMetric={metric => this.handleSelectMetric(index, metric)}
                  />
                ))}
                <ExpressionPanel
                  expressionConfig={this.expressionConfig}
                  metricFunctions={this.metricFunctions}
                  variables={this.variablesList}
                  onChangeExpression={val => this.handleChangeExpression(val)}
                  onChangeFunction={val => this.handleChangeExpressionFunction(val)}
                  onCreateVariable={this.handleCreateVariable}
                />
              </div>
            </div>
          </div>

          <div class={['submit-btns', { sticky: this.isSticky }]}>
            <bk-button
              disabled={this.getNextStepDisabled}
              theme='primary'
              onClick={this.handleNextStep}
            >
              {this.$t('下一步')}
            </bk-button>
            <bk-button
              theme='default'
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </div>
        {/* 右侧内容 */}
        <VariablesManage
          ref='variablesManage'
          metricFunctions={this.metricFunctions}
          scene='create'
          useVariables={this.useVariables}
          variablesList={this.variablesList}
          onChange={this.handleVariablesChange}
        />
      </div>
    );
  }
}
