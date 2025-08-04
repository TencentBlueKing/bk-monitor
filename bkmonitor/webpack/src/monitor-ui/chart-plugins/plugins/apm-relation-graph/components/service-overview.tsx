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

import { Component, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { topoLink } from 'monitor-api/modules/apm_topo';
import { Debounce, random } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import TextOverflowCopy from 'monitor-pc/pages/monitor-k8s/components/text-overflow-copy/text-overflow-copy';
import { echartsConnect, echartsDisconnect } from 'monitor-ui/monitor-echarts/utils';

import { PanelModel } from '../../../../chart-plugins/typings';
import ChartWrapper from '../../../components/chart-wrapper';
import BarAlarmChart from './bar-alarm-chart';
import { alarmBarChartDataTransform, EDataType } from './utils';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './service-overview.scss';

const customMenuList = ['more', 'fullscreen', 'explore', 'set', 'area', 'drill-down', 'relate-alert', 'strategy'];

type ServiceOverviewProps = {
  appName?: string;
  dashboardId?: string;
  data: Record<string, any>;
  detailIcon?: string;
  endpoint?: string;
  nodeTipsMap?: TNodeTipsMap;
  onSliceTimeRangeChange?: (timeRange: [number, number]) => void;
  serviceName?: string;
  show?: boolean;
  sliceTimeRange?: number[];
  timeRange?: TimeRangeType;
};

type TNodeTipsMap = Map<
  string,
  {
    group: string;
    name: string;
    value: string;
  }[]
>;

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
  @Prop({ type: String, default: '' }) endpoint: string;
  @Prop() data: Record<string, any>;
  @Prop({ type: Array, default: () => [] }) timeRange: TimeRangeType;
  @Prop({ type: String, default: '' }) detailIcon: string;
  @Prop({ type: Map, default: () => new Map() }) nodeTipsMap: TNodeTipsMap;
  @Prop({ type: Array, default: () => [] }) sliceTimeRange: number[];
  @Prop({ type: String, default: random(8) }) dashboardId: string;

  tabActive = 'service';
  panels = {};
  panel: PanelModel[] = [];
  detailLoading = false;
  /* 概览详情 */
  overviewDetail = {
    name: '',
    others: [],
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
  };
  /* 日志tab栏数据 */
  logTabData = {
    panels: [],
  };

  moreLink = '';

  curType: 'endpoint' | 'service' = 'service';

  @ProvideReactive('showRestore') readonly showRestore = false;
  @ProvideReactive('viewOptions') viewOptions = {
    app_name: '',
    service_name: '',
    endpoint_name: '',
  };
  @InjectReactive('refreshImmediate') readonly refreshImmediate: string;

  get tabs() {
    if (this.curType === 'endpoint') {
      return [{ id: 'service', name: window.i18n.t('服务') }];
    }
    return [
      { id: 'service', name: window.i18n.t('服务') },
      { id: 'log', name: window.i18n.t('日志') },
    ];
  }

  get name() {
    return this.curType === 'endpoint' ? this.endpoint : this.serviceName;
  }

  @Watch('serviceName')
  handleWatchServiceName(v) {
    if (this.show && v) {
      this.curType = 'service';
      this.initPanel();
    }
  }

  @Watch('endpoint')
  handleWatchEndpoint(v) {
    if (this.show) {
      this.curType = v ? 'endpoint' : 'service';
      this.initPanel();
    }
  }

  @Watch('show', { immediate: true })
  handleWatchShow(show: boolean) {
    if (show) {
      this.curType = this.endpoint ? 'endpoint' : 'service';
      this.initPanel();
    } else {
      echartsDisconnect(this.dashboardId);
      this.moreLink = '';
    }
  }
  @Watch('refreshImmediate')
  // 立刻刷新
  handleRefreshImmediateChange(v: string) {
    if (v && this.serviceName && this.appName) this.initPanel();
  }

  @Debounce(200)
  initPanel() {
    if (!this.serviceName || !this.appName) return;
    if (this.curType === 'endpoint') {
      this.tabActive = 'service';
    }
    this.viewOptions = {
      app_name: this.appName,
      service_name: this.serviceName,
      endpoint_name: this.endpoint,
    };
    this.getServiceDetail();
    this.getServiceAlert();
    this.getServiceTabData();
    this.getLogTabData();
    this.getMoreAlertLink();
  }

  /**
   * @description 获取服务详情
   */
  async getServiceDetail() {
    try {
      this.detailLoading = true;
      const typeKey = this.curType === 'endpoint' ? 'endpoint_detail' : 'service_detail';
      const apiItem = apiFn(this.data[typeKey].targets[0].api);
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const result = await (this as any).$api[apiItem.apiModule]
        [apiItem.apiFunc]({
          app_name: this.appName,
          service_name: this.serviceName,
          endpoint_name: this.curType === 'endpoint' ? this.endpoint : undefined,
          start_time: startTime,
          end_time: endTime,
        })
        .catch(() => []);
      this.overviewDetail.others = result;
    } catch (e) {
      console.error(e);
    }
    this.detailLoading = false;
  }

  /**
   * @description 获取服务告警数据
   */
  async getServiceAlert() {
    try {
      this.serviceAlert.getData = async setData => {
        const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
        const typeKey = this.curType === 'endpoint' ? 'endpoint_alert' : 'service_alert';
        const apiItem = apiFn(this.data[typeKey].targets[0].api);
        const data = await (this as any).$api[apiItem.apiModule]
          [apiItem.apiFunc]({
            app_name: this.appName,
            service_name: this.serviceName,
            data_type: EDataType.Alert,
            start_time: startTime,
            end_time: endTime,
            endpoint_name: this.curType === 'endpoint' ? this.endpoint : undefined,
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
      const typeKey = this.curType === 'endpoint' ? 'endpoint_tabs_service' : 'service_tabs_service';
      const apdexPanel = this.data[typeKey].panels.find(item => item.type === 'apdex-chart');
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
              endpoint_name: this.curType === 'endpoint' ? this.endpoint : undefined,
            })
            .catch(() => ({ series: [] }));
          const result = alarmBarChartDataTransform(EDataType.Apdex, data.series);
          setData(result);
        };
      }
      this.serviceTabData.panels = this.data[typeKey].panels
        .filter(panel => panel.type !== 'apdex-chart')
        .map(
          panel =>
            new PanelModel({
              ...panel,
              options: {
                ...(panel?.options || {}),
                time_series: {
                  ...(panel?.options?.time_series || {}),
                  hoverAllTooltips: true,
                },
                apm_time_series: {
                  ...(panel?.options?.apm_time_series || {}),
                  xAxisSplitNumber: 3,
                  disableZoom: true,
                },
              },
              dashboardId: this.dashboardId,
              type: 'apm-timeseries-chart',
              targets: panel.targets.map(t => {
                const queryConfigs = t?.data?.unify_query_param?.query_configs;
                if (queryConfigs) {
                  return {
                    ...t,
                    data: {
                      ...t.data,
                      query_configs: queryConfigs,
                    },
                  };
                }
                return t;
              }),
            })
        );
      echartsConnect(this.dashboardId);
    } catch (e) {
      console.error(e);
    }
  }

  /**
   * @description 获取日志tab栏数据
   */
  async getLogTabData() {
    try {
      if (this.curType === 'service') {
        this.logTabData.panels = this.data.service_tabs_log.panels.map(
          panel =>
            new PanelModel({
              ...panel,
              dashboardId: this.dashboardId,
              options: {
                ...(panel?.options || {}),
                related_log_chart: {
                  ...(panel?.options?.related_log_chart || {}),
                  isSimpleChart: true,
                },
              },
            })
        );
      } else {
        this.logTabData.panels = [];
      }
    } catch (e) {
      console.error(e);
    }
  }

  /* 获取更多告警链接 */
  async getMoreAlertLink() {
    try {
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const result = await topoLink(
        {
          start_time: startTime,
          end_time: endTime,
          app_name: this.appName,
          service_name: this.serviceName,
          endpoint_name: this.curType === 'endpoint' ? this.endpoint : undefined,
          link_type: 'alert',
        },
        { needMessage: false }
      ).catch(() => '');
      this.moreLink = result;
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

  handleServiceConfig() {
    const url = `service-config?app_name=${this.appName}&service_name=${this.serviceName}`;
    window.open(
      `${location.origin}${location.pathname}${location.search}#/${window.__POWERED_BY_BK_WEWEB__ ? 'apm/' : ''}${url}`,
      '_blank'
    );
  }

  handleMoreLinkClick() {
    if (this.moreLink) {
      window.open(`${location.origin}${this.moreLink}`);
    }
  }

  handleSliceTimeRangeChange(timeRange: [number, number]) {
    this.$emit('sliceTimeRangeChange', timeRange);
  }

  renderCharts() {
    if (this.tabActive === 'service') {
      let nodeTips = [];
      if (this.curType === 'endpoint') {
        nodeTips = this.nodeTipsMap.get(`${this.serviceName}___${this.endpoint}`) || [];
      } else {
        nodeTips = this.nodeTipsMap.get(this.serviceName) || [];
      }
      const tipsMap = {};
      for (const tip of nodeTips) {
        if (tipsMap[tip.group]) {
          tipsMap[tip.group].push(tip);
        } else {
          tipsMap[tip.group] = [tip];
        }
      }
      return (
        <div class='tabs-content'>
          <BarAlarmChart
            activeItemHeight={32}
            dataType={EDataType.Apdex}
            getData={this.serviceTabData.getApdexData}
            groupId={this.dashboardId}
            isAdaption={true}
            itemHeight={24}
            showHeader={true}
            showXAxis={true}
          >
            <div slot='title'>
              <span class='mr-8'>Apdex</span>
              <span
                class='bk-icon icon-info-circle tips-icon'
                v-bk-tooltips={{
                  content: '根据Apdex进行划分，划分范围为：<br>1.红：0~0.25<br>2.黄：0.25~0.75<br>3.绿：0.75以上',
                  showOnInit: false,
                  trigger: 'mouseenter',
                  placements: ['top'],
                  allowHTML: true,
                }}
              />
            </div>
          </BarAlarmChart>
          {this.serviceTabData.panels.map((panel, index) => {
            const chartMetric = panel?.options?.apm_time_series?.metric || '';
            const tipList = tipsMap?.[chartMetric] || [];
            return [
              <div
                key={`${index}__split`}
                class='split-line'
              />,
              <div
                key={panel.id}
                class={['chart-item', `${this.tabActive}-type`]}
              >
                <ChartWrapper
                  customMenuList={customMenuList}
                  panel={panel}
                  onChartCheck={v => this.handleChartCheck(v, panel)}
                  onCollectChart={() => this.handleCollectChart(panel)}
                />
                {!!tipList.length && (
                  <div class='statistics-wrap'>
                    {tipList.map(t => (
                      <div
                        key={t.name}
                        class='statistics-item'
                      >
                        <span class='item-title'>{`${t.name}：`}</span>
                        <span class='item-value'>{t.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>,
            ];
          })}
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
                customMenuList={customMenuList}
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
        {this.detailLoading ? (
          <div class='panel-skeleton'>
            <div class='skeleton-element h-24 mb-6' />
            <div class='skeleton-element h-24 mb-6' />
            <div class='skeleton-element h-24 mb-6' />
          </div>
        ) : (
          <div class='panel-form'>
            <div class='form-header'>
              {this.name ? (
                <div class='form-title'>
                  <i class={`detail-icon icon-monitor ${this.detailIcon || 'icon-wangye'}`} />
                  <div
                    class='title max-w-170'
                    title={this.name}
                  >
                    <TextOverflowCopy val={this.name} />
                  </div>
                  {/* <div class='status'>{this.$t('正常')}</div> */}
                </div>
              ) : (
                <div class='form-title'>{this.$t('暂无数据')}</div>
              )}
              {this.curType !== 'endpoint' && (
                <div
                  class='setting-btn'
                  onClick={this.handleServiceConfig}
                >
                  {this.$t('服务配置')}
                  <i class='icon-monitor icon-shezhi' />
                </div>
              )}
            </div>
            <div class='form-content'>
              {this.overviewDetail.others.map(item => (
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
        )}
        <div class='alarm-wrap'>
          <BarAlarmChart
            activeItemHeight={32}
            dataType={EDataType.Alert}
            enableSelect={true}
            getData={this.serviceAlert.getData}
            groupId={this.dashboardId}
            isAdaption={true}
            itemHeight={24}
            showHeader={true}
            showXAxis={true}
            sliceTimeRange={this.sliceTimeRange}
            onSliceTimeRangeChange={this.handleSliceTimeRangeChange}
          >
            <div slot='title'>{this.$t('告警')}</div>
            <div slot='more'>
              {!!this.moreLink && (
                <div
                  class='more-link'
                  onClick={this.handleMoreLinkClick}
                >
                  <span class='mr-4'>{this.$t('更多')}</span>
                  <span class='icon-monitor icon-fenxiang' />
                </div>
              )}
            </div>
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
          </div>
        </div>
      </div>
    );
  }
}
