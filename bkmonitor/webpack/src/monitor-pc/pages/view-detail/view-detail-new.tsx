/* eslint-disable no-param-reassign */
/* eslint-disable @typescript-eslint/member-ordering */
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
import { Component, InjectReactive, Prop, Provide, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone, random } from '../../../monitor-common/utils';
import AiopsDimensionLint from '../../../monitor-ui/chart-plugins/plugins/aiops-dimension-lint/aiops-dimension-lint';
import PerformanceChart from '../../../monitor-ui/chart-plugins/plugins/performance-chart/performance-chart';
import LineEcharts from '../../../monitor-ui/chart-plugins/plugins/time-series/time-series';
import { PanelModel } from '../../../monitor-ui/chart-plugins/typings/dashboard-panel';
import MonitorDialog from '../../../monitor-ui/monitor-dialog/monitor-dialog.vue';
import MonitorDropdown from '../../components/monitor-dropdown';
import SortButton from '../../components/sort-button/sort-button';
import TimeRange, { TimeRangeType } from '../../components/time-range/time-range';
// import { PanelToolsType } from '../monitor-k8s/typings/panel-tools';
import { DEFAULT_TIME_RANGE, getTimeDisplay } from '../../components/time-range/utils';
import { getDefautTimezone, updateTimezone } from '../../i18n/dayjs';
import { IRefleshItem } from '../monitor-k8s/components/dashboard-tools';
import CompareSelect from '../monitor-k8s/components/panel-tools/compare-select';
import { PanelToolsType } from '../monitor-k8s/typings/panel-tools';
import { IQueryOption } from '../performance/performance-type';

import QueryCriteriaItem from './query-criteria-item.vue';
import { downCsvFile, refleshList, transformSrcData, transformTableDataToCsvStr } from './utils';

import './view-detail-new.scss';
// import { IViewOptions } from '../../../monitor-ui/chart-plugins/typings';

interface IViewConfig {
  config: PanelModel;
  compareValue?: IQueryOption;
}

interface IProps {
  show?: boolean;
  viewConfig?: IViewConfig;
}

