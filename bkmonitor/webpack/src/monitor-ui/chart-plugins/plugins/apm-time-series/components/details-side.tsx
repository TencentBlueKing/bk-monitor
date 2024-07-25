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

import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import MiniChart from './mini-chart';

import type { ITableColumn, ITablePagination, TableRow } from 'monitor-pc/pages/monitor-k8s/typings/table';

import './details-side.scss';

enum EColumn {
  Chart = 'chart',
  CompareCount = 'compare-count',
  DiffCount = 'diff-count',
  InitiativeCount = 'initiative-count',
  InitiativeService = 'initiative-service',
  Operate = 'operate',
  ReferCount = 'refer-count',
  ServerName = 'service_name',
}

interface IProps {
  show: boolean;
  onClose?: () => void;
}

@Component
export default class DetailsSide extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;

  /* 时间 */
  timeRange: TimeRangeType = ['now-1d', 'now'];
  timezone: string = getDefaultTimezone();
  /* 主体切换 */
  selectOptions = [
    { id: 'avg', name: '平均响应耗时' },
    { id: 'error', name: '总错误数' },
  ];
  selected = 'avg';
  /* 类型切换 */
  typeOptions = [
    { id: 'initiative', name: '主调' },
    { id: 'passive', name: '被调' },
  ];
  curType = 'initiative';
  /* 对比时间 */
  compareTimeInfo = [
    {
      id: 'refer',
      name: window.i18n.t('参照时间'),
      time: '2024.1.1 00:00',
      color: '#FF9C01',
    },
    {
      id: 'compare',
      name: window.i18n.t('对比时间'),
      time: '2024.1.1 00:00',
      color: '#7B29FF',
    },
  ];
  /* 对比开关 */
  isCompare = false;
  /* 搜索 */
  searchValue = '';

  tableColumns: ITableColumn[] = [
    {
      type: 'link',
      id: EColumn.ServerName,
      name: window.i18n.tc('服务名称'),
    },
    {
      type: 'string',
      id: EColumn.InitiativeService,
      name: window.i18n.tc('调用服务'),
    },
    {
      type: 'number',
      id: EColumn.InitiativeCount,
      name: window.i18n.tc('调用数'),
    },
    {
      id: EColumn.CompareCount,
      type: 'number',
      name: window.i18n.tc('对比'),
    },
    {
      id: EColumn.ReferCount,
      name: window.i18n.tc('参照'),
      type: 'number',
    },
    {
      id: EColumn.DiffCount,
      name: window.i18n.tc('差异值'),
      type: 'scoped_slots',
    },
    {
      type: 'scoped_slots',
      id: EColumn.Chart,
      name: window.i18n.tc('缩略图'),
    },
    {
      type: 'scoped_slots',
      id: EColumn.Operate,
      name: window.i18n.tc('操作'),
    },
  ];
  tableData: TableRow[] = [
    {
      [EColumn.ServerName]: {
        icon: '',
        key: '',
        target: 'null_event',
        url: '',
        value: 'test1',
      },
      [EColumn.InitiativeService]: {
        icon: '',
        type: '',
        text: 'test01',
      },
      [EColumn.InitiativeCount]: 10,
      [EColumn.CompareCount]: 10,
      [EColumn.ReferCount]: 10,
      [EColumn.DiffCount]: 0.45,
      [EColumn.Chart]: null,
      [EColumn.Operate]: null,
    },
    {
      [EColumn.ServerName]: {
        icon: '',
        key: '',
        target: 'null_event',
        url: '',
        value: 'test2',
      },
      [EColumn.InitiativeService]: {
        icon: '',
        type: '',
        text: 'test02',
      },
      [EColumn.InitiativeCount]: 10,
      [EColumn.CompareCount]: 20,
      [EColumn.ReferCount]: 20,
      [EColumn.DiffCount]: -0.45,
      [EColumn.Chart]: null,
      [EColumn.Operate]: null,
    },
  ];
  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 2,
    limit: 10,
    showTotalCount: true,
  };

  get filterTableColumns() {
    return this.tableColumns.filter(item => {
      if (this.isCompare) {
        return ![EColumn.InitiativeCount].includes(item.id as EColumn);
      }
      return [EColumn.ServerName, EColumn.InitiativeService, EColumn.InitiativeCount, EColumn.Chart].includes(
        item.id as EColumn
      );
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

  handleTypeChange(id: string) {
    this.curType = id;
  }

  handleSearch() {}

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
              value={this.timeRange}
              onChange={this.handleTimeRangeChange}
              onTimezoneChange={this.handleTimezoneChange}
            />
          </div>
        </div>
        <div
          class='content-wrap'
          slot='content'
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
              scopedSlots={{
                [EColumn.DiffCount]: row => {
                  return row[EColumn.DiffCount];
                },
                [EColumn.Chart]: _row => {
                  return (
                    <div class='chart-wrap'>
                      <MiniChart />
                    </div>
                  );
                },
                [EColumn.Operate]: _row => {
                  return (
                    <bk-button
                      type='primary'
                      text
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
        </div>
      </bk-sideslider>
    );
  }
}
