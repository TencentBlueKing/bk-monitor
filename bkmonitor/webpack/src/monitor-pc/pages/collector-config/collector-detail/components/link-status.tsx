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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { transferCountSeries, transferLatestMsg } from 'monitor-api/modules/datalink';
import { formatWithTimezone } from 'monitor-common/utils/timezone';
import { copyText } from 'monitor-common/utils/utils';

import MonacoEditor from '../../../../components/editors/monaco-editor.vue';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import DetailRequest from '../detail-request';
import DetailLoadError from './detail-load-error';
import DetailSkeleton from './detail-skeleton';
import LinkStatusChart from './link-status-chart';

import type { TimeRangeType } from '../../../../components/time-range/time-range';

import './link-status.scss';

interface ChartConfigModel {
  data: any[];
  timeRange: TimeRangeType;
}

interface LinkStatusProps {
  collectId: number;
  show: boolean;
}

@Component
export default class LinkStatus extends tsc<LinkStatusProps, {}> {
  @Prop({ type: Number, required: true }) collectId: number;
  @Prop({ type: Boolean, required: false }) show: boolean;

  @Ref('minuteChartRef') minuteChart: LinkStatusChart;
  @Ref('dayChartRef') dayChart: LinkStatusChart;

  minuteChartConfig: ChartConfigModel = {
    timeRange: ['now-1h', 'now'],
    data: [],
  };

  hourChartConfig: ChartConfigModel = {
    timeRange: ['now-6h', 'now'],
    data: [],
  };

  tableList = [];
  tableRequest = new DetailRequest();
  chartRequests = { minute: new DetailRequest(), hour: new DetailRequest() };
  disposed = false;

  sideslider = {
    isShow: false,
    data: '',
  };

  @Watch('show', { immediate: true })
  handleShowChange(val) {
    if (val) {
      if (this.collectId) this.init();
      this.$nextTick(() => {
        this.minuteChart?.chartResize();
        this.dayChart?.chartResize();
      });
    } else this.cancelRequests();
  }

  cancelRequests() {
    this.tableRequest.cancel();
    this.chartRequests.minute.cancel();
    this.chartRequests.hour.cancel();
  }

  beforeDestroy() {
    this.disposed = true;
    this.cancelRequests();
  }

  handleTimeRange(val, type: 'hour' | 'minute') {
    if (type === 'minute') {
      this.minuteChartConfig.timeRange = val;
    } else {
      this.hourChartConfig.timeRange = val;
    }
  }

  async getChartData(type: 'hour' | 'minute') {
    if (this.disposed || !this.show) return;
    const [startTime, endTime] = handleTransformToTimestamp(
      type === 'minute' ? this.minuteChartConfig.timeRange : this.hourChartConfig.timeRange
    );
    return this.chartRequests[type].run(
      signal =>
        transferCountSeries(
          {
            collect_config_id: this.collectId,
            interval_option: type,
            start_time: startTime,
            end_time: endTime,
          },
          { signal, needMessage: false }
        ),
      res => {
        if (type === 'minute') {
          this.minuteChartConfig.data = res[0]?.datapoints || [];
        } else {
          this.hourChartConfig.data = res[0]?.datapoints || [];
        }
      }
    );
  }

  async getTableData() {
    if (this.disposed || !this.show) return;
    return this.tableRequest.run(
      signal =>
        transferLatestMsg(
          {
            collect_config_id: this.collectId,
          },
          { signal, needMessage: false }
        ),
      res => {
        this.tableList = res;
      }
    );
  }

  handleHiddenSlider() {
    this.sideslider.isShow = false;
  }

