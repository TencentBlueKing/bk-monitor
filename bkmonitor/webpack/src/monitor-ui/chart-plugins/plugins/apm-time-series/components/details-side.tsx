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
import { Debounce, random } from 'monitor-common/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';
import { isEnFn } from 'monitor-pc/utils';

import { getValueFormat } from '../../../../monitor-echarts/valueFormats/valueFormats';
import CompareMiniChart, { EPointType } from '../../mini-time-series/compare-mini-chart';
import CompareTopoFullscreen from './compare-topo-fullscreen/compare-topo-fullscreen';

import type { ITableColumn, ITablePagination, TableRow } from 'monitor-pc/pages/monitor-k8s/typings/table';

import './details-side.scss';

export enum EDataType {
  avgDuration = 'avg_duration',
  errorCount = 'error_count',
  requestCount = 'request_count',
}

export enum EOptionKind {
  callee = 'callee',
  caller = 'caller',
}

enum EColumn {
  Chart = 'datapoints',
  CompareCount = 'compare_count',
  DiffCount = 'diff_count',
  Operate = 'operate',
  OtherService = 'other_service',
  ReferCount = 'refer_count',
  ServerName = 'service',
}

interface IProps {
  appName?: string;
  dataType?: EDataType;
  dimensions?: string[];
  errorCountCategory?: Record<string, string>;
  panelTitle?: string;
  pointValueUnit?: string;
  serviceName?: string;
  show: boolean;
  timeRange?: TimeRangeType;
  onClose?: () => void;
}

