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

import { Component, Prop, Emit, InjectReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { calculateByRange } from 'monitor-api/modules/apm_metric';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { VariablesService } from '../../../utils/variable';
import { PERSPECTIVE_TYPE, SYMBOL_LIST } from '../utils';
import TabBtnGroup from './common-comp/tab-btn-group';
import MultiViewTable from './multi-view-table';

import type { PanelModel } from '../../../typings';
import type { IServiceConfig, IDataItem, CallOptions, IFilterCondition, IFilterData, DimensionItem } from '../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './caller-callee-table-chart.scss';
interface ICallerCalleeTableChartProps {
  searchList?: IServiceConfig[];
  tableListData?: IDataItem[];
  tableTabData?: IDataItem[];
  panel: PanelModel;
}
interface ICallerCalleeTableChartEvent {
  onCloseTag?: (val: IFilterCondition[]) => void;
  onHandleDetail?: () => void;
}

const TimeDimension: DimensionItem = {
  value: 'time',
  text: '时间',
  active: false,
};
@Component({
  name: 'CallerCalleeTableChart',
})
export default class CallerCalleeTableChart extends tsc<ICallerCalleeTableChartProps, ICallerCalleeTableChartEvent> {
  @Prop({ required: true, type: Object }) panel: PanelModel;
  @Prop({ required: true, type: String, default: '' }) activeKey: 'callee' | 'caller';
  @Prop({ type: Array }) filterData: IFilterCondition[];
  @Prop({ type: Array }) searchList: IServiceConfig[];

  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('callOptions') readonly callOptions!: CallOptions;
  @InjectReactive('filterTags') filterTags: IFilterData;

  tabList = PERSPECTIVE_TYPE;
  activeTabKey = 'single';
  tableColumn = [];
  tableListData = [];
  tableTabData = [];
  tableColData: string[] = [];

  dimensionList: DimensionItem[] = [];

  get panelCommonOptions() {
    return this.panel.options.common;
  }

  get callTags() {
    if (this.activeKey === 'callee') {
      return this.panelCommonOptions?.angle?.callee?.tags || [];
    }
    return this.panelCommonOptions?.angle?.caller?.tags || [];
  }
  created() {
    this.handlePanelChange();
  }

  @Watch('viewOptions', { deep: true })
  onViewOptionsChanges() {
    this.tableColData = this.callOptions.time_shift.map(item => item.alias);
    this.getPageList();
  }
  @Watch('callOptions', { deep: true })
  onCallOptionsChanges(val) {
    this.tableColData = val.time_shift.map(item => item.alias);
    this.viewOptions?.service_name && this.getPageList();
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
    return (this.filterData || []).filter(item => item.value.length > 0);
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
    const callTimeShift = this.callOptions.time_shift.map(item => item.alias);
    return callTimeShift.length === 2 ? callTimeShift : ['0s', ...callTimeShift];
  }
  getPageList() {
    this.tableTabData = [];
    this.tableListData = [];
    this.getTableDataList();
  }
  /** 获取表格数据 */
  getTableDataList(metric_cal_type = 'request_total') {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const variablesService = new VariablesService({
      ...this.viewOptions,
      ...this.callOptions,
      ...{ kind: this.activeKey },
    });
    const timeShift = this.getCallTimeShift();
    const newParams = {
      ...variablesService.transformVariables(this.statisticsData.data, {
        ...this.viewOptions,
      }),
      ...{
        group_by: this.dimensionList.filter(item => item.active).map(item => item.value),
        time_shifts: timeShift,
        metric_cal_type,
        baseline: '0s',
        start_time: startTime,
        end_time: endTime,
      },
    };
    newParams.where = [...newParams.where, ...this.callOptions.call_filter];
    calculateByRange(newParams).then(res => {
      const newData = (res?.data || []).map(item => {
        const { dimensions, proportions, growth_rates } = item;
        const col = {};
        timeShift.map(key => {
          const baseKey = `${metric_cal_type}_${key}`;
          col[baseKey] = item[key];
          const addToListIfNotEmpty = (source, prefix) => {
            if (Object.keys(source || {}).length > 0) {
              col[`${prefix}_${baseKey}`] = source[key];
            }
          };
          addToListIfNotEmpty(proportions, 'proportions');
          addToListIfNotEmpty(growth_rates, 'growth_rates');
        });
        return Object.assign(item, dimensions, col);
      });
      if (this.tableListData.length === 0) {
        this.tableListData = newData;
      } else {
        this.tableListData.map((item, ind) => Object.assign(item, newData[ind]));
      }
      this.tableTabData = JSON.parse(JSON.stringify(this.tableListData));
    });
  }

  changeTab(id: string) {
    this.activeTabKey = id;
    const activeList = this.dimensionList.filter(item => item.active).map(item => item.value);
    this.handleSelectDimension(this.isSingleView ? activeList.slice(0, 1) : activeList);
  }

  tabChangeHandle(list: string[]) {
    list.map(item => this.getTableDataList(item));
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
  handleDrill(option: DimensionItem) {
    if (this.activeTabKey === 'multiple') {
      const activeList = this.dimensionList.filter(item => item.active).map(item => item.value);
      activeList.push(option.value);
      this.handleSelectDimension(activeList);
    } else {
      this.handleSelectDimension([option.value]);
    }
  }
  handleSelectDimension(selectedList: string[]) {
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
    this.tableTabData = [];
    this.getTableDataList();
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
        onChange={this.handleSelectDimension}
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
              {this.tagFilterList.map(item => (
                <bk-tag
                  key={item.key}
                  closable
                  onClose={() => this.handleCloseTag(item)}
                >
                  {this.handleGetKey(item.key)}
                  <span class='tag-symbol'>{this.handleOperate(item.method)}</span>
                  {item.value.join('、')}
                </bk-tag>
              ))}
            </div>
            <div class='layout-main-table'>
              <MultiViewTable
                dimensionList={this.dimensionList}
                panel={this.panel}
                sidePanelCommonOptions={this.sidePanelCommonOptions}
                supportedCalculationTypes={this.supportedCalculationTypes}
                tableColData={this.tableColData}
                tableListData={this.tableListData}
                tableTabData={this.tableTabData}
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
