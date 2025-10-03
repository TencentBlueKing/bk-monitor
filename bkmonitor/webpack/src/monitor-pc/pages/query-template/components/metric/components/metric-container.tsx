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

import { type MetricSearchTagMode, MetricSearchTagModeMap, MetricSearchTags } from './types';

import type { MetricDetailV2 } from '@/pages/query-template/typings/metric';

import './metric-container.scss';

export interface IMetricSelectorContainerProps {
  loading?: boolean;
  metricList: MetricDetailV2[];
  selectedMetric: MetricDetailV2;
}
@Component
export default class MetricSelectorContainer extends tsc<IMetricSelectorContainerProps> {
  @Prop({ type: Array, default: () => [] }) metricList: MetricDetailV2[];
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: Object }) selectedMetric: MetricDetailV2;

  dataType = 'all';
  monitorScenes = 'all';
  isMultiple = false;
  localSelectedMetrics: MetricDetailV2[] = [];

  handleSelectSearchTagChange(mode: MetricSearchTagMode, activeId: string) {
    if (mode === MetricSearchTagModeMap.DataType) {
      this.dataType = activeId;
      return;
    }
    this.monitorScenes = activeId;
  }
  handleSelectMetric(metric: MetricDetailV2, v: boolean) {
    if (v) {
      this.localSelectedMetrics.push(metric);
    } else {
      this.localSelectedMetrics = this.localSelectedMetrics.filter(item => item.metric_id !== metric.metric_id);
    }
  }
  createCommonTagsItem(mode: MetricSearchTagMode, activeId = 'all') {
    return (
      <div class='common-search-tags'>
        {MetricSearchTags[mode]?.name}
        <ul class='tags-list'>
          {MetricSearchTags[mode]?.tags.map(item => (
            <bk-tag
              key={item.id}
              theme={item.id === activeId ? 'info' : ''}
              onClick={() => this.handleSelectSearchTagChange(mode, item.id)}
            >
              {item.name}
            </bk-tag>
          ))}
        </ul>
        {!this.selectedMetric && mode === MetricSearchTagModeMap.DataType && (
          <bk-checkbox
            class='multiple-checkbox'
            checked={this.isMultiple}
            disabled={this.localSelectedMetrics.length > 1}
            size='small'
            onChange={v => {
              this.isMultiple = v;
            }}
          >
            {this.$t('多选数据')}
          </bk-checkbox>
        )}
      </div>
    );
  }
  createMetricItem(metric: MetricDetailV2) {
    return (
      <div class='metric-list-item'>
        <div class='item-title'>
          {this.isMultiple && (
            <bk-checkbox
              checked={this.localSelectedMetrics.includes(metric)}
              size='small'
              onChange={(v: boolean) => this.handleSelectMetric(metric, v)}
            />
          )}
          <span
            style={{
              marginLeft: this.isMultiple ? '8px' : '0',
            }}
            class='icon-monitor icon-mc-event-chart item-title-icon'
          />
          <span class='item-title-readable-name'>{metric.readable_name}</span>
          {metric.metric_field_name && metric.metric_field_name !== metric.metric_field && (
            <span class='item-title-alias'>{metric.metric_field_name}</span>
          )}
        </div>
        <div class='item-subtitle'>
          {metric.result_table_label_name} / {metric.data_source_label} / {metric.related_name}
        </div>
      </div>
    );
  }
  render() {
    return (
      <div class='metric-selector-container'>
        <div class='selector-container-tags'>
          {this.createCommonTagsItem(MetricSearchTagModeMap.DataType, this.dataType)}
          {this.createCommonTagsItem(MetricSearchTagModeMap.MonitorScenes, this.monitorScenes)}
        </div>
        <div class='selector-container-search'>
          <bk-input
            class='search-input'
            right-icon='bk-icon icon-search'
          />
          <div class='search-refresh'>
            <span>{this.$t('搜不到想要的？')}</span>
            <i18n path='{0} 试试'>
              <bk-button
                class='refresh-btn'
                size='small'
                theme='primary'
                text
              >
                {this.$t('刷新')}
              </bk-button>
            </i18n>
          </div>
        </div>
        <div class='selector-container-metrics'>
          <div class='metric-list-wrapper'>
            <div class='metric-list'>{this.metricList.map(item => this.createMetricItem(item))}</div>
          </div>
          <div class='metric-list-tags'>dd</div>
        </div>
        <div class='selector-container-footer'>
          <div class='selected-metrics-wrapper'>
            <span class='selected-title'>{this.$t('已选：')}</span>
            {this.localSelectedMetrics?.map(item => (
              <bk-tag
                key={item.metric_id}
                closable
                onClose={() => this.handleSelectMetric(item, false)}
              >
                {item.metric_field_name || item.readable_name}
              </bk-tag>
            ))}
          </div>
          <bk-button
            class='confirm-btn'
            theme='primary'
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button>{this.$t('取消')}</bk-button>
        </div>
      </div>
    );
  }
}
