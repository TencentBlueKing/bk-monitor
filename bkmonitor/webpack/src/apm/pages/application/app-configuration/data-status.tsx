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

import VueJsonPretty from 'vue-json-pretty';
import { Component, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import {
  dataSampling,
  dataViewConfig,
  noDataStrategyDisable,
  noDataStrategyEnable,
  noDataStrategyInfo
} from '../../../../monitor-api/modules/apm_meta';
import { copyText } from '../../../../monitor-common/utils/utils';
import TimeRange, { TimeRangeType } from '../../../../monitor-pc/components/time-range/time-range';
import { getDefautTimezone, updateTimezone } from '../../../../monitor-pc/i18n/dayjs';
import DashboardPanel from '../../../../monitor-ui/chart-plugins/components/dashboard-panel';
import { ApdexChart } from '../../../../monitor-ui/chart-plugins/plugins/apdex-chart/apdex-chart';
import { IViewOptions, PanelModel } from '../../../../monitor-ui/chart-plugins/typings';
import PanelItem from '../../../components/panel-item/panel-item';

import { IStrategyData } from './type';

import 'vue-json-pretty/lib/styles.css';

@Component
export default class DataStatus extends tsc<{}> {
  pickerTimeRange: string[] = [
    dayjs(new Date()).add(-1, 'd').format('YYYY-MM-DD'),
    dayjs(new Date()).format('YYYY-MM-DD')
  ];
  strategyLoading = false;
  tableLoading = false;
  apdexChartPanel: PanelModel;
  /** 日志上报侧栏配置 */
  sideslider = { show: false, log: null };
  /** 无数据告警信息 */
  strategyInfo: IStrategyData = {
    id: 0, // 策略id
    name: '', // 告警名称
    alert_status: 0, // 告警状态
    alert_graph: null,
    is_enabled: true, // 启停
    notice_group: [] // 告警组
  };
  expandIndex = -1; // 采样数据展开项索引
  dashboardPanels = []; // 数据量趋势面板配置
  samplingList = []; // 采样数据
  collapseRowIndexs: number[] = []; // 采样数据记录展开收起的行
  healthMaps = { 1: this.$t('健康'), 2: this.$t('有告警') };

  // 派发到子孙组件内的视图配置变量
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = ['now-1d', 'now'];
  /** 时区 */
  @ProvideReactive('timezone') timezone: string = getDefautTimezone();
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];

  /** 应用ID */
  get appId() {
    return Number(this.$route.params?.id || 0);
  }
  /** 告警icon颜色 */
  get strategyStautsColor() {
    return this.strategyInfo.alert_status === 1 ? 'green' : 'red';
  }

  created() {
    this.timezone = getDefautTimezone();
    this.getNoDataStrategyInfo();
    this.getDataView();
    this.getsamplingList();
  }

  /**
   * @desc 获取无数据告警信息
   */
  async getNoDataStrategyInfo() {
    this.strategyLoading = true;
    const params = {
      application_id: this.appId,
      start_time: Date.parse(this.pickerTimeRange[0]) / 1000,
      end_time: Date.parse(this.pickerTimeRange[1]) / 1000
    };
    const data = await noDataStrategyInfo(params).catch(() => {});
    Object.assign(this.strategyInfo, data);
    this.apdexChartPanel = new PanelModel(this.strategyInfo.alert_graph);
    this.strategyLoading = false;
  }
  /**
   * @desc 获取图表数据
   */
  async getDataView() {
    this.dashboardPanels = await dataViewConfig(this.appId).catch(() => []);
  }
  /**
   * @desc 获取采样数据
   */
  async getsamplingList() {
    this.tableLoading = true;
    const params = {
      application_id: this.appId,
      size: 10,
      log_type: 'trace'
    };
    const data = await dataSampling(this.appId, params).catch(() => []);
    this.collapseRowIndexs = [];
    this.samplingList = data?.map(item => {
      const date = dayjs.tz(dayjs(item.sampling_time));
      return {
        ...item,
        sampling_time: date.isValid() ? date.format('YYYY-MM-DD HH:mm:ssZ') : '--'
      };
    });
    this.tableLoading = false;
  }
  /**
   * @desc 日期范围改变
   * @param { array } date 日期范围
   */
  handleTimeRangeChange(date) {
    this.timeRange = date;
    this.getNoDataStrategyInfo();
  }
  handleTimezoneChange(timezone: string) {
    updateTimezone(timezone);
    this.timezone = timezone;
    this.getNoDataStrategyInfo();
    this.getDataView();
    this.getsamplingList();
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
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }
  /**
   * @desc 查看上报日志
   * @param { object } log 日志内容
   */
  handleViewDetail(log: object) {
    this.sideslider = {
      show: true,
      log
    };
  }
  /**
   * @desc 开关前置校验
   * @param { boolean } value 当前开关状态
   */
  preCheckChange(value: boolean) {
    const applicationId = this.appId;
    return new Promise((resolve, reject) => {
      this.$bkInfo({
        title: value ? this.$t('你确认要关闭？') : this.$t('你确认要开启？'),
        confirmLoading: true,
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        confirmFn: async () => {
          const api = value ? noDataStrategyDisable : noDataStrategyEnable;
          const isPass = await api({ application_id: applicationId })
            .then(() => {
              this.getNoDataStrategyInfo();
              return true;
            })
            .catch(() => false);
          isPass ? resolve(true) : reject();
        },
        cancelFn: () => {
          reject();
        }
      });
    });
  }
  /**
   * @desc 告警跳转
   * @param { string } option
   */
  handlePageChange(option: string) {
    const { id } = this.strategyInfo;
    const hash =
      option === 'edit' ? `#/strategy-config/edit/${String(id)}` : `#/event-center?queryString=strategy_id:${id}`;
    const url = location.href.replace(location.hash, hash);
    window.open(url, '_blank');
  }
  handleRefresh() {
    this.getsamplingList();
  }

  render() {
    const logSlots = {
      default: props => [
        <div
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
        </div>
      ]
    };
    const operatorSlot = {
      default: props => [
        <bk-button
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleCopyLog(JSON.stringify(props.row.raw_log))}
        >
          {this.$t('复制')}
        </bk-button>,
        <bk-button
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleViewDetail(props.row.raw_log)}
        >
          {this.$t('查看上报数据')}
        </bk-button>
      ]
    };

    return (
      <div class='conf-content data-status-wrap'>
        <PanelItem title={this.$t('告警策略')}>
          <TimeRange
            slot='headerTool'
            value={this.timeRange}
            timezone={this.timezone}
            onTimezoneChange={this.handleTimezoneChange}
            onChange={this.handleTimeRangeChange}
          />
          <div
            class='form-content'
            v-bkloading={{ isLoading: this.strategyLoading }}
          >
            <div class='content-card'>
              <div class='msg-item'>
                <span
                  class='tip-label'
                  v-bk-tooltips={{ content: this.$t('当没有收到任何数据可以进行告警通知。'), allowHTML: false }}
                >
                  {this.$t('无数据告警')}
                </span>
                <bk-switcher
                  size='small'
                  theme='primary'
                  value={this.strategyInfo.is_enabled}
                  pre-check={() => this.preCheckChange(this.strategyInfo.is_enabled)}
                />
              </div>
              <div class='msg-item'>
                <span class='label'>{this.$t('告警状态')} : </span>
                <span class={['status-icon', `status-${this.strategyStautsColor}`]}></span>
                <span class='status-name'>{this.healthMaps[this.strategyInfo.alert_status]}</span>
              </div>
              <div class='msg-item'>
                <span class='label'>{this.$t('告警组')} : </span>
                {this.strategyInfo.notice_group.map(group => (
                  <span class='group-tag'>{group.name}</span>
                ))}
              </div>
              <div class='msg-item'>
                <span class='label'>{this.$t('告警状态')} : </span>
                <div class='apdex-chart-box'>
                  {this.apdexChartPanel && (
                    <ApdexChart
                      showChartHeader={false}
                      split-number={2}
                      panel={this.apdexChartPanel}
                    />
                  )}
                </div>
              </div>
              <div class='card-tool'>
                <span
                  class='tool-btn'
                  onClick={() => this.handlePageChange('edit')}
                >
                  {this.$t('button-编辑')}
                </span>
                <span
                  class='tool-btn'
                  onClick={() => this.handlePageChange('event')}
                >
                  {this.$t('历史告警')}
                  <span class='icon-monitor icon-fenxiang'></span>
                </span>
              </div>
            </div>
          </div>
        </PanelItem>
        <PanelItem title={this.$t('数据量趋势')}>
          <div class='form-content'>
            <DashboardPanel
              id={'volumeTrend'}
              panels={this.dashboardPanels}
            />
          </div>
        </PanelItem>
        <PanelItem title={this.$t('数据采样')}>
          <span
            class='right-btn-wrap'
            slot='headerTool'
            onClick={() => this.handleRefresh()}
          >
            <i class='icon-monitor icon-shuaxin'></i>
            {this.$t('button-刷新')}
          </span>
          <bk-table
            class={'sampling-table'}
            outer-border={false}
            row-auto-height={true}
            data={this.samplingList}
            v-bkloading={{ isLoading: this.tableLoading }}
          >
            <bk-table-column
              label={this.$t('序号')}
              type='index'
              width='80'
            />
            <bk-table-column
              label={this.$t('原始数据')}
              scopedSlots={logSlots}
            />
            <bk-table-column
              label={this.$t('采样时间')}
              width='200'
              scopedSlots={{ default: props => props.row.sampling_time }}
            />
            <bk-table-column
              label={this.$t('查看')}
              width='180'
              scopedSlots={operatorSlot}
            />
          </bk-table>
        </PanelItem>

        <bk-sideslider
          ext-cls='origin-log-sideslider'
          transfer={true}
          isShow={this.sideslider.show}
          {...{ on: { 'update:isShow': v => (this.sideslider.show = v) } }}
          quick-close={true}
          width={596}
        >
          <div
            slot='header'
            class='title-wrap'
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
              virtual={true}
              virtualLines={80}
              deep={5}
              data={this.sideslider.log}
            />
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
