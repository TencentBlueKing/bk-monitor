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

import VariableValueDetail from 'monitor-pc/pages/query-template/variables/components/variable-panel/variable-value-detail';

import DetectionAlgorithmsGroup from '../detection-algorithms-group/detection-algorithms-group';

import type { TemplateDetail } from './typing';
import type { VariableModelType } from 'monitor-pc/pages/query-template/variables';

import './template-form-detail.scss';
interface TemplateFormDetailProps {
  data: TemplateDetail;
  metricFunctions: any[];
  variablesList: VariableModelType[];
}

@Component
export default class TemplateFormDetail extends tsc<TemplateFormDetailProps> {
  /** 表单数据 */
  @Prop({ default: () => ({}) }) data: TemplateDetail;
  /** 变量列表 */
  @Prop({ default: () => [] }) variablesList: VariableModelType[];
  /** 函数列表 */
  @Prop({ default: () => [] }) metricFunctions!: any[];

  /** 监控指标 */
  get monitorData() {
    if (this.data?.query_template?.alias) {
      return `${this.data.query_template.alias}(${this.data.query_template.name})`;
    }
    return this.data?.query_template?.name;
  }

  formItem(label, content) {
    return (
      <div class='form-item'>
        <div class='form-item-label'>{label}</div>
        <div class='content'>{content}</div>
      </div>
    );
  }

  render() {
    return (
      <div class='template-form-detail'>
        {this.formItem(
          this.$t('监控数据'),
          <span
            class='monitor-data'
            v-bk-tooltips={{
              content: this.data?.query_template?.description,
              disabled: !this.data?.query_template?.description,
            }}
          >
            {this.monitorData}
          </span>
        )}
        {this.formItem(this.$t('模板类型'), <span>{this.data?.system.alias}</span>)}
        {this.formItem(
          this.$t('检测算法'),
          <DetectionAlgorithmsGroup
            algorithms={this.data?.algorithms}
            connector={this.data?.detect.connector}
          />
        )}
        {this.formItem(
          this.$t('判断条件'),
          <i18n
            class='detect-text'
            path='在{0}个周期内累计满足{1}次检测算法'
          >
            <span class='value'>{this.data?.detect?.config.trigger_check_window}</span>
            <span class='value'>{this.data?.detect?.config.trigger_count}</span>
          </i18n>
        )}
        {this.formItem(
          this.$t('告警组'),
          <div class='tag-list'>
            {this.data?.user_group_list.map(item => (
              <div
                key={item.id}
                class='tag-item'
              >
                {item.name}
              </div>
            ))}
          </div>
        )}
        {this.variablesList.map(item =>
          this.formItem(
            <span
              class='tooltips-label'
              v-bk-tooltips={{
                width: 320,
                content: `${this.$t('变量名')}: ${item.variableName}<br />${this.$t('变量别名')}: ${item.alias}<br />${this.$t('变量描述')}: ${item.description}`,
                allowHTML: true,
              }}
            >
              {item.alias || item.name}
            </span>,
            <VariableValueDetail
              key={item.id}
              metricFunctions={this.metricFunctions}
              variable={item}
            />
          )
        )}
        {this.formItem(
          this.$t('自动下发'),
          <bk-switcher
            theme='primary'
            value={this.data?.is_auto_apply}
            disabled
          />
        )}
      </div>
    );
  }
}
