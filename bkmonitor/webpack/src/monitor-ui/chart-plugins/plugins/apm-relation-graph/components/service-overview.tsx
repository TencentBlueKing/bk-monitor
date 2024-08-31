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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import deepmerge from 'deepmerge';
import { deepClone, random } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import TextOverflowCopy from 'monitor-pc/pages/monitor-k8s/components/text-overflow-copy/text-overflow-copy';
import { echartsConnect, echartsDisconnect } from 'monitor-ui/monitor-echarts/utils';

import { PanelModel } from '../../../../chart-plugins/typings';
import ChartWrapper from '../../../components/chart-wrapper';
import BarAlarmChart from './bar-alarm-chart';
import { alarmBarChartDataTransform, EDataType } from './utils';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './service-overview.scss';

type ServiceOverviewProps = {
  data: Record<string, any>;
  show?: boolean;
  appName?: string;
  serviceName?: string;
  timeRange?: TimeRangeType;
};

const apiFn = (api: string) => {
  return {
    apiModule: api?.split('.')[0] || '',
    apiFunc: api?.split('.')[1] || '',
  };
};

@Component
export default class ServiceOverview extends tsc<ServiceOverviewProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: String, default: '' }) appName: string;
  @Prop({ type: String, default: '' }) serviceName: string;
  @Prop() data: Record<string, any>;
  @Prop({ type: Array, default: () => [] }) timeRange: TimeRangeType;

  tabs = Object.freeze([
    { id: 'service', name: window.i18n.tc('服务') },
    { id: 'log', name: window.i18n.tc('日志') },
    // { id: 'event', name: window.i18n.tc('事件') },
  ]);

  tabActive = 'service';
  panels = {};
  panel: PanelModel[] = [];
  /* 服务详情 */
  serviceDetail = {
    name: '',
    others: [],
    loading: false,
  };
  /* 告警数据 */
  serviceAlert = {
    loading: false,
    getData: null,
  };
  /* 服务tab栏数据 */
  serviceTabData = {
    getApdexData: null,
    panels: [],
    dashboardId: random(8),
  };
  /* 日志tab栏数据 */
  logTabData = {
    panels: [],
  };

  @Watch('show', { immediate: true })
  handleWatchShow(show: boolean) {
    if (show) {
      this.initPanel();
    } else {
      echartsDisconnect(this.serviceTabData.dashboardId);
    }
  }

  initPanel() {
    console.log(this.data);
    this.getServiceDetail();
    this.getServiceAlert();
    this.getServiceTabData();
    this.getLogTabData();
    /* this.panel = this.panels[this.tabActive].map(
      panel =>
        new PanelModel({
          ...panel,
          options: deepmerge(
            deepClone(panel.options),
            {
              logHeader: this.tabActive === 'log',
              time_series: {
                echart_option: {
                  grid: {
                    bottom: 0,
                  },
                  xAxis: {
                    splitNumber: 3,
                  },
                },
              },
              legend: {
                displayMode: this.tabActive === 'log' ? 'hidden' : 'list',
              },
            },
            { arrayMerge: (_, newArr) => newArr }
          ),
        })
    ); */
  }

  /**
   * @description 获取服务详情
   */
  async getServiceDetail() {
    try {
      this.serviceDetail.loading = true;
      const apiItem = apiFn(this.data.service_detail.targets[0].api);
      const result = await (this as any).$api[apiItem.apiModule]
        [apiItem.apiFunc]({
          app_name: this.appName,
          service_name: this.serviceName,
        })
        .catch(() => []);
      this.serviceDetail.name = result[0].value;
      this.serviceDetail.others = result.slice(1);
      this.serviceDetail.loading = false;
    } catch (e) {
      console.error(e);
    }
  }

  /**
   * @description 获取服务告警数据
   */
  async getServiceAlert() {
    try {
      this.serviceAlert.getData = async setData => {
        const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
        const apiItem = apiFn(this.data.service_alert.targets[0].api);
        const data = await (this as any).$api[apiItem.apiModule]
          [apiItem.apiFunc]({
            app_name: this.appName,
            service_name: this.serviceName,
            data_type: EDataType.Alert,
            start_time: startTime,
            end_time: endTime,
          })
          .catch(() => ({ series: [] }));
        const result = alarmBarChartDataTransform(EDataType.Alert, data.series);
        setData(result);
      };
    } catch (e) {
      console.error(e);
    }
  }

  /**
   * @description 获取服务tab栏数据
   */
  async getServiceTabData() {
    try {
      const apdexPanel = this.data.service_tabs_service.panels.find(item => item.type === 'apdex-chart');
      if (apdexPanel) {
        this.serviceTabData.getApdexData = async setData => {
          const apiItem = apiFn(apdexPanel.targets[0].api);
          const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
          const data = await (this as any).$api[apiItem.apiModule]
            [apiItem.apiFunc]({
              app_name: this.appName,
              data_type: EDataType.Apdex,
              service_name: this.serviceName,
              start_time: startTime,
              end_time: endTime,
            })
            .catch(() => ({ series: [] }));
          const result = alarmBarChartDataTransform(EDataType.Apdex, data.series);
          setData(result);
        };
      }
      this.serviceTabData.panels = this.data.service_tabs_service.panels
        .filter(panel => panel.type !== 'apdex-chart')
        .map(
          panel =>
            new PanelModel({
              ...panel,
              dashboardId: this.serviceTabData.dashboardId,
              type: 'apm-timeseries-chart',
            })
        );
      echartsConnect(this.serviceTabData.dashboardId);
    } catch (e) {
      console.error(e);
    }
  }

  /**
   * @description 获取日志tab栏数据
   */
  async getLogTabData() {
    try {
      this.logTabData.panels = this.data.service_tabs_log.panels.map(
        panel =>
          new PanelModel({
            ...panel,
            options: {
              ...(panel?.options || {}),
              related_log_chart: {
                ...(panel?.options?.related_log_chart || {}),
                isSimpleChart: true,
              },
            },
          })
      );
    } catch (e) {
      console.error(e);
    }
  }

  handleChartCheck(check: boolean, panel: PanelModel) {
    panel.updateChecked(check);
  }

  handleCollectChart(panel: PanelModel) {
    console.log(panel);
  }

  handleTabClick(id: string) {
    this.tabActive = id;
  }

  renderCharts() {
    if (this.tabActive === 'service') {
      return (
        <div class='tabs-content'>
          <BarAlarmChart
            style='margin-bottom: 16px'
            activeItemHeight={32}
            dataType={EDataType.Apdex}
            getData={this.serviceTabData.getApdexData}
            isAdaption={true}
            itemHeight={24}
            showHeader={true}
            showXAxis={true}
          >
            <div slot='title'>Apdex</div>
          </BarAlarmChart>
          {this.serviceTabData.panels.map(panel => (
            <div
              key={panel.id}
              class={['chart-item', `${this.tabActive}-type`]}
            >
              <ChartWrapper
                customMenuList={['more', 'fullscreen', 'explore', 'set', 'area', 'drill-down', 'relate-alert']}
                panel={panel}
                onChartCheck={v => this.handleChartCheck(v, panel)}
                onCollectChart={() => this.handleCollectChart(panel)}
              />
            </div>
          ))}
        </div>
      );
    }
    if (this.tabActive === 'log') {
      return (
        <div class='tabs-content'>
          {this.logTabData.panels.map(panel => (
            <div
              key={panel.id}
              class={['chart-item', `${this.tabActive}-type`]}
            >
              <ChartWrapper
                customMenuList={['more', 'fullscreen', 'explore', 'set', 'area', 'drill-down', 'relate-alert']}
                panel={panel}
                onChartCheck={v => this.handleChartCheck(v, panel)}
                onCollectChart={() => this.handleCollectChart(panel)}
              />
            </div>
          ))}
        </div>
      );
    }
  }

  render() {
    return (
      <div class='service-overview-comp'>
        <div class='panel-form'>
          <div class='form-header'>
            <div class='form-title'>
              <i class='icon-monitor icon-wangye' />
              <div
                class='title max-w-170'
                title={this.serviceDetail.name}
              >
                <TextOverflowCopy val={this.serviceDetail.name} />
              </div>
              {/* <div class='status'>{this.$t('正常')}</div> */}
            </div>
            <div class='setting-btn'>
              {this.$t('服务配置')}
              <i class='icon-monitor icon-shezhi' />
            </div>
          </div>
          <div class='form-content'>
            {this.serviceDetail.others.map(item => (
              <div
                key={item.name}
                class='form-item'
              >
                <div class='item-label'>{item.name}:</div>
                <div class='item-value'>{item.value}</div>
              </div>
            ))}
          </div>
        </div>
        <div class='alarm-wrap'>
          <BarAlarmChart
            activeItemHeight={32}
            dataType={EDataType.Alert}
            getData={this.serviceAlert.getData}
            isAdaption={true}
            itemHeight={24}
            showHeader={true}
            showXAxis={true}
          >
            <div slot='title'>告警</div>
            <div slot='more'>更多</div>
          </BarAlarmChart>

          <div class='alarm-category-tabs'>
            <div class='tabs-header-list'>
              {this.tabs.map(item => (
                <div
                  key={item.id}
                  class={{
                    'tab-item': true,
                    active: this.tabActive === item.id,
                  }}
                  onClick={() => {
                    this.handleTabClick(item.id);
                  }}
                >
                  {item.name}
                </div>
              ))}
            </div>
            {this.renderCharts()}
            {/* <div class='tabs-content'>
              {this.tabActive === 'service' && (
                <BarAlarmChart
                  style='margin-bottom: 16px'
                  activeItemHeight={32}
                  isAdaption={true}
                  itemHeight={24}
                  showHeader={true}
                  showXAxis={true}
                >
                  <div slot='title'>Apdex</div>
                </BarAlarmChart>
              )}
              {this.panel.map(panel => (
                <div
                  key={panel.id}
                  class={['chart-item', `${this.tabActive}-type`]}
                >
                  <ChartWrapper
                    customMenuList={['more', 'fullscreen', 'explore', 'set', 'area', 'drill-down', 'relate-alert']}
                    panel={panel}
                    onChartCheck={v => this.handleChartCheck(v, panel)}
                    onCollectChart={() => this.handleCollectChart(panel)}
                  />
                </div>
              ))}
            </div> */}
          </div>
        </div>
      </div>
    );
  }
}
