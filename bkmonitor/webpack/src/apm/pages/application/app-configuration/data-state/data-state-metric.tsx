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

import { Component, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import {
  dataSampling,
  dataViewConfig,
  noDataStrategyDisable,
  noDataStrategyEnable,
  noDataStrategyInfo,
} from 'monitor-api/modules/apm_meta';
import { copyText } from 'monitor-common/utils/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { isEnFn } from 'monitor-pc/utils/index';
import DashboardPanel from 'monitor-ui/chart-plugins/components/dashboard-panel';
import BarAlarmChart from 'monitor-ui/chart-plugins/plugins/apm-relation-graph/components/bar-alarm-chart';
// import { ApdexChart } from 'monitor-ui/chart-plugins/plugins/apdex-chart/apdex-chart';
import {
  alarmBarChartDataTransform,
  EDataType,
} from 'monitor-ui/chart-plugins/plugins/apm-relation-graph/components/utils';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import VueJsonPretty from 'vue-json-pretty';

import PanelItem from '../../../../components/panel-item/panel-item';
import { type IAppInfo, type IStrategyData, ETelemetryDataType } from '../type';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './data-state-metric.scss';
import 'vue-json-pretty/lib/styles.css';

interface IProps {
  activeTab: ETelemetryDataType;
  appInfo: IAppInfo;
}

@Component
export default class DataStatusMetric extends tsc<IProps> {
  @Prop({ default: '', type: String }) activeTab: ETelemetryDataType;
  @Prop({ type: Object, default: () => ({}) }) appInfo: IAppInfo;

  strategyLoading = false;
  tableLoading = false;
  // apdexChartPanel: PanelModel;
  /** 日志上报侧栏配置 */
  sideslider = { show: false, log: null };
  /** 无数据告警信息 */
  strategyInfo: IStrategyData = {
    id: 0, // 策略id
    name: '', // 告警名称
    alert_status: 0, // 告警状态
    alert_graph: null,
    is_enabled: true, // 启停
    notice_group: [], // 告警组
  };
  expandIndex = -1; // 采样数据展开项索引
  dashboardPanels = []; // 数据量趋势面板配置
  samplingList = []; // 采样数据
  collapseRowIndexs: number[] = []; // 采样数据记录展开收起的行
  healthMaps = { 1: this.$t('健康'), 2: this.$t('有告警') };

  getAlarmData = null;
  dataViewLoading = false;

  // 时间间隔
  @InjectReactive('timeRange') timeRange: TimeRangeType;
  /** 时区 */
  @InjectReactive('timezone') timezone: string;

  @Watch('timezone')
  handleChangeTimeZone() {
    this.getNoDataStrategyInfo();
    this.getDataView();
    this.getSamplingList();
  }
  @Watch('timeRange')
  handleChangeTimeRange() {
    this.getNoDataStrategyInfo();
  }
  /**
   * todo 目前 指标/日志/调用链/性能分析4个tab设计稿只有一个页面
   * todo 如果只有接口api不同可以提供一个computed返回不同的接口api函数
   */
  get activeApi() {
    let apiMap = {};
    switch (this.activeTab) {
      case 'metric':
        apiMap = {};
        break;
    }
    return apiMap;
  }
  /** 告警icon颜色 */
  get strategyStautsColor() {
    return this.strategyInfo.alert_status === 1 ? 'green' : 'red';
  }

  created() {
    if (this.activeTab !== ETelemetryDataType.profiling) {
      this.getNoDataStrategyInfo();
    }
    this.getDataView();
    this.getSamplingList();
  }

  /**
   * @desc 获取无数据告警信息
   */
  async getNoDataStrategyInfo() {
    this.strategyLoading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      application_id: this.appInfo.application_id,
      start_time: startTime,
      end_time: endTime,
      telemetry_data_type: this.activeTab,
    };
    const data = await noDataStrategyInfo(params).catch(() => {});
    Object.assign(this.strategyInfo, data);
    if (this.strategyInfo.alert_graph) {
      /* 告警柱状图数据 */
      this.getAlarmData = async setData => {
        const apiFn = (api: string) => {
          return {
            apiModule: api?.split('.')[0] || '',
            apiFunc: api?.split('.')[1] || '',
          };
        };
        const target = this.strategyInfo.alert_graph.targets[0];
        const apiItem = apiFn(target.api);
        const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
        const data = await (this as any).$api[apiItem.apiModule]
          [apiItem.apiFunc]({
            app_name: target.data.app_name,
            strategy_id: target.data.strategy_id,
            start_time: startTime,
            end_time: endTime,
            telemetry_data_type: this.activeTab,
          })
          .catch(() => ({ series: [] }));
        const result = alarmBarChartDataTransform(EDataType.Alert, data.series);
        setData(result);
      };
      // this.apdexChartPanel = new PanelModel(this.strategyInfo.alert_graph);
    } else {
      this.getAlarmData = null;
      // this.apdexChartPanel = null;
    }
    this.strategyLoading = false;
  }
  /**
   * @desc 获取图表数据
   */
  async getDataView() {
    this.dataViewLoading = true;
    const data = await dataViewConfig(this.appInfo.application_id, {
      telemetry_data_type: this.activeTab,
    }).catch(() => []);
    this.dashboardPanels = data.map(item => new PanelModel(item));
    this.dataViewLoading = false;
  }
  /**
   * @desc 获取采样数据
   */
  async getSamplingList() {
    this.tableLoading = true;
    const params = {
      application_id: this.appInfo.application_id,
      size: 10,
      log_type: 'trace',
      telemetry_data_type: this.activeTab,
    };
    const data = await dataSampling(this.appInfo.application_id, params).catch(() => []);
    this.collapseRowIndexs = [];
    this.samplingList = data?.map(item => {
      const date = dayjs.tz(dayjs(item.sampling_time));
      return {
        ...item,
        sampling_time: date.isValid() ? date.format('YYYY-MM-DD HH:mm:ssZ') : '--',
      };
    });
    this.tableLoading = false;
  }

  /**
   * @desc 展开全部原始日志
   * @param { Object } props 展开元素
   */
  handleClickLog(props) {
    if (this.expandIndex !== props.$index) {
      this.handleViewDetail(props.row.raw_log);
      this.expandIndex = props.$index;
    } else {
      this.expandIndex = -1;
    }
  }
  /**
   * @desc 展开/收起采样原始数据
   */
  handleCollapse(e, index) {
    e.stopPropagation();
    if (this.collapseRowIndexs.includes(index)) {
      this.collapseRowIndexs = this.collapseRowIndexs.filter(item => item !== index);
      return;
    }
    this.collapseRowIndexs.push(index);
  }
  /**
   * @desc 复制原始日志
   * @param { string } text 复制文本
   */
  handleCopyLog(text: string) {
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }
  /**
   * @desc 查看上报日志
   * @param { object } log 日志内容
   */
  handleViewDetail(log: object) {
    this.sideslider = {
      show: true,
      log,
    };
  }
  /**
   * @desc 告警跳转
   * @param { string } option
   */
  handlePageChange(option: string) {
    const { id } = this.strategyInfo;
    let hash = '';
    if (option === 'edit') {
      hash = `#/strategy-config/edit/${String(id)}`;
    } else {
      const isEn = isEnFn();
      hash = `#/event-center?queryString=${isEn ? 'strategy_id' : this.$t('策略ID')} : ${id}`;
    }

    const url = location.href.replace(location.hash, hash);
    window.open(url, '_blank');
  }
  handleRefresh() {
    this.getSamplingList();
  }
  handleClickCheckWrap(e: MouseEvent) {
    e.preventDefault();
    this.$refs.switcherRef.isLoading = true;
  }
  async handleConfirmCheck() {
    const api = this.strategyInfo.is_enabled ? noDataStrategyDisable : noDataStrategyEnable;
    this.$refs.switcherRef.isLoading = true;
    return await api({
      application_id: this.appInfo.application_id,
      telemetry_data_type: this.activeTab,
    }).then(() => {
      this.getNoDataStrategyInfo();
      this.$refs.switcherRef.isLoading = false;
      this.strategyInfo.is_enabled = !this.strategyInfo.is_enabled;
    });
  }
  handleCancelCheck() {
    this.$refs.switcherRef.isLoading = false;
  }
  render() {
    const logSlots = {
      default: props => [
        <div
          key={`${props.$index}-log`}
          class={['text-log', { 'expand-row': this.collapseRowIndexs.includes(props.$index) }]}
          onClick={() => this.handleClickLog(props)}
        >
          <span>{JSON.stringify(props.row.raw_log)}</span>
          <span
            class='collapse-btn'
            onClick={e => this.handleCollapse(e, props.$index)}
          >
            {this.collapseRowIndexs.includes(props.$index) ? this.$t('收起') : this.$t('展开全部')}
          </span>
        </div>,
      ],
    };
    const operatorSlot = {
      default: props => [
        <bk-button
          key='copy'
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleCopyLog(JSON.stringify(props.row.raw_log))}
        >
          {this.$t('复制')}
        </bk-button>,
        <bk-button
          key='view'
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleViewDetail(props.row.raw_log)}
        >
          {this.$t('查看上报数据')}
        </bk-button>,
      ],
    };

    return (
      <div class='conf-content data-status-metric-wrap'>
        {this.activeTab !== ETelemetryDataType.profiling ? (
          <div
            class='form-content mb24'
            // v-bkloading={{ isLoading: this.strategyLoading }}
          >
            {this.strategyLoading ? (
              <div class='skeleton-element w--100 h-56' />
            ) : (
              <div class='content-card'>
                <div class='content-card-left'>
                  <div class='msg-item'>
                    <span
                      class='tip-label'
                      v-bk-tooltips={{ content: this.$t('当没有收到任何数据可以进行告警通知。'), allowHTML: false }}
                    >
                      {this.$t('无数据告警')}
                    </span>
                    <bk-popconfirm
                      tippy-options={{
                        onHide: () => {
                          this.$refs.switcherRef.isLoading = false;
                          return true;
                        },
                      }}
                      title={this.strategyInfo.is_enabled ? this.$t('确认关闭？') : this.$t('确认开启？')}
                      trigger='click'
                      onCancel={() => this.handleCancelCheck()}
                      onConfirm={() => this.handleConfirmCheck()}
                    >
                      <div onMousedown={this.handleClickCheckWrap}>
                        <bk-switcher
                          ref='switcherRef'
                          size='small'
                          theme='primary'
                          value={this.strategyInfo.is_enabled}
                        />
                      </div>
                    </bk-popconfirm>
                  </div>
                </div>
                <div class='content-card-right'>
                  <div class='msg-item'>
                    <span class='label'>{this.$t('告警历史')} : </span>
                    <div class='apdex-chart-box'>
                      {this.getAlarmData ? (
                        <BarAlarmChart
                          activeItemHeight={20}
                          dataType={EDataType.Alert}
                          enableSelect={false}
                          getData={this.getAlarmData}
                          isAdaption={false}
                          itemHeight={14}
                          showHeader={false}
                          showXAxis={true}
                          showXAxisNum={2}
                          xAxisFormat={'MM-DD HH:mm'}
                        />
                      ) : (
                        <span class='no-data-text'>{this.$t('暂无数据')}</span>
                      )}
                      {/* {this.apdexChartPanel ? (
                      <ApdexChart
                        panel={this.apdexChartPanel}
                        showChartHeader={false}
                        split-number={2}
                      />
                    ) : (
                      <span>{this.$t('暂无数据')}</span>
                    )} */}
                    </div>
                  </div>
                  <span
                    class='link-btn ml-12'
                    onClick={() => this.handlePageChange('event')}
                  >
                    {this.$t('更多')}
                    <span class='icon-monitor icon-fenxiang' />
                  </span>
                  <span
                    class='link-btn ml-32'
                    onClick={() => this.handlePageChange('edit')}
                  >
                    {this.$t('编辑告警策略')}
                    <span class='icon-monitor icon-fenxiang' />
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : undefined}

        <PanelItem title={this.$t('数据量趋势')}>
          <div class='form-content'>
            {this.dataViewLoading ? (
              <div class='data-view-skeleton'>
                <div class='skeleton-element view-skeleton-item' />
                <div class='skeleton-element view-skeleton-item' />
              </div>
            ) : (
              <DashboardPanel
                id={'volumeTrend'}
                layoutMargin={[24, 24]}
                panels={this.dashboardPanels}
              />
            )}
          </div>
        </PanelItem>
        <PanelItem title={this.$t('数据采样')}>
          <span
            class='right-btn-wrap'
            slot='headerTool'
            onClick={() => this.handleRefresh()}
          >
            <i class='icon-monitor icon-shuaxin' />
            {this.$t('button-刷新')}
          </span>
          {this.tableLoading ? (
            <TableSkeleton type={3} />
          ) : (
            <bk-table
              class={'sampling-table'}
              // v-bkloading={{ isLoading: this.tableLoading }}
              data={this.samplingList}
              outer-border={false}
              row-auto-height={true}
            >
              <bk-table-column
                width='80'
                label={this.$t('序号')}
                type='index'
              />
              <bk-table-column
                label={this.$t('原始数据')}
                scopedSlots={logSlots}
              />
              {this.activeTab !== ETelemetryDataType.profiling && (
                <bk-table-column
                  width='200'
                  label={this.$t('采样时间')}
                  scopedSlots={{ default: props => props.row.sampling_time }}
                />
              )}
              <bk-table-column
                width='180'
                label={this.$t('操作')}
                scopedSlots={operatorSlot}
              />
            </bk-table>
          )}
        </PanelItem>

        <bk-sideslider
          ext-cls='origin-log-sideslider'
          isShow={this.sideslider.show}
          transfer={true}
          {...{ on: { 'update:isShow': v => (this.sideslider.show = v) } }}
          width={596}
          quick-close={true}
        >
          <div
            class='title-wrap'
            slot='header'
          >
            <span>{this.$t('上报日志详情')}</span>
            <bk-button
              class='mr10'
              onClick={() => this.handleCopyLog(JSON.stringify(this.sideslider.log))}
            >
              {this.$t('复制')}
            </bk-button>
          </div>
          <div
            class='json-text-style'
            slot='content'
          >
            <VueJsonPretty
              data={this.sideslider.log}
              deep={5}
              virtual={true}
              virtualLines={80}
            />
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
