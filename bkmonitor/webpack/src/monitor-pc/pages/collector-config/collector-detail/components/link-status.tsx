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
import { Button, Divider, Sideslider, Table, TableColumn } from 'bk-magic-vue';

import { transferCountSeries, transferLatestMsg } from '../../../../../monitor-api/modules/datalink';
import { copyText } from '../../../../../monitor-common/utils/utils';
import MonacoEditor from '../../../../components/editors/monaco-editor.vue';
import { TimeRangeType } from '../../../../components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';

import LinkStatusChart from './link-status-chart';

import './link-status.scss';

interface LinkStatusProps {
  id: number;
}

interface ChartConfigModel {
  timeRange: TimeRangeType;
  data: any[];
}

@Component
export default class LinkStatus extends tsc<LinkStatusProps, {}> {
  @Prop({ type: Number, required: true }) id: number;

  minuteChartConfig: ChartConfigModel = {
    timeRange: ['now-1h', 'now'],
    data: []
  };

  dayChartConfig: ChartConfigModel = {
    timeRange: ['now-7d', 'now'],
    data: []
  };

  tableList = [];
  tableLoading = false;

  sideslider = {
    isShow: false,
    data: '',
    title: ''
  };

  handleTimeRange(val, type: 'minute' | 'day') {
    if (type === 'minute') {
      this.minuteChartConfig.timeRange = val;
    } else {
      this.dayChartConfig.timeRange = val;
    }
    this.getChartData(type);
  }

  async getChartData(type: 'minute' | 'day') {
    const [startTime, endTime] = handleTransformToTimestamp(
      type === 'minute' ? this.minuteChartConfig.timeRange : this.dayChartConfig.timeRange
    );
    const res = await transferCountSeries({
      collect_config_id: this.id,
      interval_option: type,
      start_time: startTime * 1000,
      end_time: endTime * 1000
    }).catch(() => ({ datapoints: [] }));
    res.datapoints = [
      [1698218100000, 18],
      [1698218160000, 100],
      [1698218220000, 100],
      [1698218280000, 100],
      [1698218340000, 100],
      [1698218400000, 108],
      [1698218460000, 100],
      [1698218520000, 100],
      [1698218580000, 100],
      [1698218640000, 99],
      [1698218700000, 108],
      [1698218760000, 100],
      [1698218820000, 100],
      [1698218880000, 100],
      [1698218940000, 101],
      [1698219000000, 79]
    ];

    if (type === 'minute') {
      this.minuteChartConfig.data = res.datapoints;
    } else {
      this.dayChartConfig.data = res.datapoints;
    }
  }

  async getTableData() {
    this.tableLoading = true;
    const res = await transferLatestMsg({
      collect_config_id: this.id
    }).catch(() => []);
    this.tableList = res;
    this.tableLoading = false;
  }

  handleHiddenSlider() {
    this.sideslider.isShow = false;
  }

  handleCopy(text: string) {
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

  mounted() {
    this.getChartData('minute');
    this.getChartData('day');
    this.getTableData();
  }

  render() {
    return (
      <div class='link-status-component'>
        <div class='panel-title'>{this.$t('数据量趋势')}</div>
        <div class='chart-panel'>
          <div class='chart-container'>
            <LinkStatusChart
              type='minute'
              timeRange={this.minuteChartConfig.timeRange}
              data={this.minuteChartConfig.data}
              onRefresh={() => this.getChartData('minute')}
              onTimeRangeChange={val => this.handleTimeRange(val, 'minute')}
            />
          </div>
          <div class='chart-container'>
            <LinkStatusChart
              type='day'
              timeRange={this.dayChartConfig.timeRange}
              data={this.dayChartConfig.data}
              onRefresh={() => this.getChartData('day')}
              onTimeRangeChange={val => this.handleTimeRange(val, 'day')}
            />
          </div>
        </div>
        <Divider class='divider'></Divider>

        <div class='table-container'>
          <div class='title'>
            <div class='panel-title'>{this.$t('数据采样')}</div>
            <div class='refresh-btn'>
              <i class='icon-monitor icon-zhongzhi1'></i>
            </div>
          </div>

          <div class='table-content'>
            <Table
              class='cluster-table'
              data={this.tableList}
              v-bkloading={{ isLoading: this.tableLoading }}
              max-height='254'
            >
              <TableColumn
                type='index'
                label={this.$t('序列')}
                width='90'
              />
              <TableColumn label={this.$t('原始数据')} />
              <TableColumn
                label={this.$t('采集时间')}
                width='250'
              />
              <TableColumn
                label={this.$t('操作')}
                width='175'
              />
            </Table>
          </div>
        </div>

        <Sideslider
          ext-cls='data-status-sideslider'
          transfer={true}
          isShow={this.sideslider.isShow}
          {...{ on: { 'update:isShow': v => (this.sideslider.isShow = v) } }}
          quick-close={true}
          width={656}
          onHidden={this.handleHiddenSlider}
        >
          <div
            slot='header'
            class='sideslider-title'
          >
            <span>{this.sideslider.title + this.$t('上报日志详情')}</span>
            <Button onClick={() => this.handleCopy(this.sideslider.data)}>{this.$tc('复制')}</Button>
          </div>
          <div slot='content'>
            <MonacoEditor
              class='code-viewer'
              language='json'
              value={this.sideslider.data}
              options={{ readOnly: true }}
              style='height: calc(100vh - 60px)'
            ></MonacoEditor>
          </div>
        </Sideslider>
      </div>
    );
  }
}
