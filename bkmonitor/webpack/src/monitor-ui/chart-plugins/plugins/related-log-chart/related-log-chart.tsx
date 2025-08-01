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
import { Component, InjectReactive, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { toPng } from 'html-to-image';
import { Debounce, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import { MONITOR_BAR_OPTIONS } from '../../constants';
import { type CustomChartConnector, downFile } from '../../utils';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';

import type { MonitorEchartOptions, PanelModel } from '../../typings';
import type { ITableDataItem } from '../../typings/table-chart';
import type { ITableColumn } from 'monitor-pc/pages/monitor-k8s/typings';
import type { TranslateResult } from 'vue-i18n';

import './related-log-chart.scss';

const option: MonitorEchartOptions = {
  animation: false,
  color: ['#A3C5FD'],
  xAxis: {
    show: true,
    type: 'time',
  },
  yAxis: {
    type: 'value',
    splitLine: {
      show: true,
      lineStyle: {
        color: '#F0F1F5',
        type: 'solid',
      },
    },
  },
  series: [],
};

interface IRelationLogChartProps {
  panel: PanelModel;
}

@Component
class RelatedLogChart extends CommonSimpleChart {
  @Ref('chart') baseChart: HTMLDivElement;

  @InjectReactive('customChartConnector') customChartConnector: CustomChartConnector;

  empty = true;
  emptyText = window.i18n.t('加载中...');
  emptyChart = false;
  /** 关联是否为蓝鲸日志平台 */
  isBkLog = true;
  /** alert提示文字 */
  alertText: string | TranslateResult = '';
  /** 第三方日志 */
  thirdPartyLog = '';
  /** 搜索关键字 */
  keyword = '';
  /** 关联蓝鲸日志的业务ID */
  relatedBkBizId = -1;
  /** 关联蓝鲸日志的索引集ID */
  relatedIndexSetId = -1;
  /** 关联索引集列表 */
  relatedIndexSetList = [];
  /** 柱状图配置 */
  customOptions: MonitorEchartOptions = deepmerge(MONITOR_BAR_OPTIONS, option, {
    arrayMerge: (_, srcArr) => srcArr,
  });
  /** 汇聚周期 */
  chartInterval: 'auto' | number = 'auto';
  /** 汇聚周期选项 */
  intervalList = [
    { id: 'auto', name: 'auto' },
    { id: '1m', name: '1m' },
    { id: '5m', name: '5m' },
    { id: '1h', name: '1h' },
    { id: '1d', name: '1d' },
  ];
  /** 表格数据 */
  tableData: ITableDataItem[] = [];
  /** 表格列数据 */
  columns: ITableColumn[] = [];
  pagination = {
    offset: 0,
    count: 100,
    limit: 30,
  };
  /** 滚动加载记录时间间隔 */
  localTimeRange: number[] = [0, 0];
  /** 是否滚动加载状态 */
  isScrollLoadTableData = false;
  tableRenderKey = random(6);

  isFilterError = false;

  /* 用于customChartConnector */
  chartId = random(8);

  /* 是否为精简模式 */
  get isSimpleChart() {
    return !!this.panel.options?.related_log_chart?.isSimpleChart;
  }

  /**
   * @description: 获取图表数据
   */
  @Debounce(300)
  async getPanelData(start_time?: string, end_time?: string) {
    this.unregisterObserver();
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.t('加载中...');
    this.keyword = this.panel.options?.related_log_chart?.defaultKeyword ?? this.keyword;
    // 先用 log_predicate 接口判断日志类型 蓝鲸日志平台 or 第三方其他日志
    const predicateLogTarget = this.panel.targets.find(item => item.dataType === 'log_predicate');
    if (predicateLogTarget) {
      const variablesService = new VariablesService({
        ...this.viewOptions,
      });
      const params = variablesService.transformVariables(predicateLogTarget.data);
      (this as any).$api[predicateLogTarget.apiModule]
        [predicateLogTarget.apiFunc](params, { needMessage: false })
        .then(data => {
          if (data) {
            this.empty = false;
            this.relatedBkBizId = data.related_bk_biz_id;
            // 增加前置条件（索引集）列表获取
            const conditionTarget = this.panel.targets.find(item => item.dataType === 'condition');
            if (conditionTarget) {
              const payload = variablesService.transformVariables(conditionTarget.data);
              (this as any).$api[conditionTarget.apiModule]
                [conditionTarget.apiFunc](payload, {
                  needMessage: false,
                })
                .then(res => {
                  if (res.length) {
                    this.relatedIndexSetList = res;
                    const defaultIndexSet = res[0];
                    const { index_set_id: indexSetId } = defaultIndexSet;
                    this.relatedIndexSetId = indexSetId;
                    this.handleRelationData(defaultIndexSet, start_time, end_time);
                  }
                });
            }
          } else {
            this.empty = true;
            this.emptyText = '';
          }
          this.clearErrorMsg();
        })
        .catch(error => {
          this.empty = true;
          this.handleErrorMsgChange(error.msg || error.message);
          this.emptyText = window.i18n.t('出错了');
        })
        .finally(() => {
          this.handleLoadingChange(false);
        });
    }
  }
  /** 处理关联信息展示 */
  handleRelationData(info, start_time = '', end_time = '') {
    const { log_type: logType, index_set_id: indexSetId, related_bk_biz_id: relatedBkBizId } = info;
    if (logType === 'bk_log' || this.isSimpleChart) {
      this.relatedBkBizId = relatedBkBizId;
      this.updateBarChartData(start_time, end_time);
      this.updateTableData(start_time, end_time);
      this.alertText = this.$t('如果需要查看完整日志，可跳转日志检索进行查看');
    } else {
      this.alertText = this.$t('关联了非蓝鲸日志平台的日志，只能进行日志的跳转');
      this.thirdPartyLog = indexSetId;
    }
  }

  handleSetFormatterFunc(seriesData: any, onlyBeginEnd = false) {
    let formatterFunc = null;
    const [firstItem] = seriesData;
    const lastItem = seriesData[seriesData.length - 1];
    const val = new Date('2010-01-01').getTime();
    const getXVal = (timeVal: any) => {
      if (!timeVal) return timeVal;
      return timeVal[0] > val ? timeVal[0] : timeVal[1];
    };
    const minX = Array.isArray(firstItem) ? getXVal(firstItem) : getXVal(firstItem?.value);
    const maxX = Array.isArray(lastItem) ? getXVal(lastItem) : getXVal(lastItem?.value);
    if (minX && maxX) {
      formatterFunc = (v: any) => {
        const duration = dayjs.tz(maxX).diff(dayjs.tz(minX), 'second');
        if (onlyBeginEnd && v > minX && v < maxX) {
          return '';
        }
        if (duration < 60 * 60 * 24 * 1) {
          return dayjs.tz(v).format('HH:mm');
        }
        if (duration < 60 * 60 * 24 * 6) {
          return dayjs.tz(v).format('MM-DD HH:mm');
        }
        if (duration <= 60 * 60 * 24 * 30 * 12) {
          return dayjs.tz(v).format('MM-DD');
        }
        return dayjs.tz(v).format('YYYY-MM-DD');
      };
    }
    return formatterFunc;
  }

  /**
   * @description: 在图表数据没有单位或者单位不一致时则不做单位转换 y轴label的转换用此方法做计数简化
   * @param {number} num
   * @return {*}
   */
  handleYAxisLabelFormatter(num: number): string {
    const si = [
      { value: 1, symbol: '' },
      { value: 1e3, symbol: 'K' },
      { value: 1e6, symbol: 'M' },
      { value: 1e9, symbol: 'G' },
      { value: 1e12, symbol: 'T' },
      { value: 1e15, symbol: 'P' },
      { value: 1e18, symbol: 'E' },
    ];
    const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
    let i: number;
    for (i = si.length - 1; i > 0; i--) {
      if (num >= si[i].value) {
        break;
      }
    }
    return (num / si[i].value).toFixed(3).replace(rx, '$1') + si[i].symbol;
  }
  /**
   * @desc 更新柱状图数据
   */
  async updateBarChartData(start_time?: string, end_time?: string) {
    this.handleLoadingChange(true);
    try {
      this.unregisterObserver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
        interval: this.chartInterval,
        index_set_id: this.relatedIndexSetId,
        keyword: this.keyword,
      };
      const variablesService = new VariablesService({
        ...this.scopedVars,
      });
      this.panel.targets
        .filter(item => item.dataType === 'time_series')
        .map(item =>
          (this as any).$api[item.apiModule]
            ?.[item.apiFunc](
              {
                ...variablesService.transformVariables(item.data),
                ...params,
                view_options: {
                  ...this.viewOptions,
                },
                ...(this.isSimpleChart
                  ? {
                      is_filter_error: this.isFilterError,
                    }
                  : {}),
              },
              { needMessage: false }
            )
            .then(res => {
              if (res.series?.[0].datapoints?.length) {
                this.customOptions.series = [];
                const data = {
                  series: [
                    {
                      data: res.series[0].datapoints,
                      type: 'bar',
                      colorBy: 'data',
                      name: 'COUNT ',
                      zlevel: 100,
                      ...(this.isSimpleChart
                        ? {
                            itemStyle: {
                              color: '#699DF4',
                            },
                          }
                        : {}),
                    },
                  ],
                };
                const formatterFunc = this.handleSetFormatterFunc(res.series?.[0].datapoints);
                const updateOption = deepmerge(option, data);
                this.customOptions = deepmerge(this.customOptions, {
                  ...updateOption,
                  ...(this.isSimpleChart
                    ? {
                        xAxis: {
                          axisLabel: {
                            formatter: formatterFunc || '{value}',
                          },
                          show: true,
                          type: 'time',
                          splitNumber: 3,
                        },
                        yAxis: {
                          axisLabel: {
                            formatter: (v: number) => this.handleYAxisLabelFormatter(v),
                          },
                          type: 'value',
                          splitNumber: 2,
                          splitLine: {
                            show: false,
                          },
                        },
                        toolbox: {
                          feature: {
                            dataZoom: {
                              show: false,
                            },
                          },
                        },
                        tooltip: {
                          className: 'log-chart-simple-chart-tooltip',
                          show: true,
                          trigger: 'axis',
                          appendToBody: true,
                          padding: [8, 8, 8, 8],
                          transitionDuration: 0,
                          formatter: params => {
                            const time = dayjs(params[0].value[0]).format('YYYY-MM-DD HH:mm:ss');
                            const value = params[0].value[1];
                            return `
                    <div class="time-text">${time}</div>
                    <div class="value-text">
                      <div class="color-point"></div>
                      <div>${this.$t('日志数')} : ${value}</div>
                    </div>
                    `;
                          },
                        },
                      }
                    : {}),
                });
                this.emptyChart = false;
              } else {
                this.emptyChart = true;
              }
            })
            .finally(() => {
              this.handleLoadingChange(false);
              setTimeout(() => {
                this.setChartInstance();
              }, 100);
            })
        );
      this.clearErrorMsg();
    } catch (error) {
      this.handleErrorMsgChange(error.msg || error.message);
    }
  }
  /**
   * @desc 更新表格数据
   */
  async updateTableData(start_time?: string, end_time?: string) {
    this.isScrollLoadTableData = !!this.pagination.offset;
    this.handleLoadingChange(true);
    try {
      this.unregisterObserver();

      let startTime;
      let endTime;
      if (this.isScrollLoadTableData) {
        // 分页请求
        [startTime, endTime] = this.localTimeRange;
      } else {
        // 从初始位置开始请求
        [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
        this.localTimeRange = [startTime, endTime];
      }

      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
        keyword: this.keyword,
        limit: this.pagination.limit,
        offset: this.pagination.offset,
        index_set_id: this.relatedIndexSetId,
      };
      const variablesService = new VariablesService({
        ...this.scopedVars,
      });
      await this.panel.targets
        .filter(item => item.dataType === 'table-chart')
        .map(item =>
          (this as any).$api[item.apiModule]
            ?.[item.apiFunc]({
              ...variablesService.transformVariables(item.data),
              ...params,
              view_options: {
                ...this.viewOptions,
              },
            })
            .then(data => {
              if (this.isScrollLoadTableData) {
                this.tableData.push(...data.data);
              } else {
                this.tableRenderKey = random(6);
                this.tableData.splice(0, this.tableData.length, ...data.data);
                this.columns = data.columns;
                this.pagination.count = data.total;
              }
              this.pagination.offset += data.data.length;
            })
            .finally(() => {
              this.handleLoadingChange(false);
            })
        );
    } catch {}
  }
  /** 滚动至底部分页加载 */
  handleScrollEnd() {
    /** 已加载全部 */
    if (this.pagination.offset === this.pagination.count) return;
    this.updateTableData();
  }
  dataZoom(startTime: string, endTime: string) {
    this.updateBarChartData(startTime, endTime);
  }
  handleDblClick() {
    this.updateBarChartData();
  }
  /**
   * @desc 切换汇聚周期
   */
  handleIntervalChange(v) {
    this.chartInterval = v;
    this.updateBarChartData();
  }
  /**
   * @description: 截图操作
   */
  handleSavePng() {
    toPng(this.baseChart)
      .then(url => {
        downFile(url, `${this.$t('总趋势')}.png`);
      })
      .catch(err => {
        console.log(err);
      });
  }
  @Debounce(300)
  handleSearchChange(v: string) {
    this.keyword = v;
    this.handleQueryTable();
  }
  /**
   * @desc 表格数据查询
   */
  handleQueryTable() {
    this.pagination.offset = 0;
    this.updateTableData();
    this.updateBarChartData();
  }
  /**
   * @desc 链接跳转
   */
  goLink() {
    const url = this.isBkLog
      ? `${window.bk_log_search_url}#/retrieve/${this.relatedIndexSetId}?bizId=${this.relatedBkBizId}`
      : this.thirdPartyLog;
    window.open(url, '_blank');
  }
  /**
   * @desc 关联日志
   */
  handleRelated() {
    // const { app_name: appName, service_name: serviceName } = this.viewOptions as Record<string, string>;
    // const hash = `#/apm/service-config?app_name=${appName}&service_name=${serviceName}`;
    // const url = location.href.replace(location.hash, hash);
    // window.open(url, '_blank');
    const url = `${window.bk_log_search_url}#/manage/log-collection/collection-item?bizId=${
      this.bkBizId || (this.relatedBkBizId === -1 ? window.cc_biz_id : this.relatedBkBizId)
    }`;
    window.open(url);
  }
  /** 选择索引集 */
  handleSelectIndexSet(v) {
    const indexSetOption = this.relatedIndexSetList.find(item => item.index_set_id === v);
    if (indexSetOption) {
      this.pagination.offset = 0;
      this.handleRelationData(indexSetOption);
    }
  }

  get selectedOptionAlias() {
    const target = this.relatedIndexSetList.find(item => item.index_set_id === this.relatedIndexSetId);
    return target?.index_set_name ?? '';
  }

  handleIsFilterError() {
    this.updateBarChartData();
  }

  /* 与非echarts图联动时需要调用此函数（存储实例） */
  setChartInstance() {
    if (this.panel.dashboardId === this.customChartConnector?.groupId) {
      this.customChartConnector.setChartInstance(this.chartId, this.$refs?.baseChart);
    }
  }

  /* 与非echarts图联动时需要调用此函数 (联动动作) */
  handleUpdateAxisPointer(event) {
    if (this.panel.dashboardId === this.customChartConnector?.groupId) {
      this.customChartConnector.updateAxisPointer(this.chartId, event?.axesInfo?.[0]?.value || 0);
    }
  }

  contentRender() {
    if (this.isSimpleChart) {
      return (
        <div class='log-chart-simple'>
          <div class='chart-simple-header'>
            {this.relatedBkBizId ? (
              <div
                class='left link-type'
                /*               v-bk-tooltips={{
                content: this.$tc('跳转查看详情'),
              }} */
                onClick={() => this.goLink()}
              >
                <span
                  class='name-text'
                  title={this.selectedOptionAlias}
                >
                  {this.selectedOptionAlias}
                </span>
                <span class='icon-monitor icon-fenxiang' />
              </div>
            ) : (
              <div class='left'>
                <span
                  class='name-text'
                  title={this.selectedOptionAlias}
                >
                  {this.selectedOptionAlias}
                </span>
              </div>
            )}
            <div class='right'>
              {/* <bk-checkbox
                v-model={this.isFilterError}
                onChange={this.handleIsFilterError}
              >
                Error
              </bk-checkbox> */}
            </div>
          </div>
          {!this.emptyChart ? (
            <div
              ref='chart'
              class='chart-instance'
            >
              <BaseEchart
                ref='baseChart'
                width={this.width}
                height={this.height}
                class='base-chart'
                hoverAllTooltips={true}
                options={this.customOptions}
                onDataZoom={this.dataZoom}
                onDblClick={this.handleDblClick}
                onUpdateAxisPointer={this.handleUpdateAxisPointer}
              />
            </div>
          ) : (
            <bk-exception
              scene='part'
              type='empty'
            >
              {this.$t('暂无数据')}
            </bk-exception>
          )}
        </div>
      );
    }
    return (
      <div style='position:relative;height:100%;'>
        <div class='related-alert-info'>
          {this.alertText && (
            <bk-alert showIcon={false}>
              <div slot='title'>
                <span class='alter-text'>{this.alertText}</span>
                {this.isBkLog ? (
                  <span
                    class='link'
                    onClick={() => this.goLink()}
                  >
                    {this.$t('route-日志检索')}
                    <i class='icon-monitor icon-fenxiang' />
                  </span>
                ) : (
                  <span
                    class='link'
                    onClick={() => this.goLink()}
                  >
                    <i class='icon-monitor icon-mc-target-link' />
                    <span>{this.thirdPartyLog}</span>
                  </span>
                )}
              </div>
            </bk-alert>
          )}
        </div>
        {this.isBkLog && (
          <div class='related-log-chart-main'>
            <div class='log-chart-collapse'>
              <div class='collapse-header'>
                <span class='collapse-title'>
                  <span class='title'>{this.$t('总趋势')}</span>
                  {!this.emptyChart && (
                    <div class='title-tool'>
                      <span class='interval-label'>{this.$t('汇聚周期')}</span>
                      <bk-select
                        class='interval-select'
                        behavior='simplicity'
                        clearable={false}
                        size='small'
                        value={this.chartInterval}
                        onChange={this.handleIntervalChange}
                      >
                        {this.intervalList.map(item => (
                          <bk-option
                            id={item.id}
                            key={item.id}
                            name={item.name}
                          >
                            {item.name}
                          </bk-option>
                        ))}
                      </bk-select>
                    </div>
                  )}
                </span>
                {!this.emptyChart && (
                  <i
                    class='icon-monitor icon-mc-camera'
                    v-bk-tooltips={{ content: this.$t('截图到本地') }}
                    onClick={() => this.handleSavePng()}
                  />
                )}
              </div>
              <div class='collapse-content'>
                <div class='monitor-echart-common-content'>
                  {!this.emptyChart ? (
                    <div
                      ref='chart'
                      class='chart-instance'
                    >
                      <BaseEchart
                        width={this.width}
                        height={this.height}
                        class='base-chart'
                        options={this.customOptions}
                        onDataZoom={this.dataZoom}
                        onDblClick={this.handleDblClick}
                      />
                    </div>
                  ) : (
                    <div class='empty-chart empty-chart-text'>{this.$t('查无数据')}</div>
                  )}
                </div>
              </div>
            </div>
            <div class='query-tool'>
              <bk-select
                class='table-search-select'
                v-model={this.relatedIndexSetId}
                v-bk-tooltips={{
                  content: this.selectedOptionAlias,
                  theme: 'light',
                  placement: 'top-start',
                  allowHTML: false,
                }}
                clearable={false}
                onSelected={v => this.handleSelectIndexSet(v)}
              >
                {this.relatedIndexSetList.map(option => (
                  <bk-option
                    id={option.index_set_id}
                    key={option.index_set_id}
                    name={option.index_set_name}
                  />
                ))}
              </bk-select>
              <bk-input
                class='table-search-input'
                vModel={this.keyword}
                onClear={() => this.handleSearchChange('')}
                onEnter={this.handleSearchChange}
              />
              <bk-button
                theme='primary'
                onClick={this.handleQueryTable}
              >
                {this.$t('查询')}
              </bk-button>
            </div>
            {this.columns.length ? (
              <CommonTable
                key={this.tableRenderKey}
                height='100%'
                class='related-log-table'
                checkable={false}
                columns={this.columns}
                data={this.tableData}
                hasColumnSetting={false}
                jsonViewerDataKey='source'
                pagination={null}
                showExpand={true}
                onScrollEnd={this.handleScrollEnd}
              />
            ) : (
              ''
            )}
          </div>
        )}
      </div>
    );
  }

  render() {
    return (
      <div class={['related-log-chart-wrap', { 'simple-wrap': this.isSimpleChart }]}>
        {!this.empty ? (
          this.contentRender()
        ) : (
          <div class='empty-chart'>
            {this.emptyText ? (
              this.emptyText
            ) : this.isSimpleChart ? (
              <bk-exception type='empty'>
                <span class='empty-text'>{this.$t('暂无关联日志')}</span>
                <div class='text-wrap'>
                  <span class='text-row'>{this.$t('可前往配置页去配置相关日志')}</span>
                  <bk-button
                    theme='primary'
                    text
                    onClick={() => this.handleRelated()}
                  >
                    {this.$t('去配置')}
                  </bk-button>
                </div>
              </bk-exception>
            ) : (
              <bk-exception type='building'>
                <span>{this.$t('暂无关联日志')}</span>
                <div class='text-wrap'>
                  <span class='text-row'>{this.$t('可前往配置页去配置相关日志')}</span>
                  <bk-button
                    theme='primary'
                    onClick={() => this.handleRelated()}
                  >
                    {this.$t('日志采集')}
                  </bk-button>
                </div>
              </bk-exception>
            )}
          </div>
        )}
      </div>
    );
  }
}

export default ofType<IRelationLogChartProps>().convert(RelatedLogChart);
