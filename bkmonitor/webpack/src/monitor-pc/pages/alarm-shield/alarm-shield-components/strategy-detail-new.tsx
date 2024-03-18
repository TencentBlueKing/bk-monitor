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

import { methodMap } from '../../../mixins/strategyMapMixin';

import './strategy-detail-new.scss';

const { i18n } = window;

interface IStrategyDetailNewProps {
  strategyData: any;
  detects: any;
}

@Component({
  name: 'StrategyDetailNew'
})
export default class StrategyDetailNew extends tsc<IStrategyDetailNewProps> {
  @Prop({ type: Object, default: () => ({}) }) strategyData: any;
  @Prop({ type: Object, default: () => ({}) }) detects: any;

  levelMap = ['', i18n.t('致命'), i18n.t('预警'), i18n.t('提醒')];

  render() {
    return (
      <div class='alarm-shield-stratrgy-detail'>
        {this.strategyData?.items?.[0].query_configs.map(item => (
          <div class='stratrgy-detail'>
            {item.data_type_label === 'event'
              ? this.getEventContent(item)
              : item.data_type_label === 'alert'
                ? this.getAlertContent(item)
                : this.getTimeSeriesContent(item)}
          </div>
        ))}
      </div>
    );
  }
  // 事件
  getEventContent(queryConfig) {
    return (
      <div class='item-content'>
        <div class='column-item'>
          <div class='column-label'> {this.$t('事件名称')} : </div>
          <div class='column-content item-font'>{this.strategyData.name}</div>
        </div>
        <div class='column-item'>
          <div class='column-label'> {this.$t('告警级别')} : </div>
          <div class='column-content item-font'>{this.levelMap[this.strategyData.detects?.[0].level || 0]}</div>
        </div>
        {queryConfig.data_type_label === 'event' && queryConfig.data_source_label === 'custom' ? (
          <div class='column-item column-item-agg-condition'>
            <div class='column-label column-target'> {this.$t('监控条件')} : </div>
            <div class='column-agg-condition'>
              {queryConfig.agg_condition.map((item, index) => [
                item.condition && <div class='column-agg-dimension mb-2'>{item.condition}</div>,
                <div
                  class='column-agg-dimension mb-2'
                  key={index}
                >{`${item.key} ${methodMap[item.method]} ${item.value.join(',')}`}</div>
              ])}
            </div>
          </div>
        ) : undefined}
      </div>
    );
  }
  // 监控采集
  getTimeSeriesContent(queryConfig) {
    return (
      <div class='item-content'>
        {[
          queryConfig.data_type_label === 'log'
            ? [
                <div class='column-item'>
                  <div class='column-label'> {this.$t('索引集')} : </div>
                  <div class='column-center'>{queryConfig.metric_field}</div>
                </div>,
                <div class='column-item'>
                  <div class='column-label'> {this.$t('检索语句')} : </div>
                  <div class='column-center'>{queryConfig.keywords_query_string}</div>
                </div>
              ]
            : undefined,
          [
            <div class='column-item'>
              <div class='column-label'> {this.$t('指标名称')} : </div>
              <div class='column-content'>
                <div class='item-center'>{queryConfig.metric_field}</div>
                <div class='item-source'>{queryConfig.metric_description}</div>
              </div>
            </div>,
            <div class='column-item'>
              <div class='column-label'> {this.$t('计算公式')} : </div>
              <div class='column-content item-font'>
                {queryConfig.agg_method === 'REAL_TIME' ? (
                  <div class='item-font'> {this.$t('实时')} </div>
                ) : (
                  <div class='item-font'>{queryConfig.agg_method}</div>
                )}
              </div>
            </div>
          ],
          queryConfig.agg_method !== 'REAL_TIME' ? (
            <div class='column-item'>
              <div class='column-label'> {this.$t('汇聚周期')} : </div>
              <div class='column-content'>
                {queryConfig.agg_interval / 60} {this.$t('分钟')}{' '}
              </div>
            </div>
          ) : undefined,
          queryConfig.agg_method !== 'REAL_TIME' ? (
            <div class='column-item column-item-agg-condition'>
              <div class='column-label column-target'> {this.$t('维度')} : </div>
              <div class='column-agg-condition'>
                {queryConfig.agg_dimension.map((item, index) => (
                  <div
                    class='column-agg-dimension mb-2'
                    key={index}
                  >
                    {item}
                  </div>
                ))}
              </div>
            </div>
          ) : undefined,
          <div class='column-item column-item-agg-condition'>
            <div class='column-label column-target'> {this.$t('监控条件')} : </div>
            <div class='column-agg-condition'>
              {queryConfig.agg_condition.map((item, index) => [
                item.condition && <div class='column-agg-dimension mb-2'>{item.condition}</div>,
                <div
                  class='column-agg-dimension mb-2'
                  key={index}
                >{`${item.key} ${methodMap[item.method]} ${item.value.join(',')}`}</div>
              ])}
            </div>
          </div>
        ]}
      </div>
    );
  }
  // 告警
  getAlertContent(queryConfig) {
    return (
      <div class='item-content'>
        <div class='column-item'>
          <div class='column-label'> {this.$t('告警名称')} : </div>
          <div class='column-content item-font'>{this.strategyData.name}</div>
        </div>
        {this.strategyData?.detects?.length && (
          <div class='column-item'>
            <div class='column-label'> {this.$t('告警级别')} : </div>
            <div class='column-content item-font'>{this.levelMap[this.strategyData.detects[0].level]}</div>
          </div>
        )}
        <div class='column-item column-item-agg-condition'>
          <div class='column-label column-target'> {this.$t('监控条件')} : </div>
          <div class='column-agg-condition'>
            {queryConfig.agg_condition.map((item, index) => [
              item.condition && <div class='column-agg-dimension mb-2'>{item.condition}</div>,
              <div
                class='column-agg-dimension mb-2'
                key={index}
              >{`${item.key} ${methodMap[item.method]} ${item.value.join(',')}`}</div>
            ])}
          </div>
        </div>
      </div>
    );
  }
}
