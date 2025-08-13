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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type IInfo, ETabNames } from './types';

import './tab-title.scss';

interface IProps {
  active: string;
  dimensionDrillDownErr?: string;
  dimensionDrillDownLoading: boolean;
  metricRecommendationErr?: string;
  metricRecommendationLoading: boolean;
  showDimensionDrill: boolean;
  showMetricRecommendation: boolean;
  tabInfo?: ITabInfo;
}

interface ITabInfo {
  dimensionInfo: IInfo;
  indexInfo: IInfo;
}

@Component
export default class AiopsTabtitle extends tsc<IProps> {
  @Prop({ type: Object, default: () => {} }) tabInfo: ITabInfo;
  @Prop({ type: String, default: ETabNames.dimension }) active: string;
  @Prop({ type: Boolean, default: false }) metricRecommendationLoading: boolean;
  @Prop({ type: Boolean, default: false }) dimensionDrillDownLoading: boolean;
  @Prop({ type: String, default: '' }) metricRecommendationErr: boolean;
  @Prop({ type: String, default: '' }) dimensionDrillDownErr: string;
  @Prop({ type: Boolean, default: false }) showDimensionDrill: boolean;
  @Prop({ type: Boolean, default: false }) showMetricRecommendation: boolean;

  get dimensionInfo(): IInfo {
    return this.tabInfo?.dimensionInfo || {};
  }
  get indexInfo(): IInfo {
    return this.tabInfo?.indexInfo || {};
  }
  handleActive(type: string) {
    if (this.active !== type) {
      this.$emit('active-change', type);
    }
  }
  render() {
    const isExitDimensionInfo = Object.keys(this.dimensionInfo).length > 0;
    const isExitIndexInfo = Object.keys(this.indexInfo).length > 0;
    return (
      <div class='aiops-tab-title'>
        <div
          style={{ borderRightWidth: this.showMetricRecommendation ? '1px' : '0px' }}
          class={['aiops-tab-title-item', { 'aiops-tab-title-active': this.active === ETabNames.dimension }]}
          onClick={this.handleActive.bind(this, 'dimension')}
        >
          <span class='aiops-tab-title-icon'>
            <i class='aiops-tab-icon icon-monitor icon-mc-drill-down' />
          </span>
          <span class='aiops-tab-title-text'>
            <span class='aiops-tab-title-name'>{this.$t('维度下钻')}</span>
            {this.showDimensionDrill || this.dimensionDrillDownLoading ? (
              <span
                class={['aiops-tab-title-message']}
                v-bkloading={{
                  isLoading: this.dimensionDrillDownLoading,
                  theme: 'primary',
                  size: 'mini',
                  extCls: 'metric_loading',
                }}
              >
                {[
                  this.dimensionDrillDownErr ? (
                    <span
                      key='dimension-err-text'
                      class='err-text'
                    >
                      <span>
                        <i class='bk-icon icon-exclamation-circle-shape tooltips-icon' />
                        {this.$t('模型输出异常')}
                      </span>
                    </span>
                  ) : undefined,
                  <span
                    key='dimension-info-text'
                    class={[isExitDimensionInfo ? 'vis-show' : 'vis-hide']}
                  >
                    {this.$t('异常维度(组合)')}
                    <font> {this.dimensionInfo.anomaly_dimension_count}</font>
                    {isExitDimensionInfo ? ',' : ''}
                  </span>,
                  <span
                    key='dimension-count-text'
                    style='marginLeft: 6px'
                    class={[isExitDimensionInfo ? 'vis-show' : 'vis-hide']}
                  >
                    {this.$t('异常维度值')}
                    <font> {this.dimensionInfo.anomaly_dimension_value_count}</font>
                  </span>,
                ]}
              </span>
            ) : (
              <div>
                <i class='icon-monitor icon-tips tips-icon' />
                {this.$t('当前空间暂不支持该功能，如需使用请联系管理员')}
              </div>
            )}
          </span>
        </div>
        <div
          class={['aiops-tab-title-item', { 'aiops-tab-title-active': this.active === ETabNames.index }]}
          onClick={this.handleActive.bind(this, 'index')}
        >
          <span class='aiops-tab-title-icon'>
            <i class='aiops-tab-icon icon-monitor icon-mc-correlation-metrics' />
          </span>
          <span class='aiops-tab-title-text'>
            <span class='aiops-tab-title-name'>{this.$t('关联指标')}</span>
            {this.showMetricRecommendation || this.metricRecommendationLoading ? (
              <span
                class={['aiops-tab-title-message aiops-tab-title-index-message']}
                v-bkloading={{
                  isLoading: this.metricRecommendationLoading,
                  theme: 'primary',
                  size: 'mini',
                  extCls: 'metric_loading',
                }}
              >
                {this.metricRecommendationErr && (
                  <span class='err-text'>
                    <span>
                      <i class='bk-icon icon-exclamation-circle-shape tooltips-icon' />
                      {this.$t('模型输出异常')}
                    </span>
                  </span>
                )}
                <span class={[isExitIndexInfo ? 'vis-show' : 'vis-hide']}>
                  <i18n path='{0} 个指标'>
                    <font>{this.indexInfo.recommended_metric || 0} </font>
                  </i18n>
                  {isExitIndexInfo ? ',' : ''}
                </span>
                <span
                  style='marginLeft: 6px'
                  class={[isExitIndexInfo ? 'vis-show' : 'vis-hide']}
                >
                  <i18n path='{0} 个维度'>
                    <font>{this.indexInfo.recommended_metric_count || 0} </font>
                  </i18n>
                </span>
              </span>
            ) : (
              <span class='aiops-tab-title-message aiops-tab-title-index-message'>
                <i class='icon-monitor icon-tips tips-icon' />
                {this.$t('当前空间暂不支持该功能，如需使用请联系管理员')}
              </span>
            )}
          </span>
        </div>
      </div>
    );
  }
}
