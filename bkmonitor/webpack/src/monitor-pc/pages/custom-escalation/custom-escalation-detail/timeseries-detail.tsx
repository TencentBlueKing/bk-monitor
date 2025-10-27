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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorImport from '../../../components/monitor-import/monitor-import.vue';
import DimensionTabDetail from './dimension-tab-detail';
import MetricTabDetail from './metric-tab-detail';

import './timeseries-detail.scss';

@Component({
  inheritAttrs: false,
})
export default class TimeseriesDetailNew extends tsc<any, any> {
  @Prop({ default: () => [] }) unitList;
  @Prop({ default: '' }) selectedLabel;
  @Prop({ default: () => [] }) customGroups;
  @Prop({ default: 0 }) nonGroupNum;
  @Prop({ default: () => [] }) dimensions: any[];
  @Prop({ default: () => [] }) metricList: any[];

  tabs = [
    {
      title: this.$t('指标'),
      id: 'metric',
    },
    {
      title: this.$t('维度'),
      id: 'dimension',
    },
  ];
  activeTab = this.tabs[0].id;

  created() {
    this.activeTab = this.$route.params.activeTab || this.tabs[0].id;
  }

  /**
   * 计算维度数量
   */
  get dimensionNum(): number {
    return this.dimensions.length;
  }

  /**
   * 计算指标数量
   */
  get metricNum(): number {
    return this.metricList.length;
  }

  @Emit('handleExport')
  handleDownload() {}

  @Emit('handleUpload')
  handleUpload(data) {
    return data;
  }

  getCmpByActiveTab(activeTab: string) {
    const cmpMap = {
      /** 指标 */
      metric: () => (
        <MetricTabDetail
          customGroups={this.customGroups}
          metricNum={this.metricNum}
          {...{
            attrs: this.$attrs,
            on: {
              ...this.$listeners,
            },
          }}
          dimensionTable={this.dimensions}
          metricList={this.metricList}
          nonGroupNum={this.nonGroupNum}
          selectedLabel={this.selectedLabel}
          unitList={this.unitList}
        />
      ),
      /** 维度 */
      dimension: () => (
        <DimensionTabDetail
          dimensionTable={this.dimensions}
          {...{
            attrs: this.$attrs,
            on: {
              ...this.$listeners,
            },
          }}
        />
      ),
    };
    return cmpMap[activeTab]();
  }

  getCountByType(type: string) {
    const obj = {
      metric: this.metricNum,
      dimension: this.dimensionNum,
    };
    return obj[type];
  }

  render() {
    return (
      <div class='timeseries-detail-page'>
        <div class='list-header'>
          <div class='detail-information-title'>{this.$t('指标与维度')}</div>
          <div class='head'>
            <div class='tabs'>
              {this.tabs.map(({ title, id }) => (
                <span
                  key={id}
                  class={['tab', id === this.activeTab ? 'active' : '']}
                  onClick={() => (this.activeTab = id)}
                >
                  {`${title}(${this.getCountByType(id)})`}
                </span>
              ))}
            </div>
            <div class='tools'>
              <MonitorImport
                class='tool'
                base64={false}
                return-text={true}
                onChange={this.handleUpload}
              >
                <i class='icon-monitor icon-xiazai2' /> {this.$t('导入')}
              </MonitorImport>
              <span
                class='tool'
                onClick={this.handleDownload}
              >
                <i class='icon-monitor icon-shangchuan' />
                {this.$t('导出')}
              </span>
            </div>
          </div>
        </div>
        <div class='timeseries-detail-page-content'>{this.getCmpByActiveTab(this.activeTab)}</div>
      </div>
    );
  }
}