@Component
export default class ViewDetailNew extends tsc<IProps> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ default: () => null }) viewConfig: IViewConfig;

  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 刷新间隔
  @ProvideReactive('refleshInterval') refleshInterval = -1;
  // 时区
  @ProvideReactive('timezone') timezone = window.timezone;
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 对比类型
  @ProvideReactive('compareType') compareType: PanelToolsType.CompareId = 'none';
  @InjectReactive('readonly') readonly: boolean;
  // // 视图变量
  // @ProvideReactive('viewOptions') viewOptions: IViewOptions = { };
  // 是否展示复位
  @ProvideReactive('showRestore') showRestore = false;
  // 是否开启（框选/复位）全部操作
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      this.timeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
  }

  /* 刷新时间列表 */
  refleshList: IRefleshItem[] = [];
  /* 右侧数据 */
  rightData = [];
  /* 右侧参数 */
  queryconfig = [];
  /* 对比 */
  compare = {
    type: 'none', // 对比类型 目前只支持 时间对比
    value: [] // 对应对比类型的值
  };
  /* 拖拽数据 */
  drag = { height: 550, minHeight: 300, maxHeight: 550 };
  /* 图表数据 */
  panel = null;
  /* 原始数据 */
  tableThArr = [];
  tableTdArr = [];
  tableData = [];
  loading = false;
  /* 主动刷新图表 */
  chartKey = random(8);
  /* 是否显示右侧 */
  rightShow = true;
  compareTypeList = ['none', 'time', 'metric'];
  cacheTimeRange = [];
  defaultTimezone = '';
  created() {
    this.compareTypeList = [
      'none',
      !window.__BK_WEWEB_DATA__?.lockTimeRange ? 'time' : undefined,
      !this.readonly ? 'metric' : undefined
    ];
    this.refleshList = refleshList;
    this.handleQueryConfig(this.viewConfig);
  }

  mounted() {
    const { clientHeight } = document.body;
    this.drag.height = clientHeight - 173;
    document.addEventListener('keyup', this.handleEsc);
  }

  handleEsc(evt: KeyboardEvent) {
    if (evt.code === 'Escape') this.$emit('close-modal');
  }

  handleBackStep() {
    updateTimezone(this.defaultTimezone);
    this.$emit('close-modal');
  }

  handleTimeRangeChange(val: TimeRangeType) {
    this.timeRange = [...val];
  }
  handleTimezoneChange(timezone: string) {
    this.timezone = timezone;
  }

  handleRefleshChange(val) {
    this.refleshInterval = val;
  }
  handleImmediateReflesh() {
    this.chartKey = random(8);
  }

  /* 处理入参 */
  handleQueryConfig(data) {
    const { compare, tools } = data.compareValue;
    if (compare.type === 'time') {
      this.compare.type = compare.type;
      this.compare.value = compare.value;
      this.compareType = compare.type;
      this.timeOffset = compare.value;
    }
    this.timeRange = tools.timeRange || DEFAULT_TIME_RANGE;
    this.refleshInterval = tools.refleshInterval || -1;
    this.defaultTimezone = window.timezone;
    this.timezone = tools.timezome || getDefautTimezone();
    const { targets } = data.config;
    this.queryconfig = deepClone(targets);
    const str = 'ABCDEFGHIJKLNMOPQRSTUVWXYZ';
    this.rightData = this.queryconfig.map((item, index) => ({
      ...item,
      show: index === 0,
      name: str[index]
    }));
    this.panel = new PanelModel({
      ...this.viewConfig.config,
      options: {
        ...this.viewConfig.config.options,
        legend: {
          displayMode: 'table',
          placement: 'bottom'
        }
      }
    });
  }

  //  图表大小拖拽
  handleMouseDown(e) {
    let { target } = e;

    while (target && target.dataset.tag !== 'resizeTarget') {
      target = target.parentNode;
    }
    const rect = target.getBoundingClientRect();
    document.onselectstart = function () {
      return false;
    };
    document.ondragstart = function () {
      return false;
    };
    const handleMouseMove = event => {
      this.drag.height = Math.max(this.drag.minHeight, event.clientY - rect.top);
    };
    const handleMouseUp = () => {
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.onselectstart = null;
      document.ondragstart = null;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }

  handleMouseMove(e) {
    let { target } = e;
    while (target && target.dataset.tag !== 'resizeTarget') {
      target = target.parentNode;
    }
  }

  /* 获取原始数据 */
  handleGetSeriesData(res) {
    const dataSeries = (res.series || []).map(set => {
      const { datapoints, dimensions, target, ...setData } = set;
      const metric = res.metrics[0];
      return {
        metric,
        dimensions,
        datapoints,
        ...setData,
        target
      };
    });
    const dataList = dataSeries.reduce((data, item) => data.concat(item), []);
    this.handleRawData(dataList);
  }
  handleRawData(data) {
    if (data.length === 0) {
      return;
    }
    const { tableThArr, tableTdArr } = transformSrcData(data);
    this.tableThArr = tableThArr.map(item => ({
      name: item,
      sort: ''
    }));
    this.tableTdArr = tableTdArr;
    this.tableData = [...tableTdArr];
  }

  /* 原始数据排序 */
  handleTableSort(sort, index) {
    this.tableThArr.forEach((item, i) => {
      i !== index && (item.sort = '');
    });
    if (!sort) {
      this.tableData = [...this.tableTdArr];
    } else {
      this.tableData = [...this.tableTdArr].sort((a, b) => {
        const left = a[index].originValue;
        const right = b[index].originValue;
        return sort === 'asc' ? left - right : right - left;
      });
    }
  }
  /* 原始数据排序 */
  handleTableSortAuto(item, index) {
    const old = item.sort;
    if (!old) {
      item.sort = 'asc';
      this.handleTableSort('asc', index);
    } else {
      const newSort = old === 'asc' ? 'desc' : '';
      item.sort = newSort;
      this.handleTableSort(newSort, index);
    }
  }

  /* 时间对比 */
  handleTimeChange(value) {
    this.compare.value = value;
    this.timeOffset = value;
  }
  /* 对比方式 */
  handleTypeChange(value) {
    this.compare.type = value;
    this.compareType = value;
    this.handleTimeChange([]);
  }
  /* 指标对比 todo */
  handleMetricChange(value) {
    this.compare.value = value;
  }

  handleChangeStatus(name) {
    const data = this.rightData.find(item => item.name === name);
    data && (data.show = !data.show);
  }
  handleQueryChange(value, type, groupIndex) {
    if (type === 'method') {
      this.queryconfig[groupIndex].data.query_configs[0].metrics[0].method = value;
    }
    if (type === 'interval') {
      this.queryconfig[groupIndex].data.query_configs[0].interval = value;
    }
    if (type === 'step') {
      this.queryconfig[groupIndex].data.query_configs[0].agg_interval = value;
    }
    this.handleSetPanelParams();
  }
  handleCheckedChange(groupIndex: number, obj, metricDataList: any[]) {
    const key = Object.keys(obj)[0];
    const val = obj[key];
    let hasChanged = false;
    this.queryconfig[groupIndex].data.query_configs.forEach(item => {
      !item.filter_dict && this.$set(item, 'filter_dict', {});
      if (val !== 'all') {
        const metricData = metricDataList.find(
          metric =>
            metric.data_source_label === item.data_source_label &&
            metric.data_type_label === item.data_type_label &&
            metric.result_table_id === item.table &&
            metric.metric_field === item.metrics[0].field
        );
        const groupByList = metricData?.dimensions?.map(item => item.id);
        if (groupByList?.includes(key)) {
          hasChanged = true;
          this.$set(item.filter_dict, key, val);
          item.filter_dict[key] = val;
        }
      } else {
        if (Object.prototype.hasOwnProperty.call(item.filter_dict, key)) {
          hasChanged = true;
          this.$delete(item.filter_dict, key);
        }
      }
    });
    hasChanged && this.handleSetPanelParams();
  }
  handleChangeLoading(status) {
    this.loading = status;
  }

  /* 写入参数 */
  handleSetPanelParams() {
    this.panel.targets.forEach((target, index) => {
      const queryConfigOfParams = this.queryconfig[index].data.query_configs[0];
      const { interval } = queryConfigOfParams;
      const { metrics } = queryConfigOfParams;
      const { filter_dict } = queryConfigOfParams;
      const { functions } = queryConfigOfParams;
      let tempFunctions = functions;
      const tempShiftItem = { id: 'time_shift', params: [{ id: 'n', value: '$time_shift' }] };
      if (!functions?.length) {
        tempFunctions = [tempShiftItem];
      } else {
        const hasTimeShift = functions.some(item => item?.id === 'time_shift');
        if (!hasTimeShift) {
          tempFunctions = [tempShiftItem, ...functions];
        }
      }
      const queryConfig = {
        interval,
        metrics,
        filter_dict,
        functions: tempFunctions
      };
      target.data.query_configs = target.data.query_configs.map(qc => ({
        ...qc,
        ...queryConfig
      }));
    });
    this.chartKey = random(8);
  }

  handleHideRight() {
    this.rightShow = !this.rightShow;
  }

  handleExportCsv() {
    const csvString = transformTableDataToCsvStr(
      this.tableThArr.map(item => item.name),
      this.tableTdArr
    );
    downCsvFile(csvString, this.viewConfig?.config?.title);
  }

  /* 支持的图表 */
  handlePanel2Chart() {
    switch (this.panel.type) {
      case 'aiops-dimension-lint':
        return (
          <AiopsDimensionLint
            panel={this.panel}
            customMenuList={['screenshot', 'set', 'area']}
            onSeriesData={this.handleGetSeriesData}
            showHeaderMoreTool={true}
            needLegend
          ></AiopsDimensionLint>
        );
      case 'performance-chart':
        return (
          <PerformanceChart
            panel={this.panel}
            customMenuList={['screenshot', 'set', 'area']}
            onSeriesData={this.handleGetSeriesData}
            showHeaderMoreTool={true}
          />
        );
      case 'graph':
      default:
        return (
          <LineEcharts
            // onLoading={this.handleChangeLoading}
            panel={this.panel}
            customMenuList={['screenshot', 'set', 'area']}
            onSeriesData={this.handleGetSeriesData}
            showHeaderMoreTool={true}
            // onFullScreen={this.handleFullScreen}
            // onCollectChart={this.handleCollectChart}
            // onDimensionsOfSeries={this.handleDimensionsOfSeries}
          />
        );
    }
  }

  render() {
    return (
      <div class='view-detail-wrap-component'>
        <MonitorDialog
          class='view-detail-wrap-component-dialog'
          value={this.show}
          append-to-body={true}
          full-screen={true}
          need-footer={false}
          need-header={true}
          header-theme={'header-bar'}
          title={this.$t('查看大图')}
          before-close={this.handleBackStep}
        >
          <div class='view-detail'>
            <div class='view-box'>
              {/* 头部工具栏 */}
              <div class='view-box-header'>
                <div class={['view-box-header-left', { 'show-right': this.rightShow }]}>
                  <div class='header-left-compare-panel'>
                    {/* 对比 */}
                    <div class='compare-panel-left'>
                      <CompareSelect
                        needMetricSelect={true}
                        type={this.compare.type as any}
                        compareListEnable={this.compareTypeList as any}
                        panel={null}
                        zIndex={4999}
                        timeValue={this.compare.type === 'time' ? this.compare.value : undefined}
                        onTimeChange={this.handleTimeChange}
                        onTypeChange={this.handleTypeChange}
                        onMetricChange={this.handleMetricChange}
                      ></CompareSelect>
                    </div>
                    {/* 时间工具栏 */}
                    <div class='compare-panel-right'>
                      <span class='margin-left-auto'></span>
                      {window.__BK_WEWEB_DATA__?.lockTimeRange ? (
                        <span class='dashboard-tools-timerange'>{getTimeDisplay(this.timeRange)}</span>
                      ) : (
                        <TimeRange
                          class='dashboard-tools-timerange'
                          value={this.timeRange}
                          timezone={this.timezone}
                          onChange={this.handleTimeRangeChange}
                          onTimezoneChange={this.handleTimezoneChange}
                        />
                      )}
                      <MonitorDropdown
                        icon='icon-zidongshuaxin'
                        class='dashboard-tools-interval'
                        value={this.refleshInterval}
                        text-active={this.refleshInterval !== -1}
                        on-on-icon-click={this.handleImmediateReflesh}
                        on-change={this.handleRefleshChange}
                        isRefleshInterval={true}
                        list={this.refleshList}
                      />
                    </div>
                  </div>
                </div>
                <div class={['right-title', { 'right-title-active': !this.rightShow }]}>
                  <i
                    class={['icon-monitor icon-double-up', { 'icon-active': !this.rightShow }]}
                    onClick={this.handleHideRight}
                  ></i>
                  {this.rightShow && <span>{this.$t('设置')}</span>}
                </div>
              </div>
              {/* 图表及参数区域 */}
              <div class='view-box-content'>
                {/* 图表区域 */}
                <div class={['box-left', { 'box-left-active': !this.rightShow }]}>
                  <div
                    class='box-left-chart'
                    data-tag='resizeTarget'
                    style={{ height: `${this.drag.height}px` }}
                  >
                    <div
                      style={{ height: `${this.drag.height - 20}px` }}
                      key={this.chartKey}
                    >
                      {!!this.panel && this.handlePanel2Chart()}
                    </div>
                    <div
                      class='chart-drag'
                      onMousedown={this.handleMouseDown}
                      onMousemove={this.handleMouseMove}
                    ></div>
                  </div>
                  <div class='box-left-source'>
                    <div class='source-title'>
                      <span>{this.$t('原始数据')}</span>
                      <span class='title-count'>
                        {this.$t('共')}
                        {this.tableData?.length || 0}
                        {this.$t('条数据')}
                      </span>
                      <bk-button
                        class='export-csv-btn'
                        size='small'
                        onClick={this.handleExportCsv}
                      >
                        {this.$t('导出CSV')}
                      </bk-button>
                    </div>
                    <div class='source-content'>
                      <table
                        cellspacing='0'
                        cellpadding='0'
                        border='0'
                        style='width: 100%'
                      >
                        <thead>
                          <tr class='table-head'>
                            {this.tableThArr.map((item, index) => (
                              <th
                                class='table-content'
                                key={index}
                              >
                                <div
                                  class='table-item sort-handle'
                                  style={index === 0 ? 'text-align: left' : ''}
                                  onClick={() => this.handleTableSortAuto(item, index)}
                                >
                                  <span class='table-header'>
                                    {item.name}
                                    <SortButton
                                      class='sort-btn'
                                      v-model={item.sort}
                                      on-change={() => this.handleTableSort(item.sort, index)}
                                    ></SortButton>
                                  </span>
                                </div>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {this.tableData.map((row, index) => (
                            <tr key={index}>
                              {row.map((item, tdIndex) => (
                                <td
                                  class='table-content'
                                  key={tdIndex}
                                >
                                  <div
                                    class='table-item'
                                    style={tdIndex === 0 ? 'text-align: left' : ''}
                                  >
                                    {item.value === null ? '--' : item.value}
                                    {tdIndex > 0 && (item.max || item.min) && (
                                      <img
                                        alt=''
                                        class='item-max-min'
                                        // eslint-disable-next-line @typescript-eslint/no-require-imports
                                        src={require(`../../static/images/svg/${item.min ? 'min.svg' : 'max.svg'}`)}
                                      ></img>
                                    )}
                                  </div>
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
                {/* 参数区域 */}
                <div
                  class='box-right'
                  style={!this.rightShow && 'display: none'}
                >
                  {this.rightData.map((item, index) => (
                    <QueryCriteriaItem
                      key={index}
                      query-config={item}
                      group-index={index}
                      compare-value={{
                        tools: {
                          timeRange: this.timeRange
                        }
                      }}
                      on-change-status={this.handleChangeStatus}
                      on-query-change={this.handleQueryChange}
                      on-checked-change={this.handleCheckedChange}
                      on-change-loading={this.handleChangeLoading}
                    ></QueryCriteriaItem>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </MonitorDialog>
      </div>
    );
  }
}
