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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctions } from 'monitor-api/modules/grafana';
import { retrieveQueryTemplate } from 'monitor-api/modules/model';

import { TemplateDetailTabEnum } from '../constants';
import { getRetrieveQueryTemplateQueryConfigs } from '../service';
import { type VariableModelType, getCreateVariableParams, getVariableModel } from '../variables';
import ConfigPanel from './components/config-panel';
import ConsumePanel from './components/consume-panel';
import MonitorTab from '@/components/monitor-tab/monitor-tab';

import type { BasicInfoData, QueryConfig } from '../typings';
import type { TemplateDetailTabEnumType } from '../typings/constants';

import './template-detail.scss';

interface TemplateDetailEmits {
  /** 模板详情 - 侧弹抽屉展示状态改变回调 */
  onSliderShowChange: (isShow: boolean) => void;
}
interface TemplateDetailProps {
  /** 模板详情 - 侧弹抽屉显示时默认激活的 tab 面板 */
  defaultActiveTab?: TemplateDetailTabEnumType;
  id: number | string;
  /** 模板详情 - 侧弹抽屉是否可见 */
  sliderShow: boolean;
}
@Component
export default class TemplateDetail extends tsc<TemplateDetailProps, TemplateDetailEmits> {
  @Prop({ type: [String, Number], required: true }) id: number | string;
  /** 模板详情 - 侧弹抽屉显示时默认激活的 tab 面板 */
  @Prop({ type: String, default: TemplateDetailTabEnum.CONFIG }) defaultActiveTab?: TemplateDetailTabEnumType;
  /** 模板详情 - 侧弹抽屉是否可见 */
  @Prop({ type: Boolean, default: false }) sliderShow: boolean;

  /** 当前激活的 tab 面板 */
  activeTab: TemplateDetailTabEnumType = TemplateDetailTabEnum.CONFIG;

  basicInfoData: BasicInfoData = {
    name: '',
    description: '',
    space_scope: [],
  };

  queryConfigs: QueryConfig[] = [];

  variablesList: VariableModelType[] = [];

  metricFunctions = [];

  mounted() {
    this.handleGetMetricFunctions();
  }

  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }

  @Watch('sliderShow')
  sliderShowChange() {
    if (!this.sliderShow) return;
    this.activeTab = this.defaultActiveTab || TemplateDetailTabEnum.CONFIG;
    this.getQueryTemplateDetail();
  }

  /**
   * @description 获取查询模板详情
   */
  async getQueryTemplateDetail() {
    const data = await retrieveQueryTemplate(this.id).catch(() => null);
    if (data) {
      this.queryConfigs = await getRetrieveQueryTemplateQueryConfigs(data.query_configs);
      this.basicInfoData = {
        name: data.name,
        description: data.description,
        space_scope: data.space_scope,
      };
      this.variablesList = data.variables.map(item =>
        getVariableModel(
          getCreateVariableParams(
            item,
            this.queryConfigs.map(queryConfig => queryConfig.metricDetail)
          )
        )
      );
    }
  }

  /**
   * @description 模板详情 - 侧弹抽屉展示状态改变回调
   */
  @Emit('sliderShowChange')
  handleSliderShowChange(isShow: boolean) {
    return isShow;
  }

  handleTabChange(tab: TemplateDetailTabEnumType) {
    this.activeTab = tab;
  }
  render() {
    return (
      <bk-sideslider
        width='60vw'
        ext-cls='template-detail'
        is-show={this.sliderShow}
        quick-close={true}
        show-mask={true}
        transfer={true}
        {...{ on: { 'update:isShow': this.handleSliderShowChange } }}
      >
        <div
          class='template-detail-header'
          slot='header'
        >
          <div class='header-info'>
            <div class='header-info-title'>
              <span>{this.$t('模板详情')}</span>
            </div>
            <div class='header-info-division' />
            <div class='header-info-template-name'>
              <span>模板名称占位AA</span>
            </div>
          </div>
          <div class='header-operations'>
            <bk-button
              theme='primary'
              title={this.$t('编辑')}
              onClick={this.handleSliderShowChange.bind(this, false)}
            >
              {this.$t('编辑')}
            </bk-button>
            <bk-button
              title={this.$t('删除')}
              onClick={this.handleSliderShowChange.bind(this, false)}
            >
              {this.$t('删除')}
            </bk-button>
          </div>
        </div>
        <div
          class='template-detail-content'
          slot='content'
        >
          <MonitorTab
            class='template-detail-tabs'
            // @ts-ignore
            active={this.activeTab}
            on-tab-change={v => this.handleTabChange(v)}
          >
            <bk-tab-panel
              label={this.$t('配置信息')}
              name={TemplateDetailTabEnum.CONFIG}
              renderDirective='if'
            >
              <ConfigPanel
                metricFunctions={this.metricFunctions}
                variables={this.variablesList}
              />
            </bk-tab-panel>
            <bk-tab-panel
              label={`${this.$t('消费场景')} (6)`}
              name={TemplateDetailTabEnum.CONSUME}
              renderDirective='if'
            >
              <ConsumePanel />
            </bk-tab-panel>
          </MonitorTab>
        </div>
      </bk-sideslider>
    );
  }
}