  handleCopy(text: string) {
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

  handleViewData(row) {
    this.sideslider.isShow = true;
    this.sideslider.data = JSON.stringify(row.raw, null, '\t');
  }

  init() {
    this.getTableData();
  }

  render() {
    return (
      <div class='link-status-component'>
        <div class='panel-title'>{this.$t('数据量趋势')}</div>
        <div class='chart-panel'>
          <div class='chart-container'>
            <LinkStatusChart
              ref='minuteChartRef'
              data={this.minuteChartConfig.data}
              error={this.chartRequests.minute.error}
              getChartData={() => this.getChartData('minute')}
              loaded={this.chartRequests.minute.loaded}
              loading={this.chartRequests.minute.loading}
              timeRange={this.minuteChartConfig.timeRange}
              type='minute'
              onTimeRangeChange={val => this.handleTimeRange(val, 'minute')}
            />
          </div>
          <div class='chart-container'>
            <LinkStatusChart
              ref='dayChartRef'
              data={this.hourChartConfig.data}
              error={this.chartRequests.hour.error}
              getChartData={() => this.getChartData('hour')}
              loaded={this.chartRequests.hour.loaded}
              loading={this.chartRequests.hour.loading}
              timeRange={this.hourChartConfig.timeRange}
              type='hour'
              onTimeRangeChange={val => this.handleTimeRange(val, 'hour')}
            />
          </div>
        </div>
        <bk-divider class='divider' />
        <div class='table-container' aria-busy={this.tableRequest.loading ? 'true' : 'false'}>
          <div class='title'>
            <div class='panel-title'>{this.$t('数据采样')}</div>
            <div
              class='refresh-btn'
              onClick={() => !this.tableRequest.loading && this.getTableData()}
            >
              {this.tableRequest.loading ? (
                <span class='collector-detail-loading-indicator' role='status' aria-label={this.$t('加载中')} />
              ) : <i class='icon-monitor icon-zhongzhi1' />}
            </div>
          </div>

          <div class='table-content'>
            {this.tableRequest.error && (
              <DetailLoadError
                compact={this.tableRequest.loaded}
                onRetry={this.getTableData}
              />
            )}
            {!this.tableRequest.loaded && !this.tableRequest.error ? (
              <DetailSkeleton section='sample' />
            ) : (
              this.tableRequest.loaded && (
                <bk-table
                  class='data-sample-table'
                  data={this.tableList}
                  header-border={false}
                  outer-border={false}
                >
                  <bk-table-column
                    width='120'
                    label={this.$t('序号')}
                    type='index'
                  />
                  <bk-table-column
                    label={this.$t('原始数据')}
                    prop='message'
                    show-overflow-tooltip
                  />
                  <bk-table-column
                    width='250'
                    scopedSlots={{
                      default: ({ row }) => <span>{formatWithTimezone(row.time)}</span>,
                    }}
                    label={this.$t('采集时间')}
                    prop='time'
                  />
                  <bk-table-column
                    width='175'
                    scopedSlots={{
                      default: ({ row }) => [
                        <bk-button
                          key='copy'
                          class='mr8'
                          text
                          onClick={() => this.handleCopy(row.message)}
                        >
                          {this.$t('复制')}
                        </bk-button>,
                        <bk-button
                          key='view'
                          text
                          onClick={() => this.handleViewData(row)}
                        >
                          {this.$t('查看上报数据')}
                        </bk-button>,
                      ],
                    }}
                    label={this.$t('操作')}
                  />
                </bk-table>
              )
            )}
          </div>
        </div>

        <bk-sideslider
          ext-cls='data-status-sideslider'
          isShow={this.sideslider.isShow}
          transfer={true}
          {...{ on: { 'update:isShow': v => (this.sideslider.isShow = v) } }}
          width={656}
          quick-close={true}
          onHidden={this.handleHiddenSlider}
        >
          <div
            class='sideslider-title'
            slot='header'
          >
            <span>{this.$t('上报日志详情')}</span>
            <bk-button onClick={() => this.handleCopy(this.sideslider.data)}>{this.$tc('复制')}</bk-button>
          </div>
          <div slot='content'>
            <MonacoEditor
              style='height: calc(100vh - 60px)'
              class='code-viewer'
              language='json'
              options={{ readOnly: true }}
              value={this.sideslider.data}
            />
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
