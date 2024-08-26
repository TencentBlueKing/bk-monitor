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

import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils';

import { PanelModel } from '../../../../chart-plugins/typings';
import ChartWrapper from '../../../components/chart-wrapper';
import BarAlarmChart from './bar-alarm-chart';

import './service-overview.scss';

type ServiceOverviewProps = {
  data: Record<string, any>;
};

@Component
export default class ServiceOverview extends tsc<ServiceOverviewProps> {
  @Prop() data: Record<string, any>;

  tabs = Object.freeze([
    { id: 'service', name: window.i18n.tc('服务') },
    { id: 'log', name: window.i18n.tc('日志') },
    { id: 'event', name: window.i18n.tc('事件') },
  ]);

  panels = {
    service: [
      {
        id: 4,
        title: '错误数',
        type: 'apm-timeseries-chart',
        gridPos: {
          x: 8,
          y: 4,
          w: 8,
          h: 6,
        },
        targets: [
          {
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
            datasource: 'time_series',
            alias: null,
            data: {
              type: 'range',
              stack: 'all',
              expression: 'A',
              query_configs: [
                {
                  data_source_label: 'custom',
                  data_type_label: 'time_series',
                  table: '2_bkapm_metric_kimmy_test.__default__',
                  metrics: [
                    {
                      field: 'bk_apm_count',
                      method: 'SUM',
                      alias: 'A',
                    },
                  ],
                  group_by: ['http_status_code'],
                  display: true,
                  where: [
                    {
                      key: 'status_code',
                      method: 'eq',
                      value: ['2'],
                      condition: 'and',
                    },
                    {
                      key: 'http_status_code',
                      method: 'neq',
                      value: [''],
                      condition: 'and',
                    },
                  ],
                  interval_unit: 's',
                  time_field: 'time',
                  filter_dict: {},
                  functions: [],
                },
              ],
            },
          },
          {
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
            datasource: 'time_series',
            alias: null,
            data: {
              type: 'range',
              stack: 'all',
              expression: 'A',
              query_configs: [
                {
                  data_source_label: 'custom',
                  data_type_label: 'time_series',
                  table: '2_bkapm_metric_kimmy_test.__default__',
                  metrics: [
                    {
                      field: 'bk_apm_count',
                      method: 'SUM',
                      alias: 'A',
                    },
                  ],
                  group_by: ['rpc_grpc_status_code'],
                  display: true,
                  where: [
                    {
                      key: 'status_code',
                      method: 'eq',
                      value: ['2'],
                      condition: 'and',
                    },
                    {
                      key: 'rpc_grpc_status_code',
                      method: 'neq',
                      value: [''],
                      condition: 'and',
                    },
                  ],
                  interval_unit: 's',
                  time_field: 'time',
                  filter_dict: {},
                  functions: [],
                },
              ],
            },
          },
          {
            data_type: 'time_series',
            api: 'grafana.graphUnifyQuery',
            datasource: 'time_series',
            alias: 'OTHER',
            data: {
              type: 'range',
              stack: 'all',
              expression: 'A',
              query_configs: [
                {
                  data_source_label: 'custom',
                  data_type_label: 'time_series',
                  table: '2_bkapm_metric_kimmy_test.__default__',
                  metrics: [
                    {
                      field: 'bk_apm_count',
                      method: 'SUM',
                      alias: 'A',
                    },
                  ],
                  group_by: [],
                  display: true,
                  where: [
                    {
                      key: 'status_code',
                      method: 'eq',
                      value: ['2'],
                      condition: 'and',
                    },
                    {
                      key: 'http_status_code',
                      method: 'eq',
                      value: [''],
                      condition: 'and',
                    },
                    {
                      key: 'rpc_grpc_status_code',
                      method: 'eq',
                      value: [''],
                      condition: 'and',
                    },
                  ],
                  interval_unit: 's',
                  time_field: 'time',
                  filter_dict: {},
                  functions: [],
                },
              ],
            },
          },
        ],
        options: {
          time_series: {
            type: 'bar',
          },
        },
      },
    ],
    log: [],
    event: [
      {
        type: 'alarm-event-chart',
      },
    ],
  };

  tabActive = 'service';

  panel: PanelModel[] = [];

  initPanel() {
    this.panel = this.panels[this.tabActive].map(
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
    );
  }

  mounted() {
    this.initPanel();
  }

  handleChartCheck(check: boolean, panel: PanelModel) {
    panel.updateChecked(check);
  }

  handleCollectChart(panel: PanelModel) {
    console.log(panel);
  }

  handleTabClick(id: string) {
    this.tabActive = id;
    this.initPanel();
  }

  render() {
    return (
      <div class='service-overview-comp'>
        <div class='panel-form'>
          <div class='form-header'>
            <div class='form-title'>
              <i class='icon-monitor icon-wangye' />
              <div class='title'>Mongo</div>
              <div class='status'>{this.$t('正常')}</div>
            </div>
            <div class='setting-btn'>
              {this.$t('服务配置')}
              <i class='icon-monitor icon-shezhi' />
            </div>
          </div>
          <div class='form-content'>
            <div class='form-item'>
              <div class='item-label'>{this.$t('类型')}:</div>
              <div class='item-value'>Mysql</div>
            </div>
            <div class='form-item'>
              <div class='item-label'>{this.$t('语言')}:</div>
              <div class='item-value'>php</div>
            </div>
            <div class='form-item'>
              <div class='item-label'>{this.$t('实例数')}:</div>
              <div class='item-value'>2</div>
            </div>
            <div class='form-item'>
              <div class='item-label'>{this.$t('三方应用')}:</div>
              <div class='item-value'>
                memcache
                <i class='icon-monitor icon-fenxiang' />
              </div>
            </div>
          </div>
        </div>
        <div class='alarm-wrap'>
          <BarAlarmChart
            activeItemHeight={32}
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
            <div class='tabs-content'>
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
            </div>
          </div>
        </div>
      </div>
    );
  }
}
