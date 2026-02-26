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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getMetricListV2 } from 'monitor-api/modules/strategies';

import VariablesManage from '../../variables/variables-manage/variables-manage';
import BasicInfo from '../basic-info/basic-info';
import ExpressionPanel from '../expression-panel/expression-panel';
import ExpressionPanelLoading from '../expression-panel/expression-panel-loading';
import QueryPanel from '../query-panel/query-panel';
import QueryPanelLoading from '../query-panel/query-panel-loading';

import type {
  AggCondition,
  AggFunction,
  BasicInfoData,
  Expression,
  IVariableModel,
  MetricDetailV2,
  QueryConfig,
} from '../../typings';
import type { VariableModelType } from '../../variables';
import type { IGetMetricListData, IGetMetricListParams } from '../metric/components/types';

import './query-template-set.scss';

interface QueryConfigSetEvents {
  onAddQueryConfig: (index: number) => void;
  onBasicInfoChange: (basicInfo: BasicInfoData) => void;
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
  onDeleteVariable: (index: number) => void;
  onSelectMetric: (index: number, metric: MetricDetailV2) => void;
  onStepChange: (step: number) => void;
  onVariableAliasChange: (val: string, index: number) => void;
  onVariableDefaultValueChange: (val: any, index: number) => void;
  onVariableDescChange: (val: string, index: number) => void;
  onVariableNameChange: (val: string, index: number) => void;
  onVariableOptionsChange: (val: string[], index: number) => void;
  onVariableValueChange: (val: any, index: number) => void;
}

interface QueryConfigSetProps {
  basicInfo: BasicInfoData;
  expressionConfig: Expression;
  loading?: boolean;
  metricFunctions: any[];
  queryConfigs: QueryConfig[];
  scene?: 'create' | 'edit';
  useVariables?: string[];
  variablesList: VariableModelType[];
}

@Component
export default class QueryTemplateSet extends tsc<QueryConfigSetProps, QueryConfigSetEvents> {
  @Prop() basicInfo: BasicInfoData;
  @Prop({ type: String, default: 'create' }) readonly scene: 'create' | 'edit';
  @Prop({ default: () => [] }) queryConfigs: QueryConfig[];
  @Prop() expressionConfig: Expression;
  @Prop({ default: () => [] }) metricFunctions: any[];
  @Prop({ default: () => [] }) useVariables: string[];
  @Prop({ default: () => [] }) variablesList: VariableModelType[];
  @Prop({ default: false }) loading: boolean;
  @Ref('basicInfo') basicInfoRef: BasicInfo;
  @Ref('createContainer') createContainerRef: HTMLDivElement;
  @Ref('variablesManage') variablesManageRef: VariablesManage;

  resizeObserver = null;
  isSticky = false;
  abortController: AbortController | null = null;

  get getNextStepDisabled() {
    return !this.queryConfigs.some(item => item.metricDetail);
  }

  @Emit('basicInfoChange')
  handleBasicInfoChange(basicInfo: BasicInfoData) {
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
  async getMetricList(params: IGetMetricListParams) {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    this.abortController = new AbortController();
    const data = await getMetricListV2<IGetMetricListData>(
      {
        conditions: [
          {
            key: 'query',
            value: '',
          },
        ],
        data_type_label: 'time_series',
        tag: '',
        page: 1,
        page_size: 20,
        ...params,
      },
      {
        signal: this.abortController.signal,
      }
    );
    return data;
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

  handleVariableNameChange(val: string, index: number) {
    this.$emit('variableNameChange', val, index);
  }

  handleVariableAliasChange(val: string, index: number) {
    this.$emit('variableAliasChange', val, index);
  }

  handleVariableDescChange(val: string, index: number) {
    this.$emit('variableDescChange', val, index);
  }

  handleVariableOptionsChange(val: string[], index: number) {
    this.$emit('variableOptionsChange', val, index);
  }

  handleVariableDefaultValueChange(val: any, index: number) {
    this.$emit('variableDefaultValueChange', val, index);
  }

  handleVariableValueChange(val: any, index: number) {
    this.$emit('variableValueChange', val, index);
  }

  handleDeleteVariable(index: number) {
    this.$emit('deleteVariable', index);
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
          class={['left-create-container', { sticky: this.isSticky }]}
        >
          <div class='create-content-wrap'>
            <BasicInfo
              ref='basicInfo'
              formData={this.basicInfo}
              scene={this.scene}
              onChange={this.handleBasicInfoChange}
            />
            <div class='template-config-wrap-component panel'>
              <div class='template-config-title'>{this.$t('模板配置')}</div>
              {this.loading ? (
                <div class='template-config-content'>
                  <QueryPanelLoading />
                  <ExpressionPanelLoading class='mt-12' />
                </div>
              ) : (
                <div class='template-config-content'>
                  {this.queryConfigs.map((item, index) => (
                    <QueryPanel
                      key={item.key}
                      getMetricList={this.getMetricList}
                      hasAdd={index === this.queryConfigs.length - 1}
                      hasDelete={this.queryConfigs.length >= 2}
                      hasVariableOperate={true}
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
              )}
            </div>
          </div>

          <div class='submit-btns'>
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
          onAliasChange={this.handleVariableAliasChange}
          onDefaultValueChange={this.handleVariableDefaultValueChange}
          onDelete={this.handleDeleteVariable}
          onDescChange={this.handleVariableDescChange}
          onNameChange={this.handleVariableNameChange}
          onOptionsChange={this.handleVariableOptionsChange}
          onValueChange={this.handleVariableValueChange}
        />
      </div>
    );
  }
}
