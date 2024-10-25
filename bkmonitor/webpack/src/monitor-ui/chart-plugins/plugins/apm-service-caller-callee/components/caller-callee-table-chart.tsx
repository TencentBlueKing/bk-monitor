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
import { ofType } from 'vue-tsx-support';

import { calculateByRange } from 'monitor-api/modules/apm_metric';
import { Debounce } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { VariablesService } from '../../../utils/variable';
import { CommonSimpleChart } from '../../common-simple-chart';
import { PERSPECTIVE_TYPE, SYMBOL_LIST } from '../utils';
import TabBtnGroup from './common-comp/tab-btn-group';
import MultiViewTable from './multi-view-table';

import type { PanelModel } from '../../../typings';
import type {
  IServiceConfig,
  CallOptions,
  IFilterCondition,
  IFilterData,
  IChartOption,
  IPointTime,
  IDataItem,
} from '../type';

import './caller-callee-table-chart.scss';
interface ICallerCalleeTableChartProps {
  activeKey: string;
  chartPointOption: IChartOption;
  filterData?: IFilterCondition[];
  searchList?: IServiceConfig[];
  panel: PanelModel;
}
interface ICallerCalleeTableChartEvent {
  onCloseTag?: (val: IFilterCondition[]) => void;
  onHandleDetail?: (val: IDataItem) => void;
  onCloseChartPoint?: () => void;
  onDrill?: (val: IFilterCondition) => void;
}
@Component
class CallerCalleeTableChart extends CommonSimpleChart {
  @Prop({ required: true, type: String, default: '' }) activeKey: string;
  @Prop({ type: Object, default: () => {} }) chartPointOption: IChartOption;
  @Prop({ type: Array }) filterData: IFilterCondition[];
  @Prop({ type: Array }) searchList: IServiceConfig[];

  @InjectReactive('callOptions') readonly callOptions!: CallOptions;
  @InjectReactive('filterTags') filterTags: IFilterData;

  tabList = PERSPECTIVE_TYPE;
  activeTabKey = 'single';
  singleChooseField = '';
  chooseList: string[] = [];
  tableColumn = [];
  tableListData = [];
  tableTabData = [];
  tableColData: string[] = [];
  tableLoading = false;
  pointWhere: IFilterCondition[] = [];
  drillWhere: IFilterCondition[] = [];
  pointTime: IPointTime = {};

  @Watch('callOptions', { deep: true })
  onCallOptionsChanges(val) {
    this.tableColData = val.time_shift.map(item => item.alias);
    this.viewOptions?.service_name && this.getPageList();
  }
  /** 点击选择图表中点 */
  @Watch('chartPointOption', { deep: true })
  onChartPointOptionChanges(val) {
    if (val) {
      this.pointWhere = [];
      this.pointTime = {};
      const { dimensions, time } = val;
      Object.keys(dimensions || {}).map(key =>
        this.pointWhere.push({
          key: key,
          method: 'eq',
          value: [dimensions[key]],
          condition: 'and',
        })
      );
      if (time) {
        const endTime = new Date(time).getTime() / 1000;
        const interval = this.commonOptions?.time?.interval || 60;
        const startTime = endTime - interval;
        this.pointTime = { endTime, startTime };
      }
      this.getTableDataList();
    }
  }

