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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import QueryChart from '../../query-chart/query-chart';
import VariablesManage from '../../variables/variables-manage/variables-manage';
import QueryConfigViewer from '../query-config-viewer/query-config-viewer';

import type { Expression } from '../../typings/expression';
import type { QueryConfig } from '../../typings/query-config';
import type { VariableModelType } from '../../variables';

import './query-template-view.scss';

interface QueryTemplateViewEvents {
  onCancel: () => void;
  onStepChange: (index: number) => void;
  onSubmit: () => void;
  onVariablesChange: (variablesList: VariableModelType[]) => void;
}

interface QueryTemplateViewProps {
  chartTitle: string;
  expressionConfig: Expression;
  metricFunctions: any[];
  queryConfigs: QueryConfig[];
  variablesList: VariableModelType[];
}

@Component
export default class QueryTemplateView extends tsc<QueryTemplateViewProps, QueryTemplateViewEvents> {
  @Prop({ default: () => [] }) metricFunctions: any[];
  @Prop({ default: () => [] }) variablesList: VariableModelType[];
  @Prop({ default: () => [] }) queryConfigs: QueryConfig[];
  @Prop({ default: () => {} }) expressionConfig: Expression;
  @Prop({ default: () => '' }) chartTitle: string;

  @Emit('variablesChange')
  handleVariablesListChange(variablesList: VariableModelType[]) {
    return variablesList;
  }

  @Emit('submit')
  handleSubmit() {}

  @Emit('stepChange')
  handlePrevStep() {
    return 1;
  }

  @Emit('cancel')
  handleCancel() {}

  render() {
    return (
      <div class='query-template-view'>
        <div class='query-template-view-content'>
          <div class='left-view-container'>
            <div class='content-wrap panel'>
              {this.variablesList.length > 0 && (
                <div class='edit-variable-wrap'>
                  <VariablesManage
                    metricFunctions={this.metricFunctions}
                    scene='edit'
                    variablesList={this.variablesList}
                    onChange={this.handleVariablesListChange}
                  />
                </div>
              )}
              <QueryChart
                expressionConfig={this.expressionConfig}
                queryConfigs={this.queryConfigs}
                title={this.chartTitle}
              />
            </div>
          </div>
          <div class='template-view'>
            <div class='template-view-header'>
              <span class='header-title'>{this.$t('模板配置预览')}</span>
            </div>
            <QueryConfigViewer
              class='template-config-view'
              expressionConfig={this.expressionConfig}
              queryConfigs={this.queryConfigs}
              variablesList={this.variablesList}
            />
          </div>
        </div>
        <div class='submit-btns'>
          <bk-button
            theme='primary'
            onClick={this.handleSubmit}
          >
            {this.$t('提交')}
          </bk-button>
          <bk-button onClick={this.handlePrevStep}>{this.$t('上一步')}</bk-button>
          <bk-button
            theme='default'
            onClick={this.handleCancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </div>
    );
  }
}
