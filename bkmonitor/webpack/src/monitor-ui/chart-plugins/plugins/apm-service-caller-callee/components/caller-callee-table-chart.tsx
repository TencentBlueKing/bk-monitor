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

import { Component, Emit, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { calculateByRange } from 'monitor-api/modules/apm_metric';
import { Debounce } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { timeOffsetDateFormat } from 'monitor-pc/pages/monitor-k8s/components/group-compare-select/utils';

import { replaceRegexWhere } from '../../../utils/method';
import { VariablesService } from '../../../utils/variable';
import { CommonSimpleChart } from '../../common-simple-chart';
import { PERSPECTIVE_TYPE, SYMBOL_LIST } from '../utils';
import MultiViewTable from './multi-view-table';
import TabBtnGroup from './tab-btn-group';

import type { PanelModel } from '../../../typings';
import type {
  CallOptions,
  DimensionItem,
  IChartOption,
  IDataItem,
  IFilterCondition,
  IFilterData,
  IListItem,
  IPointTime,
  IServiceConfig,
} from '../type';

import './caller-callee-table-chart.scss';
interface ICallerCalleeTableChartEvent {
  onCloseChartPoint?: () => void;
  onCloseTag?: (val: IFilterCondition) => void;
  onDrill?: (val: IFilterCondition[]) => void;
  onHandleDetail?: (val: IDataItem) => void;
}
interface ICallerCalleeTableChartProps {
  activeKey: string;
  chartPointOption: IChartOption;
  filterData?: IFilterCondition[];
  panel: PanelModel;
  searchList?: IServiceConfig[];
  timeStrShow?: IDataItem;
}
const TimeDimension: DimensionItem = {
  value: 'time',
  text: '时间',
  active: false,
};

@Component
class CallerCalleeTableChart extends CommonSimpleChart {
  @Prop({ required: true, type: String, default: '' }) activeKey: string;
  @Prop({ type: Object, default: () => {} }) chartPointOption: IChartOption;
  @Prop({ type: Array }) filterData: IFilterCondition[];
  @Prop({ type: Array }) searchList: IServiceConfig[];
  @Prop({ type: Object, default: () => {} }) timeStrShow: IDataItem;

  @InjectReactive('callOptions') readonly callOptions!: CallOptions;
  @InjectReactive('filterTags') filterTags: IFilterData;
  @ProvideReactive('dimensionParam') dimensionParam: Partial<CallOptions> = {};

  tabList = PERSPECTIVE_TYPE;
  activeTabKey = 'single';
  tableColumn = [];
  tableListData = [];
  tableTabData = {};
  tableColData: IListItem[] = [];
  tableLoading = false;
  pointWhere: IFilterCondition[] = [];
  drillWhere: IFilterCondition[] = [];
  pointTime: IPointTime = {};
  dimensionList: DimensionItem[] = [];
  totalListData = [];
  tableTabList: string[] = ['request_total'];
  resizeStatus = false;
  get panelCommonOptions() {
    return this.panel.options.common;
  }

  get callTags() {
    if (this.activeKey === 'callee') {
      return this.panelCommonOptions?.angle?.callee?.tags || [];
    }
    return this.panelCommonOptions?.angle?.caller?.tags || [];
  }
  @Watch('panel', { immediate: true })
  handlePageChange() {
    this.dimensionParam = structuredClone(this.callOptions);
  }

  @Watch('$route.query')
  handleRoute(val) {
    if (val?.callOptions) {
      const callOptions = JSON.parse(val.callOptions);
      if (callOptions?.perspective_group_by) {
        this.dimensionList.map(item => (item.active = callOptions.perspective_group_by.includes(item.value)));
      }
      callOptions?.perspective_type && this.changeTab(callOptions.perspective_type);
    }
  }

  @Watch('dimensionList', { immediate: true })
  handleDimensionListChange(val) {
    this.dimensionParam = {
      ...this.dimensionParam,
      group_by: val.filter(item => item.active).map(item => item.value),
      dimensionList: structuredClone(val),
    };
  }
  @Watch('tagFilterList', { immediate: true })
  handleTagFilterList(val) {
    this.dimensionParam = {
      ...this.dimensionParam,
      group_by: val.filter(item => item.active).map(item => item.value),
      dimensionList: structuredClone(val),
    };
  }

  handleDrillDownList() {
    const keys = this.tagFilterList.map(item => item.key);
    const data = structuredClone(this.dimensionList);
    return data.map(item => {
      return {
        id: item.id,
        name: item.text,
        disabled: keys.includes(item.id),
      };
    });
  }

  created() {
    this.handlePanelChange();
  }
  @Watch('callOptions', { deep: true })
  onCallOptionsChanges(val) {
    this.dimensionParam = {
      ...structuredClone(val),
      group_by: this.dimensionList.filter(item => item.active).map(item => item.value),
    };
    this.viewOptions?.service_name && this.getPanelData();
  }
  /** 点击选择图表中点 */
  @Watch('chartPointOption')
  onChartPointOptionChanges(val, oldVal) {
    if (val && val?.time !== oldVal?.time) {
      this.pointWhere = [];
      this.pointTime = {};
      const { dimensions, time, interval } = val;
      Object.keys(dimensions || {}).map(key =>
        this.pointWhere.push({
          key: key,
          method: 'eq',
          value: [dimensions[key]],
          condition: 'and',
        })
      );
      if (time) {
        const endTime = new Date(time).getTime() / 1000 + 60;
        const intervalNum = interval || this.commonOptions?.time?.interval || 60;
        const startTime = endTime - intervalNum;
        this.pointTime = { endTime, startTime };
      }
      this.getPageList();
    }
    this.dimensionParam = { ...this.dimensionParam, pointTime: this.pointTime };
  }

  @Watch('activeKey')
  handlePanelChange() {
    this.activeTabKey = 'single';
    this.dimensionList = [
      { ...TimeDimension },
      ...this.callTags.map(item => ({ value: item.value, text: item.text, active: !!item.default_group_by_field })),
    ];
  }

  /** 是否为单视图 */
  get isSingleView() {
    return this.activeTabKey === 'single';
  }

  get commonOptions() {
    return this.panel?.options?.common || {};
  }

  get statisticsData() {
    return this.commonOptions?.statistics || {};
  }

  get supportedCalculationTypes() {
    return this.statisticsData.supported_calculation_types;
  }

  get tagFilterList() {
    return (this.filterData || []).filter(item => item.value.length > 0) || [];
  }

  get sidePanelCommonOptions(): Partial<CallOptions> {
    const angel = this.commonOptions?.angle || {};
    const options = this.activeKey === 'caller' ? angel.caller : angel.callee;
    return {
      server: options.server,
      ...options?.metrics,
      call_filter: [...this.callOptions.call_filter],
    };
  }

  getCallTimeShift() {
    const callTimeShift = this.callOptions.time_shift;
    return callTimeShift.length === 2 ? callTimeShift : ['0s', ...callTimeShift];
  }
  getPageList() {
    this.tableLoading = true;
    this.handleClearData();
    this.tableTabList.map(item => {
      this.getTableDataList(false, item);
      this.getTableDataList(true, item);
    });
  }
  @Debounce(100)
  async getPanelData() {
    this.tableListData = [];
    if (!(await this.beforeGetPanelData())) {
      return;
    }
    this.unregisterObserver();
    this.tableColData = this.callOptions.time_shift.map(item => ({
      value: item,
      text: timeOffsetDateFormat(item),
    }));
    this.getPageList();
  }
  transformDimensionToKey(dimensions: Record<string, any>) {
    const keys = Object.keys(dimensions || []).sort();
    if (keys.length === 0) {
      return '';
    }
    let str = '';
    for (const key of keys) {
      str += `${key}:${dimensions[key]}|`;
    }
    return str;
  }
  /** 获取表格数据 */
  getTableDataList(isTotal = false, metric_cal_type = 'request_total') {
    const variablesService = new VariablesService({
      ...this.viewOptions,
      ...this.callOptions,
      ...{ kind: this.activeKey },
    });
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const timeShift = this.getCallTimeShift();
    const timeParams = {
      start_time: this.pointTime?.startTime || startTime,
      end_time: this.pointTime?.endTime || endTime,
    };
    const groupBy = this.dimensionList.filter(item => item.active).map(item => item.value);
    const newParams = {
      ...variablesService.transformVariables(this.statisticsData.data, {
        ...this.viewOptions,
      }),
      ...{
        group_by: isTotal ? [] : groupBy,
        time_shifts: timeShift,
        metric_cal_type,
        baseline: '0s',
        ...timeParams,
        // start_time: this.pointTime?.startTime || startTime,
        // end_time: this.pointTime?.endTime || endTime,
      },
    };
    newParams.where = replaceRegexWhere([
      ...newParams.where,
      ...this.callOptions.call_filter.filter(item => item.key !== 'time'),
      ...this.pointWhere,
      // ...this.drillWhere,
    ]);
    this.dimensionParam = { ...this.dimensionParam, whereParams: newParams.where, timeParams };
    calculateByRange(newParams)
      .then(res => {
        this.tableLoading = false;
        let list = (isTotal ? this.totalListData?.slice() : this.tableListData?.slice()) || [];
        if (!list.length) {
          list = res?.data || [];
        }
        const tableData = [];
        const resetColItem = (item, rawItem, key = '', dimensions = {}) => {
          const { proportions, growth_rates } = rawItem || {};
          const col = {
            key,
          };
          [...timeShift, ...['0s']].map(key => {
            const baseKey = `${metric_cal_type}_${key}`;
            col[baseKey] = rawItem[key];
            const addToListIfNotEmpty = (source, prefix) => {
              if (Object.keys(source || {}).length > 0) {
                col[`${prefix}_${baseKey}`] = source[key];
              }
            };
            addToListIfNotEmpty(proportions, 'proportions');
            addToListIfNotEmpty(growth_rates, 'growth_rates');
          });
          return {
            ...item,
            ...dimensions,
            ...col,
          };
        };
        for (const item of list) {
          if (!isTotal) {
            const { dimensions } = item;
            const key = item.key || this.transformDimensionToKey(dimensions);
            const rawItem = res?.data?.find(set => this.transformDimensionToKey(set.dimensions) === key);
            if (metric_cal_type === 'timeout_rate') {
              console.info(item['0s'], rawItem['0s']);
            }
            tableData.push(resetColItem(item, rawItem, key, dimensions));
          } else {
            tableData.push(resetColItem(item, res?.data[0]));
          }
        }
        if (!isTotal) {
          this.tableListData = tableData;
          const list = {};
          // biome-ignore lint/complexity/noForEach: <explanation>
          groupBy.forEach(item => {
            const uniqueSet = new Map();
            // biome-ignore lint/complexity/noForEach: <explanation>
            this.tableListData.forEach(row => {
              const value = row[item] !== undefined ? row[item] : '--';
              uniqueSet.set(value, { text: value, value: row[item] });
            });

            list[item] = Array.from(uniqueSet.values());
          });
          /** 表头需要过滤的值 */
          this.tableTabData = list;
          return;
        }
        this.totalListData = tableData;
      })
      .catch(() => {
        this.tableLoading = false;
      });
  }

  handleClearData() {
    this.tableListData = [];
    this.tableTabData = {};
    this.totalListData = [];
  }

  changeTab(id: string) {
    this.activeTabKey = id;
    const activeList = this.dimensionList.filter(item => item.active).map(item => item.value);
    this.handleSelectDimension(this.isSingleView ? activeList.slice(0, 1) : activeList);
    this.handleClearData();
    this.getPanelData();
  }
  handleDataFormat(keyList: string, data: string, field: string[]) {
    this[data] = [...(this[keyList][field[0]] || [])];
    // biome-ignore lint/complexity/noForEach: <explanation>
    field.slice(1).forEach(val => {
      this[data] = this[data].map((item, index) => ({
        ...item,
        ...this[keyList][val]?.[index],
      }));
    });
  }
  // 合并数组
  mergeArrays(data) {
    const keys = Object.keys(data);
    const result = [];

    // 假定每个数组的长度相同
    const length = data[keys[0]]?.length || 0;

    for (let i = 0; i < length; i++) {
      const mergedObject: IDataItem = {};

      for (const key of keys) {
        const currentObject = data[key][i] || {};
        for (const [prop, value] of Object.entries(currentObject)) {
          if (!['dimensions', 'growth_rates', 'proportions'].includes(prop)) {
            // 以第一个对象的 dimensions 为准
            if (value !== 'undefined' && value !== null && value !== '') {
              mergedObject[prop] = value;
            }
          } else if (!mergedObject.dimensions) {
            mergedObject.dimensions = value;
          }
        }
      }

      result.push(mergedObject);
    }

    return result;
  }
  @Debounce(10)
  tabChangeHandle(list: string[]) {
    this.tableTabList = list;
    list.map(item => {
      this.getTableDataList(false, item);
      this.getTableDataList(true, item);
    });
  }
  @Emit('closeTag')
  handleCloseTag(item) {
    return item;
  }
  handleGetKey(key: string) {
    return this.dimensionList.find(item => item.value === key).text;
  }
  handleOperate(key: string) {
    return SYMBOL_LIST.find(item => item.value === key).label;
  }

  @Emit('handleDetail')
  handleShowDetail({ row, key }) {
    return { row, key };
  }
  // 下钻handle
  handleDrill({ option, row }) {
    const filter = [];
    Object.keys(row?.dimensions || {}).map(key => {
      row.dimensions[key] !== 'null' &&
        filter.push({
          key,
          method: 'eq',
          value: [row.dimensions[key]],
          condition: 'and',
        });
    });
    this.drillWhere = filter;
    if (this.activeTabKey === 'multiple') {
      const activeList = this.dimensionList.filter(item => item.active).map(item => item.value);
      activeList.push(option.value);
      this.handleSelectDimension(activeList, true);
    } else {
      this.handleSelectDimension([option.value], true);
    }
    this.$emit('drill', filter);
  }
  handleSelectDimension(selectedList: string[], isDrill = false) {
    const tableColumn = [];
    this.dimensionList = this.dimensionList.map(item => {
      const active = selectedList.includes(item.value);
      if (active) {
        tableColumn.push({
          label: item.text,
          prop: item.value,
        });
      }
      return {
        ...item,
        active,
      };
    });

    this.tableColumn = tableColumn;
    this.handleClearData();
    !isDrill && this.getPageList();
  }
  renderDimensionList() {
    const activeList = this.dimensionList.filter(item => item.active).map(item => item.value);
    if (this.isSingleView) {
      return this.dimensionList.map(item => (
        <span
          key={item.value}
          class={['aside-item', { active: item.active }]}
          onClick={() => item.value !== activeList[0] && this.handleSelectDimension([item.value])}
        >
          {item.text}
        </span>
      ));
    }
    return (
      <bk-checkbox-group
        value={activeList}
        onChange={v => this.handleSelectDimension(v)}
      >
        {this.dimensionList.map(item => (
          <bk-checkbox
            key={item.value}
            class='aside-item'
            disabled={activeList.length === 1 && item.active}
            value={item.value}
          >
            {item.text}
          </bk-checkbox>
        ))}
      </bk-checkbox-group>
    );
  }
  getChartPointDimensionsTxt() {
    const { dimensions } = this.chartPointOption;
    return Object.keys(dimensions || {}).map(key => (
      <span
        key={key}
        style='display: inline-flex; margin-left: 4px'
      >
        {this.handleGetKey(key)}
        <span class='tag-symbol'>{this.handleOperate('eq')}</span>
        {dimensions[key] === '' ? this.$t('- 空 -') : dimensions[key]}
      </span>
    ));
  }
  /** 关闭图表点的数据 */
  closeChartPoint() {
    this.$emit('closeChartPoint');
  }
  handleResizeTab(status: boolean) {
    this.resizeStatus = status;
  }
  dimensionKeyChange(data) {
    this.dimensionParam = { ...this.dimensionParam, ...data };
  }

  render() {
    return (
      <div class='caller-callee-tab-table-view'>
        <bk-resize-layout
          class='tab-table-view-layout'
          initial-divide={160}
          max={400}
          min={160}
          placement='left'
          collapsible
          on-collapse-change={this.handleResizeTab}
        >
          <div
            class='layout-aside'
            slot='aside'
          >
            <div class='aside-head'>
              <TabBtnGroup
                height={26}
                activeKey={this.activeTabKey}
                list={this.tabList}
                type='block'
                onChange={this.changeTab}
              />
            </div>
            <div class='aside-main'>{this.renderDimensionList()}</div>
          </div>
          <div
            class='layout-main'
            slot='main'
          >
            <div class='layout-main-head'>
              {Object.keys(this.chartPointOption || {}).length > 0 && (
                <bk-tag
                  class='chart-point-tag'
                  closable
                  onClose={this.closeChartPoint}
                >
                  {this.handleGetKey('time')}
                  <span class='tag-symbol'>{this.handleOperate('eq')}</span>
                  {`${this.chartPointOption?.time} `}
                  <span class='tag-symbol-txt'>{this.getChartPointDimensionsTxt()}</span>
                </bk-tag>
              )}
              {this.tagFilterList.length > 0 &&
                (this.tagFilterList || []).map(item => (
                  <bk-tag
                    key={item.key}
                    closable
                    onClose={() => this.handleCloseTag(item)}
                  >
                    {this.handleGetKey(item.key)}
                    <span class='tag-symbol'>{this.handleOperate(item.method)}</span>
                    {item?.value &&
                      (item.key === 'time'
                        ? (item.value || []).map(val => dayjs.tz(Number(val) * 1000).format('YYYY-MM-DD HH:mm:ss'))
                        : (item?.value || []).map(item => (item === '' ? this.$t('- 空 -') : item)).join('、'))}
                  </bk-tag>
                ))}
            </div>
            <div class='layout-main-table'>
              <MultiViewTable
                activeTabKey={this.activeTabKey}
                dimensionList={this.dimensionList}
                isLoading={this.tableLoading}
                panel={this.panel}
                resizeStatus={this.resizeStatus}
                sidePanelCommonOptions={this.sidePanelCommonOptions}
                supportedCalculationTypes={this.supportedCalculationTypes}
                tableColData={this.tableColData}
                tableFilterData={this.tableTabData}
                tableListData={this.tableListData}
                timeStrShow={this.timeStrShow}
                totalList={this.totalListData}
                onDimensionKeyChange={this.dimensionKeyChange}
                onDrill={this.handleDrill}
                onShowDetail={this.handleShowDetail}
                onTabChange={this.tabChangeHandle}
              />
            </div>
          </div>
        </bk-resize-layout>
      </div>
    );
  }
}
export default ofType<ICallerCalleeTableChartProps, ICallerCalleeTableChartEvent>().convert(CallerCalleeTableChart);