  @Watch('activeKey', { immediate: true })
  handlePanelChange(val) {
    const defaultKey = this.filterTags[val].find(item => item.default_group_by_field);
    this.singleChooseField = defaultKey.value;
    this.chooseList = [this.singleChooseField];
    this.activeTabKey = 'single';
    this.tableColumn = [
      {
        label: defaultKey.text,
        prop: defaultKey.value,
      },
    ];
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
  get chooseKeyList() {
    return [
      ...[
        {
          value: 'time',
          text: '时间',
        },
      ],
      ...this.filterTags[this.activeKey],
    ];
  }
  @Debounce(100)
  async getPanelData() {
    console.log('getPanelData', this.chartPointOption);
    this.tableLoading = true;
    this.tableColData = this.callOptions.time_shift.map(item => item.alias);
    this.getPageList();
  }
  /** 获取表格数据 */
  getTableDataList(metric_cal_type = 'request_total') {
    const variablesService = new VariablesService({
      ...this.viewOptions,
      ...this.callOptions,
      ...{ kind: this.activeKey },
    });
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const timeShift = this.getCallTimeShift();
    const newParams = {
      ...variablesService.transformVariables(this.statisticsData.data, {
        ...this.viewOptions,
      }),
      ...{
        group_by: this.chooseList,
        time_shifts: timeShift,
        metric_cal_type,
        baseline: '0s',
        start_time: this.pointTime?.startTime || startTime,
        end_time: this.pointTime?.endTime || endTime,
      },
    };
    newParams.where = [...newParams.where, ...this.callOptions.call_filter, ...this.pointWhere, ...this.drillWhere];
    calculateByRange(newParams)
      .then(res => {
        this.tableLoading = false;
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
      })
      .catch(() => {
        this.tableLoading = false;
      });
  }

  changeTab(id: string) {
    this.activeTabKey = id;
    if (id === 'multiple') {
      this.chooseList = [this.singleChooseField];
      this.tableColumn.map(item => this.chooseList.push(item.value));
    } else {
      const option = this.chooseKeyList.find(item => item.value === this.chooseList[0]);
      this.chooseSingleField(option);
    }
  }
  // 单视角时选择key
  setChooseKey(item) {
    this.singleChooseField = item.value;
    this.tableColumn = [
      {
        label: item.text,
        prop: item.value,
      },
    ];
    this.chooseList = [item.value];
  }
  chooseSingleField(item) {
    this.setChooseKey(item);
    this.tableTabData = [];
    this.getTableDataList();
  }
  // 多视角时选择key
  handleMultiple() {
    this.tableColumn = [];
    this.chooseKeyList.map(item => {
      if (this.chooseList.includes(item.value)) {
        this.tableColumn.push({
          label: item.text,
          prop: item.value,
        });
      }
      return item;
    });
    this.tableTabData = [];
    this.getTableDataList();
  }

  tabChangeHandle(list: string[]) {
    console.log(list, 'list');
    this.tableLoading = true;
    list.map(item => this.getTableDataList(item));
  }
  @Emit('closeTag')
  handleCloseTag(item) {
    return item;
  }
  handleGetKey(key: string) {
    return this.chooseKeyList.find(item => item.value === key).text;
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
      row.dimensions[key] &&
        filter.push({
          key,
          method: 'eq',
          value: [row.dimensions[key]],
          condition: 'and',
        });
    });
    this.drillWhere = filter;
    if (this.activeTabKey === 'multiple') {
      this.chooseList.push(option.value);
      this.handleMultiple();
    } else {
      this.setChooseKey(option);
    }
    this.$emit('drill', filter);
  }

  renderMainList() {
    if (this.isSingleView) {
      return this.chooseKeyList.map(item => (
        <span
          key={item.value}
          class={['aside-item', { active: this.singleChooseField === item.value }]}
          onClick={() => this.chooseSingleField(item)}
        >
          {item.text}
        </span>
      ));
    }
    return (
      <bk-checkbox-group
        v-model={this.chooseList}
        onChange={this.handleMultiple}
      >
        {this.chooseKeyList.map(item => (
          <bk-checkbox
            key={item.value}
            class='aside-item'
            disabled={this.chooseList.length === 1 && this.chooseList.includes(item.value)}
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
      <span key={key}>
        {this.handleGetKey(key)}
        <span class='tag-symbol'>{this.handleOperate('eq')}</span>
        {dimensions[key]}
      </span>
    ));
  }
  /** 关闭图表点的数据 */
  closeChartPoint() {
    this.$emit('closeChartPoint');
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
            <div class='aside-main'>{this.renderMainList()}</div>
          </div>
          <div
            class='layout-main'
            slot='main'
          >
            <div class='layout-main-head'>
              {Object.keys(this.chartPointOption || {}).length > 0 && (
                <bk-tag
                  closable
                  onClose={this.closeChartPoint}
                >
                  {this.handleGetKey('time')}
                  <span class='tag-symbol'>{this.handleOperate('eq')}</span>
                  {`${this.chartPointOption?.time} `}
                  {this.getChartPointDimensionsTxt()}
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
                    {item?.value && (item?.value || []).join('、')}
                  </bk-tag>
                ))}
            </div>
            <div class='layout-main-table'>
              <MultiViewTable
                isLoading={this.tableLoading}
                searchList={this.chooseKeyList}
                supportedCalculationTypes={this.supportedCalculationTypes}
                tableColData={this.tableColData}
                tableColumn={this.tableColumn}
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
export default ofType<ICallerCalleeTableChartProps, ICallerCalleeTableChartEvent>().convert(CallerCalleeTableChart);
