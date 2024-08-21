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

import dayjs from 'dayjs';
import { connect, disconnect } from 'echarts/core';
import { metricDetailStatistics } from 'monitor-api/modules/apm_metric';
import { random } from 'monitor-common/utils';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import CompareTopoFullscreen from './compare-topo-fullscreen/compare-topo-fullscreen';
import MiniChart, { EPointType } from './mini-chart';

import type { ITableColumn, ITablePagination, TableRow } from 'monitor-pc/pages/monitor-k8s/typings/table';

import './details-side.scss';

enum EColumn {
  Chart = 'datapoints',
  CompareCount = 'compare-count',
  DiffCount = 'diff-count',
  InitiativeCount = 'initiative-count',
  InitiativeService = 'initiative-service',
  Operate = 'operate',
  ReferCount = 'refer-count',
  ServerName = 'service',
}

enum EOptionKind {
  callee = 'callee',
  caller = 'caller',
}

export enum EDataType {
  avgDuration = 'avg_duration',
  errorCount = 'error_count',
  requestCount = 'request_count',
}

interface IProps {
  show: boolean;
  timeRange?: TimeRangeType;
  serviceName?: string;
  appName?: string;
  dataType?: EDataType;
  onClose?: () => void;
}

@Component
export default class DetailsSide extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Array, default: () => ['now-1d', 'now'] }) timeRange: TimeRangeType;
  @Prop({ type: String, default: '' }) serviceName: string;
  @Prop({ type: String, default: '' }) appName: string;
  @Prop({ type: String, default: '' }) dataType: EDataType;

  loading = false;
  sourceTableData = [];
  /* 时间 */
  localTimeRange: TimeRangeType = ['now-1d', 'now'];
  timezone: string = getDefaultTimezone();
  /* 主体切换 */
  selectOptions = [
    { id: EDataType.requestCount, name: window.i18n.tc('总请求数') },
    { id: EDataType.errorCount, name: window.i18n.tc('总错误数') },
    { id: EDataType.avgDuration, name: window.i18n.tc('平均响应耗时') },
  ];
  selected = EDataType.requestCount;
  /* 类型切换 */
  typeOptions = [
    { id: EOptionKind.caller, name: window.i18n.tc('主调') },
    { id: EOptionKind.callee, name: window.i18n.tc('被调') },
  ];
  curType = EOptionKind.caller;
  /* 对比时间 */
  compareTimeInfo = [
    {
      id: 'refer',
      name: window.i18n.t('参照时间'),
      time: '--',
      color: '#FF9C01',
    },
    {
      id: 'compare',
      name: window.i18n.t('对比时间'),
      time: '--',
      color: '#7B29FF',
    },
  ];
  /** 对比拓扑弹窗 */
  compareTopoShow = false;
  /* 对比开关 */
  isCompare = false;
  /* 搜索 */
  searchValue = '';

  tableColumns: ITableColumn[] = [];
  tableData: TableRow[] = [];
  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 2,
    limit: 10,
    showTotalCount: true,
  };

  /* 对比点 */
  compareX = 0;
  /* 参照点 */
  referX = 0;
  pointType: EPointType = EPointType.compare;

  chartGroupId = random(8);

  get filterTableColumns() {
    return this.tableColumns;
    /* return this.tableColumns.filter(item => {
      if (this.isCompare) {
        return ![EColumn.InitiativeCount].includes(item.id as EColumn);
      }
      return [EColumn.ServerName, EColumn.InitiativeService, EColumn.InitiativeCount, EColumn.Chart].includes(
        item.id as EColumn
      );
    }); */
  }

  created() {
    connect(this.chartGroupId);
  }

  destroyed() {
    disconnect(this.chartGroupId);
  }

  @Watch('show')
  handleWatchShow(val: boolean) {
    if (val) {
      this.getData();
    }
  }

  async getData() {
    this.loading = true;
    this.selected = this.dataType;
    const [startTime, endTime] = handleTransformToTimestamp(this.localTimeRange);
    const data = await metricDetailStatistics({
      app_name: this.appName,
      start_time: startTime,
      end_time: endTime,
      option_kind: this.curType,
      data_type: this.selected,
      service_name: this.serviceName,
    }).catch(() => ({ data: [] }));
    this.sourceTableData = Object.freeze(data.data);
    this.tableColumns = data.columns.map(item => {
      if (item.id === EColumn.Chart) {
        return {
          ...item,
          type: 'scoped_slots',
          renderHeader: () => this.chartLabelPopover(),
        };
      }
      return item;
    });
    this.getTableData();
    this.loading = false;
  }

  getTableData() {
    this.tableData = this.sourceTableData
      .slice(this.pagination.limit * (this.pagination.current - 1), this.pagination.limit * this.pagination.current)
      .map(item => {
        return {
          ...item,
          [EColumn.Chart]: (item[EColumn.Chart] || []).filter(d => d[0] !== null),
          id: random(8),
        };
      });
  }

  handleClose() {
    this.$emit('close');
  }

  handleTimeRangeChange(date) {
    this.timeRange = date;
  }

  handleTimezoneChange(timezone: string) {
    updateTimezone(timezone);
    this.timezone = timezone;
  }

  handleTypeChange(id: EOptionKind) {
    this.curType = id;
  }

  handleSearch() {}

  handlePointTypeChange(value: EPointType) {
    this.pointType = value;
  }
  handleCompareXChange(value: number) {
    this.compareX = value;
    this.setCompareTimes('compare', value);
  }
  handleReferXChange(value: number) {
    this.referX = value;
    this.setCompareTimes('refer', value);
  }

  setCompareTimes(type, value) {
    for (const item of this.compareTimeInfo) {
      if (item.id === type) {
        if (!value) {
          item.time = '--';
          break;
        }
        item.time = dayjs(value).format('YYYY.MM.DD HH:mm');
        break;
      }
    }
  }

  handleSwitchCompareChange(v: boolean) {
    try {
      if (v) {
        setTimeout(() => {
          this.$refs.table.$refs.table.$refs.tableHeader.$refs?.['chart-tip-popover']?.showHandler?.();
        }, 200);
      } else {
        this.handleCompareXChange(0);
        this.handleReferXChange(0);
        this.$refs.table.$refs.table.$refs.tableHeader.$refs?.['chart-tip-popover']?.hideHandler?.();
      }
    } catch (e) {
      console.log(e);
    }
  }

  chartLabelPopover() {
    return (
      <bk-popover
        ref={'chart-tip-popover'}
        ext-cls={'apm-time-series-details-side-chat-pop'}
        tippy-options={{
          trigger: 'click',
        }}
        disabled={!this.isCompare}
        max-width={150}
        placement='right'
        transfer={true}
      >
        <div>{window.i18n.tc('缩略图')}</div>
        <div slot='content'>
          <span>{this.$t('选择任一图并点选所需对比时间和参照时间')}</span>
        </div>
      </bk-popover>
    );
  }

  handleViewTopo() {
    this.compareTopoShow = true;
  }

  render() {
    return (
      <bk-sideslider
        width={960}
        extCls='apm-time-series-details-side'
        beforeClose={this.handleClose}
        isShow={this.show}
        quickClose={true}
        transfer={true}
      >
        <div
          class='header-wrap'
          slot='header'
        >
          <div class='left-title'>请求数详情</div>
          <div class='right-time'>
            <TimeRange
              timezone={this.timezone}
              value={this.localTimeRange}
              onChange={this.handleTimeRangeChange}
              onTimezoneChange={this.handleTimezoneChange}
            />
          </div>
        </div>
        <div
          class='content-wrap'
          slot='content'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='content-header-wrap'>
            <div class='left-wrap'>
              <bk-select
                class='theme-select-wrap'
                v-model={this.selected}
                clearable={false}
              >
                {this.selectOptions.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  />
                ))}
              </bk-select>
              <div class='bk-button-group'>
                {this.typeOptions.map(item => (
                  <bk-button
                    key={item.id}
                    class={this.curType === item.id ? 'is-selected' : ''}
                    onClick={() => this.handleTypeChange(item.id)}
                  >
                    {item.name}
                  </bk-button>
                ))}
              </div>
              <div class='compare-switcher'>
                <bk-switcher
                  v-model={this.isCompare}
                  theme='primary'
                  onChange={this.handleSwitchCompareChange}
                />
                <span class='switcher-text'>{this.$t('对比')}</span>
              </div>
              {this.isCompare && (
                <div class='compare-time-wrap'>
                  {this.compareTimeInfo.map((item, index) => [
                    index ? (
                      <div
                        key={`${item.id}${index}`}
                        class='split-line'
                      />
                    ) : undefined,
                    <div
                      key={item.id}
                      class='compare-time-item'
                    >
                      <span
                        style={{ backgroundColor: item.color }}
                        class='point'
                      />
                      <span class='time-text'>{`${item.name}: ${item.time}`}</span>
                    </div>,
                  ])}
                </div>
              )}
            </div>
            <div class='right-wrap'>
              <bk-input
                v-model={this.searchValue}
                placeholder={this.$t('搜索服务名称')}
                right-icon='bk-icon icon-search'
                clearable
                onChange={this.handleSearch}
                onRightIconClick={this.handleSearch}
              />
            </div>
          </div>
          <div class='content-table-wrap'>
            <CommonTable
              ref='table'
              scopedSlots={{
                [EColumn.DiffCount]: row => {
                  return row[EColumn.DiffCount] > 0 ? (
                    <span class='diff-up-text'>{`+${row[EColumn.DiffCount] * 100}%`}</span>
                  ) : (
                    <span class='diff-down-text'>{`${row[EColumn.DiffCount] * 100}%`}</span>
                  );
                },
                [EColumn.Chart]: row => {
                  return (
                    <div
                      key={row.id}
                      class='chart-wrap'
                    >
                      <MiniChart
                        compareX={this.compareX}
                        data={row.datapoints}
                        disableHover={!this.isCompare}
                        groupId={this.chartGroupId}
                        pointType={this.pointType}
                        referX={this.referX}
                        onCompareXChange={this.handleCompareXChange}
                        onPointTypeChange={this.handlePointTypeChange}
                        onReferXChange={this.handleReferXChange}
                      />
                    </div>
                  );
                },
                [EColumn.Operate]: _row => {
                  return (
                    <bk-button
                      type='primary'
                      text
                      onClick={this.handleViewTopo}
                    >
                      {this.$t('查看拓扑')}
                    </bk-button>
                  );
                },
              }}
              checkable={false}
              columns={this.filterTableColumns}
              data={this.tableData}
              pagination={this.pagination}
              paginationType={'simple'}
            />
          </div>

          <CompareTopoFullscreen
            isService={true}
            show={this.compareTopoShow}
            onShowChange={val => {
              this.compareTopoShow = val;
            }}
          />
        </div>
      </bk-sideslider>
    );
  }
}
