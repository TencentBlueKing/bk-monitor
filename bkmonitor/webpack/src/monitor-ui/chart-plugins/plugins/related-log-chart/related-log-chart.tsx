/* eslint-disable max-len */
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
import { TranslateResult } from 'vue-i18n';
import { Component, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';
import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import type { EChartOption } from 'echarts';
import { toPng } from 'html-to-image';

import { Debounce, random } from '../../../../monitor-common/utils/utils';
import { handleTransformToTimestamp } from '../../../../monitor-pc/components/time-range/utils';
import CommonTable from '../../../../monitor-pc/pages/monitor-k8s/components/common-table';
import { ITableColumn } from '../../../../monitor-pc/pages/monitor-k8s/typings';
import { MONITOR_BAR_OPTIONS } from '../../constants';
import { PanelModel } from '../../typings';
import { ITableDataItem } from '../../typings/table-chart';
import { downFile } from '../../utils';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';

import './related-log-chart.scss';

const option: EChartOption = {
  animation: false,
  color: ['#A3C5FD'],
  xAxis: {
    show: true,
    type: 'time'
  },
  yAxis: {
    type: 'value',
    splitLine: {
      show: true,
      lineStyle: {
        color: '#F0F1F5',
        type: 'solid'
      }
    }
  },
  series: []
};

interface IRelationLogChartProps {
  panel: PanelModel;
}

@Component
class RelatedLogChart extends CommonSimpleChart {
  @Ref() baseChart: HTMLDivElement;

  empty = true;
  emptyText = window.i18n.tc('加载中...');
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
  customOptions: EChartOption = deepmerge(MONITOR_BAR_OPTIONS, option, {
    arrayMerge: (_, srcArr) => srcArr
  });
  /** 汇聚周期 */
  chartInterval: number | 'auto' = 'auto';
  /** 汇聚周期选项 */
  intervalList = [
    { id: 'auto', name: 'auto' },
    { id: '1m', name: '1m' },
    { id: '5m', name: '5m' },
    { id: '1h', name: '1h' },
    { id: '1d', name: '1d' }
  ];
  /** 表格数据 */
  tableData: ITableDataItem[] = [];
  /** 表格列数据 */
  columns: ITableColumn[] = [];
  pagination = {
    offset: 0,
    count: 100,
    limit: 30
  };
  /** 滚动加载记录时间间隔 */
  localTimeRange: number[] = [0, 0];
  /** 是否滚动加载状态 */
  isScrollLoadTableData = false;
  tableRenderKey = random(6);

  /**
   * @description: 获取图表数据
   */
  @Debounce(300)
  async getPanelData(start_time?: string, end_time?: string) {
    this.unregisterOberver();
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    this.keyword = this.panel.options?.related_log_chart?.defaultKeyword ?? this.keyword;
    // 先用 log_predicate 接口判断日志类型 蓝鲸日志平台 or 第三方其他日志
    const predicateLogTarget = this.panel.targets.find(item => item.dataType === 'log_predicate');
    if (predicateLogTarget) {
      const variablesService = new VariablesService({
        ...this.viewOptions
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
                  needMessage: false
                })
                .then(res => {
                  if (res.length) {
                    this.relatedIndexSetList = res;
                    const defaultIndexSet = res[0];
                    const { index_set_id: indexSetId } = defaultIndexSet;
                    this.relatedIndexSetId = indexSetId;
                    this.handleRealtionData(defaultIndexSet, start_time, end_time);
                  }
                });
            }
          } else {
            this.empty = true;
            this.emptyText = '';
            this.handleLoadingChange(false);
          }
          this.clearErrorMsg();
        })
        .catch(error => {
          this.empty = true;
          this.handleErrorMsgChange(error.msg || error.message);
          this.emptyText = window.i18n.tc('出错了');
          this.handleLoadingChange(false);
        });
    }
  }
  /** 处理关联信息展示 */
  handleRealtionData(info, start_time = '', end_time = '') {
    const { log_type: logType, index_set_id: indexSetId, related_bk_biz_id: relatedBkBizId } = info;
    if (logType === 'bk_log') {
      this.relatedBkBizId = relatedBkBizId;
      this.updateBarChartData(start_time, end_time);
      this.updateTableData(start_time, end_time);
      this.alertText = this.$t('如果需要查看完整日志，可跳转日志检索进行查看');
    } else {
      this.alertText = this.$t('关联了非蓝鲸日志平台的日志，只能进行日志的跳转');
      this.thirdPartyLog = indexSetId;
    }
  }
  /**
   * @desc 更新柱状图数据
   */
  async updateBarChartData(start_time?: string, end_time?: string) {
    this.handleLoadingChange(true);
    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
        interval: this.chartInterval,
        index_set_id: this.relatedIndexSetId,
        keyword: this.keyword
      };
      const variablesService = new VariablesService({
        ...this.scopedVars
      });
      this.panel.targets
        .filter(item => item.dataType === 'time_series')
        .map(
          item =>
            (this as any).$api[item.apiModule]
              ?.[item.apiFunc](
                {
                  ...variablesService.transformVariables(item.data),
                  ...params,
                  view_options: {
                    ...this.viewOptions
                  }
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
                        zlevel: 100
                      }
                    ]
                  };
                  const updateOption = deepmerge(option, data);
                  this.customOptions = deepmerge(this.customOptions, updateOption);
                  this.emptyChart = false;
                } else {
                  this.emptyChart = true;
                }
              })
              .finally(() => {
                this.handleLoadingChange(false);
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
      this.unregisterOberver();

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
        index_set_id: this.relatedIndexSetId
      };
      const variablesService = new VariablesService({
        ...this.scopedVars
      });
      await this.panel.targets
        .filter(item => item.dataType === 'table-chart')
        .map(
          item =>
            (this as any).$api[item.apiModule]
              ?.[item.apiFunc]({
                ...variablesService.transformVariables(item.data),
                ...params,
                view_options: {
                  ...this.viewOptions
                }
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
    } catch (e) {}
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
      this.bkBizId || this.relatedBkBizId
    }`;
    window.open(url);
  }
  /** 选择索引集 */
  handleSelectIndexSet(v) {
    const indexSetOption = this.relatedIndexSetList.find(item => item.index_set_id === v);
    if (indexSetOption) {
      this.pagination.offset = 0;
      this.handleRealtionData(indexSetOption);
    }
  }

  get selectedOptionAlias() {
    // eslint-disable-next-line eqeqeq
    const target = this.relatedIndexSetList.find(item => item.index_set_id == this.relatedIndexSetId);
    return target?.index_set_name ?? '';
  }

  render() {
    return (
      <div class='related-log-chart-wrap'>
        {!this.empty ? (
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
                        <i class='icon-monitor icon-fenxiang'></i>
                      </span>
                    ) : (
                      <span
                        class='link'
                        onClick={() => this.goLink()}
                      >
                        <i class='icon-monitor icon-mc-target-link'></i>
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
                            size='small'
                            behavior='simplicity'
                            clearable={false}
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
                          class='chart-instance'
                          ref='baseChart'
                        >
                          <BaseEchart
                            class='base-chart'
                            height={this.height}
                            width={this.width}
                            options={this.customOptions}
                            onDataZoom={this.dataZoom}
                            onDblClick={this.handleDblClick}
                          />
                        </div>
                      ) : (
                        <div class='empty-chart'>{this.$t('查无数据')}</div>
                      )}
                    </div>
                  </div>
                </div>
                <div class='query-tool'>
                  <bk-select
                    class='table-search-select'
                    v-model={this.relatedIndexSetId}
                    clearable={false}
                    onSelected={v => this.handleSelectIndexSet(v)}
                    v-bk-tooltips={{
                      content: this.selectedOptionAlias,
                      theme: 'light',
                      placement: 'top-start',
                      allowHTML: false
                    }}
                  >
                    {this.relatedIndexSetList.map(option => (
                      <bk-option
                        key={option.index_set_id}
                        id={option.index_set_id}
                        name={option.index_set_name}
                      ></bk-option>
                    ))}
                  </bk-select>
                  <bk-input
                    class='table-search-input'
                    vModel={this.keyword}
                    onEnter={this.handleSearchChange}
                    onClear={() => this.handleSearchChange('')}
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
                    class='related-log-table'
                    checkable={false}
                    height='100%'
                    hasColnumSetting={false}
                    showExpand={true}
                    data={this.tableData}
                    columns={this.columns}
                    jsonViewerDataKey='source'
                    pagination={null}
                    onScrollEnd={this.handleScrollEnd}
                  />
                ) : (
                  ''
                )}
              </div>
            )}
          </div>
        ) : (
          <div class='empty-chart'>
            {this.emptyText ? (
              this.emptyText
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