@Component
export default class DetailsSide extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Array, default: () => ['now-1d', 'now'] }) timeRange: TimeRangeType;
  @Prop({ type: String, default: '' }) serviceName: string;
  @Prop({ type: String, default: '' }) appName: string;
  @Prop({ type: String, default: '' }) dataType: EDataType;
  @Prop({ type: Array, default: () => [] }) dimensions: string[];
  @Prop({ type: String, default: '' }) panelTitle: string;
  @Prop({ type: String, default: '' }) pointValueUnit: string;
  @Prop({ type: Object, default: () => ({}) }) errorCountCategory: Record<string, string>;

  loading = false;
  sourceTableData = [];
  sourcesTableColumns = [];
  /* 时间 */
  localTimeRange: TimeRangeType = ['now-1h', 'now'];
  timezone: string = getDefaultTimezone();
  selected = 'default';
  /* 类型切换 */
  typeOptions = [
    { id: EOptionKind.caller, name: window.i18n.t('主调') },
    { id: EOptionKind.callee, name: window.i18n.t('被调') },
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
    count: 0,
    limit: 10,
    showTotalCount: true,
  };

  /* 对比点 */
  compareX = 0;
  /* 参照点 */
  referX = 0;
  pointType: EPointType = EPointType.compare;

  chartGroupId = random(8);

  tableKey = random(8);

  sortInfo = {
    prop: '',
    order: '',
  };

  emptyStatus = 'empty';
  get unit() {
    if (this.dataType === EDataType.errorCount) {
      return this.selected === 'error_rate' ? 'percentunit' : 'none';
    }
    if (!this.pointValueUnit || this.pointValueUnit === 'number') {
      return '';
    }
    return this.pointValueUnit;
  }
  get unitDecimal() {
    if (this.dataType === EDataType.errorCount) {
      return this.selected === 'error_rate' ? 2 : 0;
    }
    if (this.dataType === EDataType.requestCount) return 0;
    return 2;
  }
  get selectOptions() {
    if (this.dataType === EDataType.errorCount) {
      return [
        {
          id: 'error_count',
          name: window.i18n.t('错误数'),
        },
        {
          id: 'error_rate',
          name: window.i18n.t('错误率'),
        },
      ];
    }
    if (this.dataType === EDataType.avgDuration) {
      return this.dimensions.map(dim => {
        return {
          id: dim,
          name: dim,
        };
      });
    }
    return [];
  }
  initData() {
    this.compareTimeInfo = [
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
    this.curType = EOptionKind.caller;
    this.selected = '';
    this.isCompare = false;
    this.compareX = 0;
    this.referX = 0;
    this.pointType = EPointType.compare;
    this.localTimeRange = JSON.parse(JSON.stringify(this.timeRange));
    this.sortInfo = {
      prop: '',
      order: '',
    };
    this.tableColumns = [];
    this.tableData = [];
    this.emptyStatus = 'empty';
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
      this.initData();
      this.selected = this.selectOptions[0]?.id || 'default';
      if (this.dataType === EDataType.avgDuration) {
        // 响应耗时默认是 平均响应耗时
        this.selected = 'AVG';
      }
      this.getData();
    }
  }

  /**
   * @description 调用接口获取数据
   */
  async getData() {
    this.loading = true;
    this.tableKey = random(8);
    const [startTime, endTime] = handleTransformToTimestamp(this.localTimeRange);
    const data = await metricDetailStatistics({
      app_name: this.appName,
      start_time: startTime,
      end_time: endTime,
      option_kind: this.curType,
      data_type: this.dataType === EDataType.errorCount ? this.selected : this.dataType,
      dimension: this.dataType === EDataType.errorCount ? undefined : this.selected,
      service_name: this.serviceName,
    }).catch(() => ({ data: [], columns: [] }));
    this.sourceTableData = Object.freeze(
      data.data.map(item => {
        let avgDuration = null;
        if (item.avg_duration) {
          avgDuration = {
            value: item.avg_duration[0],
            unit: item.avg_duration[1],
          };
        }
        return {
          ...item,
          avg_duration: avgDuration,
        };
      })
    );
    this.sourcesTableColumns = Object.freeze(
      data.columns.map(item => {
        if (item.id === EColumn.ServerName) {
          return {
            ...item,
            min_width: 200,
          };
        }
        if (item.id === EColumn.OtherService) {
          return {
            ...item,
            min_width: 150,
          };
        }
        if (item.id === EColumn.Chart) {
          return {
            ...item,
            type: 'scoped_slots',
            min_width: 167,
            renderHeader: () => this.chartLabelPopover(),
          };
        }
        return item;
      })
    );
    this.pagination.current = 1;
    this.pagination.count = this.sourceTableData.length;
    this.getTableData();
    this.loading = false;
  }

  /* 筛选及搜索 */
  getFilterData() {
    const { prop, order } = this.sortInfo;
    /* 对比及参照数据 */
    const diffItemFn = item => {
      const pointData = (item[EColumn.Chart] || []).filter(d => d[0] !== null);
      let compareCount = 0;
      let referCount = 0;
      let diffCount = 0;
      if (this.pointType === EPointType.end) {
        let i = 0;
        for (const point of pointData) {
          if (point[1] === this.compareX) {
            compareCount = point[0];
            i += 1;
          }
          if (point[1] === this.referX) {
            referCount = point[0];
            i += 1;
          }
          if (i === 2) {
            break;
          }
        }
        diffCount = (compareCount - referCount) / referCount || 0;
        if (referCount === 0 && compareCount) {
          diffCount = 1;
        }
        if (compareCount === 0 && referCount) {
          diffCount = -1;
        }
      }
      const unit = this.unit;
      return {
        [EColumn.Chart]: pointData,
        [EColumn.CompareCount]: unit ? { value: compareCount, unit } : compareCount,
        [EColumn.ReferCount]: unit ? { value: referCount, unit } : referCount,
        [EColumn.DiffCount]: diffCount,
      };
    };
    let filterTableData = this.sourceTableData.map((item, index) => {
      const diffItems = diffItemFn(item);
      return {
        ...item,
        ...diffItems,
        id: `${this.tableKey}_${index}`,
        [EColumn.ServerName]: {
          ...item[EColumn.ServerName],
          disabledClick: !item[EColumn.ServerName]?.url,
        },
      };
    });
    const sortItemValue = (key, item) => {
      if (typeof item[key] === 'object') {
        return item[key].value;
      }
      return item[key];
    };
    switch (order) {
      case 'ascending': {
        filterTableData = filterTableData.sort((a, b) => sortItemValue(prop, a) - sortItemValue(prop, b));
        break;
      }
      case 'descending': {
        filterTableData = filterTableData.sort((a, b) => sortItemValue(prop, b) - sortItemValue(prop, a));
        break;
      }
      default: {
        break;
      }
    }
    /* 搜索服务名称 */
    if (this.searchValue) {
      filterTableData = filterTableData.filter(item =>
        item[EColumn.ServerName].name.toLowerCase().includes(this.searchValue.toLowerCase())
      );
    }
    this.pagination.count = filterTableData.length;
    return filterTableData;
  }

  /**
   * @description 整理表格数据
   */
  getTableData() {
    const filterTableData = this.getFilterData();
    /* 分页数据 */
    this.tableData = filterTableData.slice(
      this.pagination.limit * (this.pagination.current - 1),
      this.pagination.limit * this.pagination.current
    );
    this.getTableColumns();
  }

  /**
   * @description 整理表格字段
   */
  getTableColumns() {
    this.tableColumns = this.sourcesTableColumns;
    const tableColumns = [];
    let index = -1;
    for (const column of this.sourcesTableColumns) {
      index += 1;
      if (index === 2 && this.pointType === EPointType.end) {
        tableColumns.push(
          ...[
            {
              id: EColumn.CompareCount,
              name: window.i18n.t('对比'),
              sortable: 'custom',
              type: 'scoped_slots',
            },
            {
              id: EColumn.ReferCount,
              name: window.i18n.t('参照'),
              sortable: 'custom',
              type: 'scoped_slots',
            },
            {
              id: EColumn.DiffCount,
              name: window.i18n.t('差异值'),
              sortable: 'custom',
              type: 'scoped_slots',
              min_width: 100,
            },
          ]
        );
      } else {
        tableColumns.push(column);
      }
    }
    /* if (this.pointType === EPointType.end) {
      tableColumns.push({
        id: EColumn.Operate,
        name: window.i18n.t('操作'),
        type: 'scoped_slots',
        min_width: 80,
      });
    } */
    this.tableColumns = tableColumns;
  }

  /**
   * @description 选择维度
   * @param value
   */
  handleSelectedChange(value: string) {
    this.selected = value;
    this.getData();
  }

  handleClose() {
    this.$emit('close');
  }

  /**
   * @description 时间范围变化
   * @param date
   */
  handleTimeRangeChange(date) {
    this.localTimeRange = date;
    this.getData();
  }

  handleTimezoneChange(timezone: string) {
    updateTimezone(timezone);
    this.timezone = timezone;
  }

  /**
   * @description 切换主调背调
   * @param id
   */
  handleTypeChange(id: EOptionKind) {
    this.curType = id;
    this.getData();
  }

  @Debounce(300)
  handleSearch() {
    this.emptyStatus = this.searchValue ? 'search-empty' : 'empty';
    this.pagination.current = 1;
    this.getTableData();
  }

  /**
   * @description 当前对比阶段
   * @param value
   */
  handlePointTypeChange(value: EPointType) {
    this.pointType = value;
    if (value === EPointType.end) {
      this.getTableData();
    }
  }
  /**
   * @description 设置对比点
   * @param value
   */
  handleCompareXChange(value: number) {
    this.compareX = value;
    this.setCompareTimes('compare', value);
    if (this.pointType === EPointType.end) {
      this.getTableData();
    }
  }
  /**
   * @description 设置参照点
   * @param value
   */
  handleReferXChange(value: number) {
    this.referX = value;
    this.setCompareTimes('refer', value);
    if (this.pointType === EPointType.end) {
      this.getTableData();
    }
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

  /**
   * @description 切换对比开关
   * @param v
   */
  handleSwitchCompareChange(v: boolean) {
    try {
      if (v) {
        setTimeout(() => {
          this.$refs.table.$refs.table.$refs.tableHeader.$refs?.['chart-tip-popover']?.showHandler?.();
        }, 200);
      } else {
        this.pointType = EPointType.compare;
        this.getTableData();
        this.handleCompareXChange(0);
        this.handleReferXChange(0);
        this.$refs.table.$refs.table.$refs.tableHeader.$refs?.['chart-tip-popover']?.hideHandler?.();
      }
    } catch (e) {
      console.log(e);
    }
  }

  /**
   * @description 图表标签提示
   * @returns
   */
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
        <div>{window.i18n.t('缩略图')}</div>
        <div slot='content'>
          <span>{this.$t('选择任一图并点选所需对比时间和参照时间')}</span>
        </div>
      </bk-popover>
    );
  }

  handleViewTopo() {
    this.compareTopoShow = true;
  }

  /**
   * @description 表格分页
   * @param page
   */
  handlePageChange(page: number) {
    this.pagination.current = page;
    this.getTableData();
  }

  /**
   * @description 表格分页
   * @param limit
   */
  handleLimitChange(limit: number) {
    this.pagination.limit = limit;
    this.pagination.current = 1;
    this.getTableData();
  }

  /**
   * @description 表格排序
   * @param sortInfo
   */
  handleSortChange(sortInfo) {
    this.sortInfo = sortInfo;
    this.pagination.current = 1;
    this.getTableData();
  }

  handleClearSearch() {
    this.searchValue = '';
    this.pagination.current = 1;
    this.getTableData();
    this.$nextTick(() => {
      this.emptyStatus = 'empty';
    });
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
          <div class='left-title'>{`${this.panelTitle}${isEnFn() ? ' ' : ''}${this.$t('详情')}`}</div>
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
          // v-bkloading={{ isLoading: this.loading }}
        >
          <div class='content-header-wrap'>
            {this.loading ? (
              <div class='skeleton-element w-336 h-32' />
            ) : (
              <div class='left-wrap'>
                {this.selectOptions.length > 0 && (
                  <bk-select
                    class='theme-select-wrap'
                    v-model={this.selected}
                    clearable={false}
                    onSelected={this.handleSelectedChange}
                  >
                    {this.selectOptions.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </bk-select>
                )}
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
                    size='small'
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
            )}
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
            {this.loading ? (
              <TableSkeleton type={2} />
            ) : (
              <CommonTable
                ref='table'
                scopedSlots={{
                  [EColumn.DiffCount]: row => {
                    return row[EColumn.DiffCount] >= 0 ? (
                      <span class='diff-up-text'>{`+${(row[EColumn.DiffCount] * 100).toFixed(2)}%`}</span>
                    ) : (
                      <span class='diff-down-text'>{`${(row[EColumn.DiffCount] * 100).toFixed(2)}%`}</span>
                    );
                  },
                  [EColumn.Chart]: row => {
                    return (
                      <div
                        key={row.id}
                        class='chart-wrap'
                      >
                        <CompareMiniChart
                          compareX={this.compareX}
                          data={row.datapoints}
                          disableHover={!this.isCompare}
                          groupId={this.chartGroupId}
                          pointType={this.pointType}
                          referX={this.referX}
                          unit={this.unit}
                          unitDecimal={this.unitDecimal}
                          valueTitle={this.panelTitle}
                          onCompareXChange={this.handleCompareXChange}
                          onPointTypeChange={this.handlePointTypeChange}
                          onReferXChange={this.handleReferXChange}
                        />
                      </div>
                    );
                  },
                  [EColumn.CompareCount]: row => {
                    if (typeof row[EColumn.CompareCount] === 'object') {
                      const rowItem = row[EColumn.CompareCount];
                      const timeItem = getValueFormat(rowItem.unit)(rowItem.value, this.unitDecimal);
                      return <span>{`${timeItem.text}${timeItem.suffix}`}</span>;
                    }
                    return row[EColumn.CompareCount];
                  },
                  [EColumn.ReferCount]: row => {
                    if (typeof row[EColumn.ReferCount] === 'object') {
                      const rowItem = row[EColumn.ReferCount];
                      const timeItem = getValueFormat(rowItem.unit)(rowItem.value, this.unitDecimal);
                      return <span>{`${timeItem.text}${timeItem.suffix}`}</span>;
                    }
                    return row[EColumn.ReferCount];
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
                columns={this.tableColumns}
                data={this.tableData}
                hasColumnSetting={false}
                pagination={this.pagination}
                paginationType={'simple'}
                onLimitChange={this.handleLimitChange}
                onPageChange={this.handlePageChange}
                onSortChange={this.handleSortChange}
              >
                <div slot='empty'>
                  <EmptyStatus
                    type={this.emptyStatus}
                    onOperation={this.handleClearSearch}
                  />
                </div>
              </CommonTable>
            )}
          </div>

          <CompareTopoFullscreen
            callType={this.curType}
            compareTime={this.compareX}
            dataType={this.dataType}
            isService={true}
            referTime={this.referX}
            secondSelectList={this.selectOptions}
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
