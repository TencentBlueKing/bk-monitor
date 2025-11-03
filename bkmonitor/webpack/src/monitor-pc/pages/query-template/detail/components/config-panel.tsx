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

import ExploreCollapseWrapper from 'monitor-ui/chart-plugins/plugins/explore-custom-graph/components/explore-collapse-wrapper';

import QueryConfigViewer from '../../components/query-config-viewer/query-config-viewer';
import VariablesManage from '../../variables/variables-manage/variables-manage';

import './config-panel.scss';

interface ConfigPanelProps {
  templateInfo: any;
}
@Component
export default class ConfigPanel extends tsc<ConfigPanelProps> {
  @Prop({ type: Object, default: () => ({}) }) templateInfo: any;

  getSpaceScopeName() {
    if (!this.templateInfo?.space_scope?.length) {
      return this.$t('全业务可见');
    }
    const bizIdMap = this.$store.getters.bizIdMap;
    return this.templateInfo?.space_scope
      ?.map(bizId => bizIdMap.get(bizId)?.name)
      ?.filter(Boolean)
      ?.join(',');
  }

  render() {
    return (
      <div class='config-panel'>
        <div class='base-info'>
          <div class='info-header'>
            <span class='header-title'>{this.$t('基本信息')}</span>
          </div>
          <div class='info-main'>
            <div class='info-item'>
              <span class='info-item-label'>{`${this.$t('模板名称')}:`}</span>
              <span class='info-item-value'>{this.templateInfo?.name || '--'}</span>
            </div>
            <div class='info-item'>
              <span class='info-item-label'>{`${this.$t('模板别名')}:`}</span>
              <span class='info-item-value'>{this.templateInfo?.alias || '--'}</span>
            </div>
            <div class='info-item'>
              <span class='info-item-label'>{`${this.$t('生效范围')}:`}</span>
              <span class='info-item-value'>{this.getSpaceScopeName() || '--'}</span>
            </div>
            <div class='info-item'>
              <span class='info-item-label'>{`${this.$t('模板说明')}:`}</span>
              <span class='info-item-value'>{this.templateInfo?.description || '--'}</span>
            </div>
          </div>
        </div>
        <ExploreCollapseWrapper
          class='collapse-panel'
          collapseShowHeight={24}
          defaultHeight={0}
          hasResize={false}
          title={this.$t('模板配置') as string}
        >
          <QueryConfigViewer
            expressionConfig={this.templateInfo?.expressionConfig}
            queryConfigs={this.templateInfo?.queryConfigs}
          />
        </ExploreCollapseWrapper>
        <ExploreCollapseWrapper
          class='collapse-panel'
          collapseShowHeight={24}
          defaultHeight={0}
          hasResize={false}
          title={this.$t('变量列表') as string}
        >
          <VariablesManage
            metricFunctions={this.templateInfo?.metricFunctions}
            scene='detail'
            variablesList={this.templateInfo?.variables}
          />
        </ExploreCollapseWrapper>
      </div>
    );
  }
}
