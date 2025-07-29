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
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { simpleServiceList } from 'monitor-api/modules/apm_meta';
import { getFieldOptionValues } from 'monitor-api/modules/apm_metric';
import { copyText } from 'monitor-common/utils/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import DashboardPanel from 'monitor-ui/chart-plugins/components/flex-dashboard-panel';

import { CHART_TYPE, TAB_TABLE_TYPE } from '../utils';
import { formatDateRange } from '../utils';
import TabBtnGroup from './tab-btn-group';

import type { PanelModel } from '../../../typings';
import type { CallOptions, DimensionItem, IColumn, IDataItem, IDimensionChartOpt, IListItem } from '../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './multi-view-table.scss';
interface IMultiViewTableEvent {
  onDimensionKeyChange?: (key: string) => void;
  onDrill?: () => void;
  onShowDetail?: () => void;
  onTabChange?: () => void;
}
interface IMultiViewTableProps {
  activeTabKey?: string;
  dimensionList: DimensionItem[];
  isLoading?: boolean;
  panel: PanelModel;
  resizeStatus?: boolean;
  sidePanelCommonOptions: Partial<CallOptions>;
  supportedCalculationTypes?: IListItem[];
  tableColData: IListItem[];
  tableFilterData: IDataItem;
  tableListData: IDataItem[];
  timeStrShow?: IDataItem;
  totalList?: IDataItem[];
}
@Component({
  name: 'MultiViewTable',
  components: {},
})
export default class MultiViewTable extends tsc<IMultiViewTableProps, IMultiViewTableEvent> {
  @Prop({ type: Array, default: () => [] }) supportedCalculationTypes: IListItem[];
  @Prop({ required: true, type: Array }) dimensionList: DimensionItem[];
  @Prop({ required: true, type: Array }) tableColData: IColumn[];
  @Prop({ required: true, type: Array }) tableListData: IDataItem[];
  @Prop({ required: true, type: Object }) tableFilterData: IDataItem;
  @Prop({ required: true, type: Boolean }) isLoading: boolean;
  @Prop({ required: true, type: Object }) panel: PanelModel;
  @Prop({ required: true, type: Object }) sidePanelCommonOptions: Partial<CallOptions>;
  @Prop({ required: true, type: Array }) totalList: IDataItem[];
  @Prop({ type: String }) activeTabKey: string;
  @Prop({ required: true, type: Boolean }) resizeStatus: boolean;
  @Prop({ type: Object, default: () => {} }) timeStrShow: IDataItem;

  @InjectReactive('dimensionParam') readonly dimensionParam: CallOptions;
  @ProvideReactive('callOptions') callOptions: Partial<CallOptions> = {};
  @ProvideReactive('dimensionChartOpt') dimensionChartOpt: IDimensionChartOpt;
  @ProvideReactive('curDimensionKey') curDimensionKey: string;
  @InjectReactive('viewOptions') viewOptions;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;

  active = 'request';
  cachePanels = TAB_TABLE_TYPE;
  panels = TAB_TABLE_TYPE;
  isShowDetail = false;
  isShowDimension = false;
  chartPanels = CHART_TYPE;
  chartActive = 'caller-pie-chart';
  drillValue = '';
  serviceList = [];
  curRowData = {};
  request = ['request_total'];
  timeout = ['success_rate', 'timeout_rate', 'exception_rate'];
  consuming = ['avg_duration', 'p50_duration', 'p95_duration', 'p99_duration'];
  // 侧滑面板 维度id
  filterDimensionValue = '';
  pagination = {
    current: 1,
    limit: 10,
    limitList: [10, 20, 50],
  };
  tableAppendWidth = 0;
  simpleList = [];
  prefix = ['growth_rates', 'proportions', 'success_rate', 'exception_rate', 'timeout_rate'];
  sortProp: null | string = null;
  sortOrder: 'ascending' | 'descending' | null = null;
  simpleLoading = false;
  filterOpt = {};
  drillFilterData: IDataItem[] = [];
  drillGroupBy: string[] = [];

  created() {
    this.curDimensionKey = 'request_total';
  }
  /** 是否需要展示百分号 */
  hasPrefix(fieldName: string) {
    return this.prefix.some(pre => fieldName.startsWith(pre));
  }

  @Watch('resizeStatus')
  handleResizeStatus() {
    this.tableAppendWidth = this.$refs.tableAppendRef?.offsetParent?.children[0]?.offsetWidth || 0;
  }
  @Watch('sidePanelCommonOptions', { immediate: true })
  handleRawCallOptionsChange() {
    const selectItem = this.dimensionOptions.find(item => item.id === this.filterDimensionValue);
    const list = [];
    for (const [key, val] of Object.entries(selectItem?.dimensions || {})) {
      if (key === 'time') continue;
      if (val !== null) {
        list.push({
          key,
          value: [val],
          method: 'eq',
          condition: 'and',
        });
      }
    }
    this.callOptions = {
      ...this.sidePanelCommonOptions,
      call_filter: [...this.sidePanelCommonOptions.call_filter, ...list],
    };
  }
  @Watch('activeTabKey')
  handleTableData() {
    this.pagination.current = 1;
  }
  @Watch('supportedCalculationTypes', { immediate: true })
  handleCalculationTypesChange(val) {
    const txtVal = {
      avg_duration: '平均耗时',
      p95_duration: 'P95',
      p99_duration: 'P99',
      p50_duration: 'P50',
    };
    this.panels.map(item => {
      if (item.id !== 'request') {
        item.columns = val
          .map(opt => Object.assign(opt, { prop: `${opt.value}_0s`, label: txtVal[opt.value] || opt.text }))
          .filter(key => this[item.id].includes(key.value));
      }
    });
    this.cachePanels = JSON.parse(JSON.stringify(this.panels));
  }

  get dialogTop() {
    return (window.innerHeight - 720) / 2;
  }

  get appName() {
    return this.viewOptions?.app_name;
  }

  get dimensionOptions() {
    if (!this.tableListData?.length) return [];
    const options = new Map();
    for (const item of this.tableListData) {
      const dimensions = item.dimensions;
      const name = this.getDimensionId(dimensions);
      if (!options.has(name)) {
        options.set(name, { name, id: name, dimensions });
      }
    }
    return Array.from(options.values());
  }
  get dimensionPanels() {
    return this.panel?.dimension_panels || [];
  }
  get currentPanels() {
    return this.dimensionPanels.filter(item => item.type === this.chartActive);
  }

  get commonOptions() {
    return this.panel?.options?.common || {};
  }

  get panelInterval() {
    return this.commonOptions?.time?.interval || 60;
  }
  get groupByCalculationTypes() {
    return this.commonOptions?.group_by?.supported_calculation_types;
  }
  get groupByChartLimit() {
    return this.commonOptions?.group_by?.data?.limit || 30;
  }
  get currentKind() {
    return this.dimensionParam?.kind || 'callee';
  }
  /** 对应的字段操作 */
  get supportOperations() {
    return this.commonOptions?.angle[this.currentKind]?.support_operations;
  }

  get perAfterString() {
    const { kind } = this.dimensionParam;
    const after = kind === 'callee' ? this.$t('主调') : this.$t('被调');
    return after;
  }

  @Watch('tableListData', { immediate: true })
  handleListData(_val: IListItem[]) {
    this.filterOpt = {};
    // console.log(val, 'tableListData');
  }

  get showTableList() {
    const { limit, current } = this.pagination;
    const groupByList = this.dimensionList.filter(item => item.active);
    if (this.totalList.length > 0) {
      groupByList.map((item, ind) => {
        Object.assign(this.totalList[0], {
          isTotal: true,
          [item.value]: ind === 0 ? '汇总' : '  ',
        });
      });
    }
    this.tableAppendWidth = this.$refs.tableAppendRef?.offsetParent?.children[0]?.offsetWidth || 0;
    let list = this.tableListData || [];
    if (this.sortProp && this.sortOrder && list.length) {
      list = list.toSorted((a, b) => {
        if (this.sortOrder === 'ascending') {
          return a[this.sortProp] > b[this.sortProp] ? 1 : -1;
        }
        return a[this.sortProp] < b[this.sortProp] ? 1 : -1;
      });
    }
    return list.slice((current - 1) * limit, current * limit);
  }
  mounted() {
    TAB_TABLE_TYPE.find(item => item.id === 'request').handle = this.handleGetDistribution;
    setTimeout(() => this.getServiceList());
    window.addEventListener('resize', this.handleResize);
  }
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize);
  }
  handleResize() {
    this.tableAppendWidth = this.$refs.tableAppendRef?.offsetParent?.children[0]?.offsetWidth || 0;
  }
  async getServiceList() {
    if (!this.appName) return;
    const listData = await simpleServiceList({ app_name: this.appName }).catch(() => []);
    this.serviceList = listData.map(item => item.service_name).sort((a, b) => a.isClick - b.isClick);
  }

  handleGetDistribution() {
    this.isShowDimension = true;
  }
  getDimensionId(dimensions: Record<string, string>) {
    let name = '';
    for (const [key, val] of Object.entries(dimensions)) {
      if (key === 'time') continue;
      const tag = this.dimensionList.find(item => item.value === key);
      name += ` ${tag.text}:${val || '--'} `;
    }
    return name;
  }
  changeTab(id: string) {
    this.active = id;
    this.$emit('tabChange', this[id]);
  }
  changeChartTab(id: string) {
    this.chartActive = id;
  }

  /** 动态处理表格要展示的数据 */
  @Watch('tableColData', { immediate: true })
  handleChangeCol(val: IListItem[]) {
    const key = {
      '1d': '昨天',
      '0s': '当前',
      '1w': '上周',
    };
    for (const { value, text } of val) {
      const name = key[value];
      if (name) {
        key[value] = name;
        continue;
      }
      key[value] = text;
    }
    this.panels = JSON.parse(JSON.stringify(this.cachePanels));
    const panelList = [];
    const keyList = ['0s', ...val.map(item => item.value)];
    const hastCompare = val.length > 0;
    for (const panel of this.panels) {
      const columns = [];
      if (panel.id === 'request') {
        columns.push(
          ...[
            {
              label: this.$t('占比'),
              prop: 'proportions_request_total_0s',
            },
            {
              label: this.$t('当前'),
              prop: 'request_total_0s',
            },
          ]
        );
        for (const { value } of val) {
          columns.push(
            ...[
              {
                label: key[value],
                prop: `request_total_${value}`,
              },
              {
                label: this.$t('波动'),
                prop: `growth_rates_request_total_${value}`,
              },
            ]
          );
        }
      } else if (panel.id === 'timeout') {
        const colList = ['success_rate', 'timeout_rate', 'exception_rate'].filter(Boolean);
        const nameMap = {
          success_rate: this.$t('成功率'),
          timeout_rate: this.$t('超时率'),
          exception_rate: this.$t('异常率'),
        };
        for (const col of colList) {
          for (const name of keyList) {
            columns.push({
              label: (hastCompare ? key[name] : '') + nameMap[col],
              prop: `${col}_${name}`,
            });
            if (name !== '0s') {
              columns.push({
                label: this.$t('波动'),
                prop: `growth_rates_${col}_${name}`,
              });
            }
          }
        }
      } else if (panel.id === 'consuming') {
        const colList = ['avg_duration', 'p50_duration', 'p95_duration', 'p99_duration'].filter(Boolean);
        const nameMap = {
          avg_duration: this.$t('平均耗时'),
          p50_duration: this.$t('P50'),
          p95_duration: this.$t('P95'),
          p99_duration: this.$t('P99'),
        };
        for (const col of colList) {
          for (const name of keyList) {
            columns.push({
              label: (hastCompare ? key[name] : '') + nameMap[col],
              prop: `${col}_${name}`,
            });
            if (name !== '0s') {
              columns.push({
                label: this.$t('波动'),
                prop: `growth_rates_${col}_${name}`,
              });
            }
          }
        }
      }
      panelList.push({
        ...panel,
        columns,
      });
    }
    this.panels = panelList;
    // console.log(this.panels, '---');
  }

  @Emit('showDetail')
  handleShowDetail(row, key) {
    if (!row?.isTotal && key !== 'time' && row[key]) {
      this.isShowDetail = true;
      this.filterDimensionValue = this.getDimensionId(row.dimensions);
      this.handleRawCallOptionsChange();
      this.curRowData = row;
      return { row, key };
    }
  }
  handleFilterChange(id: string) {
    this.filterDimensionValue = id;
    this.handleRawCallOptionsChange();
  }

  handleDimension(row, key) {
    this.isShowDimension = true;
    this.drillFilterData = [];
    this.drillGroupBy = [];
    this.chartActive = 'caller-pie-chart';
    const parts = key.split('_');
    const metricCalType = parts.slice(0, 2).join('_');
    const timeShift = parts.slice(2).join('_');
    const metricCalTypeName = this.groupByCalculationTypes.find(item => item.value === metricCalType)?.text;
    this.dimensionChartOpt = {
      metric_cal_type: metricCalType,
      time_shift: timeShift,
      metric_cal_type_name: metricCalTypeName,
    };
    this.curDimensionKey = metricCalType;
  }

  handleDimensionKeyChange(id) {
    const metricCalTypeName = this.groupByCalculationTypes.find(item => item.value === id)?.text;
    this.$set(this.dimensionChartOpt, 'metric_cal_type', id);
    this.$set(this.dimensionChartOpt, 'metric_cal_type_name', metricCalTypeName);
    this.curDimensionKey = id;
    this.$emit('dimensionKeyChange', { dimension: id });
  }

  pageChange(page) {
    this.pagination.current = page;
  }
  limitChange(limit) {
    this.pageChange(1);
    this.pagination.limit = limit;
  }
  // 下钻选择key值之后的处理
  @Emit('drill')
  chooseSelect(option: IListItem, row: IDataItem) {
    this.drillValue = option.value;
    return { option, row };
  }
  copyValue(text) {
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }
  handleSort({ prop, order }) {
    this.sortProp = prop;
    this.sortOrder = order;
  }

  /** 字段操作 */
  handleFieldOperations(opt: any, row: IDataItem, canClick = true, intersection = '', service = '') {
    const type = opt.value;
    if (!canClick) {
      return;
    }
    const { kind, timeParams, pointTime } = this.dimensionParam;
    /** 是否选中了图表中的某个点 */
    const isHasPointTime = pointTime?.startTime;
    const interval = isHasPointTime ? 60 : 0;
    const from = isHasPointTime ? (timeParams.start_time - interval) * 1000 : this.timeRange[0];
    const to = isHasPointTime ? timeParams.end_time * 1000 : this.timeRange[1];

    const { app_name, service_name } = this.viewOptions;
    /** 主被调 */
    if (type === 'callee') {
      const kindKey = kind === 'caller' ? 'callee' : 'caller';
      const callOptions = {
        kind: kindKey,
        call_filter: [
          {
            key: intersection,
            method: 'eq',
            value: [row[intersection]],
            condition: 'and',
          },
        ],
      };
      window.open(
        location.href.replace(
          location.hash,
          `#/apm/service?filter-app_name=${app_name}&filter-service_name=${service}&dashboardId=service-default-caller_callee&callOptions=${JSON.stringify(callOptions)}&from=${from}&to=${to}`
        )
      );
      return;
    }
    /** Trace */
    if (type === 'trace') {
      const groupBy = this.dimensionParam.group_by.filter(item => opt.tags.includes(item));
      const tagTraceMapping = opt.tag_trace_mapping;
      const filter = {
        kind: tagTraceMapping[kind].value,
        'resource.service.name': [service_name],
      };
      groupBy.map(item => {
        if (row[item]) {
          filter[tagTraceMapping[item].field] = [row[item]];
        }
      });

      const conditionList = Object.keys(filter).map(key => {
        return {
          key,
          operator: 'equal',
          value: filter[key],
        };
      });
      window.open(
        location.href.replace(
          location.hash,
          `#/trace/home?app_name=${app_name}&where=${encodeURIComponent(JSON.stringify(conditionList))}&start_time=${from}&end_time=${to}&sceneMode=span&filterMode=ui`
        )
      );
      return;
    }
    /** 查看 */
    if (type === 'service') {
      window.open(
        location.href.replace(
          location.hash,
          `#/apm/service?filter-app_name=${app_name}&filter-service_name=${row[intersection]}&dashboardId=service-default-caller_callee&from=${from}&to=${to}`
        )
      );
      return;
    }
    /** 拓扑 */
    if (type === 'topo') {
      const serviceName = this.serviceList.find(key => key === row[opt.tags[0]]);
      window.open(
        location.href.replace(
          location.hash,
          `#/apm/service?filter-app_name=${app_name}&filter-service_name=${serviceName || service_name}&dashboardId=service-default-topo&from=${from}&to=${to}`
        )
      );
      return;
    }
  }
  async getSimpleList(field: string, value: string) {
    const { kind } = this.dimensionParam;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    this.simpleLoading = true;
    const data = await getFieldOptionValues({
      app_name: this.appName,
      // 主调 -> 查被调服务候选值
      field: kind === 'caller' ? 'callee_server' : 'caller_server',
      // 使用被调指标
      metric_field: kind === 'caller' ? 'rpc_server_handled_total' : 'rpc_client_handled_total',
      filter_dict: {},
      start_time: startTime,
      end_time: endTime,
      where: [
        {
          key: field,
          method: 'eq',
          value: [value],
          condition: 'and',
        },
      ],
    });
    this.simpleLoading = false;
    this.simpleList = data.map(item => ({
      isClick: this.serviceList.includes(item.value),
      ...item,
    }));
  }
  @Watch('filterOpt', { deep: true })
  handleFilterOpt(_val) {
    // console.log(val, 'val');
  }
  fieldFilterMethod(value, row, column) {
    const { property } = column;
    this.filterOpt[property] = Array.from(new Set([...this.filterOpt[property], value]));
    // console.log(this.filterOpt, 'this.filterOpt-val');
    return row[property] === value;
  }

  // 渲染左侧表格的列
  handleMultiColumn() {
    const groupBy = this.dimensionParam.group_by;
    const set1 = new Set(groupBy);
    const operationCol = (
      <bk-table-column
        width={220}
        scopedSlots={{
          default: ({ row }) => {
            if (row?.isTotal) {
              return;
            }
            return (
              <div class='multi-view-table-link'>
                <bk-dropdown-menu
                  ref='dropdown'
                  ext-cls='drill-down-popover'
                  trigger='click'
                  position-fixed
                >
                  <div
                    class='drill-down-btn'
                    slot='dropdown-trigger'
                  >
                    <span>{this.$t('下钻')}</span>
                    <i class='icon-monitor icon-arrow-down' />
                  </div>
                  <ul
                    class='drill-down-list'
                    slot='dropdown-content'
                  >
                    {this.dimensionList.map(option => {
                      const isActive = this.drillValue === option.value;
                      return (
                        <li
                          key={option.text}
                          class={['drill-down-item', { active: isActive }]}
                          onClick={() => this.chooseSelect(option, row)}
                        >
                          {option.text}
                        </li>
                      );
                    })}
                  </ul>
                </bk-dropdown-menu>
                {this.supportOperations.map(opt => {
                  const intersection = Array.from(new Set(opt.tags.filter(item => set1.has(item)))) || [];
                  const pre = this.dimensionList.find(item => item.value === intersection[0]);
                  const isHas = intersection.length > 0;
                  if (isHas && opt.value === 'callee') {
                    const tips =
                      this.simpleList.length === 0
                        ? this.$t('当前「{preText}」在{perAfterString}分析无调用记录', {
                            preText: pre?.text || '',
                            perAfterString: this.perAfterString,
                          })
                        : this.$t('查看当前「{preText}」在{perAfterString}分析的数据', {
                            preText: pre?.text || '',
                            perAfterString: this.perAfterString,
                          });
                    return (
                      <bk-popover
                        ext-cls='caller-field-popover'
                        placement='top'
                        theme='light'
                        // trigger='click'
                        onShow={() => this.getSimpleList(intersection[0], row[intersection[0]])}
                      >
                        <span class='operation-item'>{opt.text}</span>
                        <div
                          class='simple-list'
                          slot='content'
                        >
                          <span>{tips}</span>
                          <div
                            class='simple-list-item'
                            v-bkloading={{ isLoading: this.simpleLoading, theme: 'primary', size: 'mini' }}
                          >
                            {this.simpleList.map(item => (
                              <div
                                key={item.value}
                                class={['field-item', { disabled: !item.isClick }]}
                                v-bk-tooltips={{
                                  content: this.$t('服务未接入'),
                                  disabled: item.isClick,
                                }}
                                onClick={() =>
                                  this.handleFieldOperations(opt, row, item.isClick, intersection[0], item.value)
                                }
                              >
                                {item.value}
                              </div>
                            ))}
                          </div>
                        </div>
                      </bk-popover>
                    );
                  }
                  if (isHas && ['service', 'topo', 'trace'].includes(opt.value)) {
                    const isClick = this.serviceList.includes(row[opt.tags[0]]);
                    const tipsData = {
                      trace: this.$t('查看关联调用链'),
                      topo: this.$t('跳转到「{intersection}」拓扑页面', {
                        intersection: row[intersection[0]],
                      }),
                      service: this.$t('跳转到「{intersection}」调用分析页面', {
                        intersection: row[intersection[0]],
                      }),
                    };
                    return (
                      <span
                        key={opt.value}
                        class={['operation-item', { disabled: ['service', 'topo'].includes(opt.value) && !isClick }]}
                        v-bk-tooltips={
                          ['service', 'topo'].includes(opt.value)
                            ? {
                                content: !isClick ? this.$t('服务未接入') : tipsData[opt.value],
                              }
                            : { content: tipsData[opt.value] }
                        }
                        onClick={() =>
                          this.handleFieldOperations(
                            opt,
                            row,
                            ['service', 'topo'].includes(opt.value) ? isClick : true,
                            intersection[0]
                          )
                        }
                      >
                        {opt.text}
                      </span>
                    );
                  }
                })}
              </div>
            );
          },
        }}
        label={this.$t('操作')}
      />
    );
    const baseCol = this.dimensionList
      .filter(item => item.active)
      .map(item => {
        const key = (this.tableFilterData[item.value] || []).length;
        this.filterOpt[item.value] = [];
        return (
          <bk-table-column
            key={`${item.value}_${key}`}
            scopedSlots={{
              default: a => {
                const timeTxt = a.row.time ? dayjs.tz(a.row.time * 1000).format('YYYY-MM-DD HH:mm:ss') : '--';
                const txt = item.value === 'time' && !a.row?.isTotal ? timeTxt : a.row[item.value];
                return (
                  <span
                    class={[
                      'multi-view-table-link',
                      { 'block-link': a.row?.isTotal || item.value === 'time' || !a.row[item.value] },
                    ]}
                  >
                    <span
                      class='item-txt'
                      v-bk-overflow-tips
                      onClick={() => this.handleShowDetail(a.row, item.value)}
                    >
                      {txt || '--'}
                    </span>
                    {!a.row?.isTotal && a.row[item.value] && (
                      <i
                        class='icon-monitor icon-mc-copy tab-row-icon'
                        onClick={() => this.copyValue(a.row[item.value])}
                      />
                    )}
                  </span>
                );
              },
            }}
            // filter-method={this.fieldFilterMethod}
            // filters={this.tableFilterData[item.value]}
            label={item.text}
            min-width={120}
            prop={item.value}
          />
        );
      });
    return [baseCol, operationCol];
  }
  /** 检查是否需要保留2位小数 */
  formatToTwoDecimalPlaces(value: number) {
    if (!value) {
      return;
    }
    // 首先检查值是否为数字
    if (typeof value !== 'number') {
      throw new Error('Input must be a number');
    }
    // 将数字转换为字符串并分割为整数部分和小数部分
    const parts = value.toString().split('.');

    // 检查小数部分是否存在以及其长度是否大于2
    if (parts.length > 1 && parts[1].length > 2) {
      // 如果小数部分多于两位，使用 toFixed 方法保留两位小数
      return Number.parseFloat(value.toFixed(2));
    }
    return value;
  }

  renderHeader(h, { column }: any, item: any) {
    const { pointTime } = this.dimensionParam;
    let tips = this.timeStrShow[item.prop.slice(-2)];
    if (pointTime?.startTime) {
      tips = formatDateRange(pointTime?.startTime * 1000, pointTime?.endTime * 1000);
    }
    const showKeys = ['growth_rates', 'proportions', 'p50_duration', 'p95_duration', 'p99_duration'];
    const tipsKey = ['1d', '1w'];
    const hasPrefix = (fieldName: string) => {
      return showKeys.some(pre => fieldName.startsWith(pre));
    };
    const hasTips = (fieldName: string) => {
      return tipsKey.some(pre => fieldName.endsWith(pre));
    };
    return (
      <span class='custom-header-main'>
        <span
          class={[{ 'item-txt': !hasPrefix(item.prop) }, { 'item-txt-no': hasPrefix(item.prop) }]}
          v-bk-overflow-tips
        >
          <span
            class={{ 'custom-header-tips': !hasPrefix(item.prop) && hasTips(item.prop) }}
            v-bk-tooltips={!hasPrefix(item.prop) && hasTips(item.prop) ? { content: tips } : {}}
          >
            {item.label}
          </span>
        </span>
        {!hasPrefix(item.prop) && (
          <i
            class='icon-monitor icon-bingtu tab-row-icon'
            onClick={e => {
              e.stopPropagation();
              this.handleDimension(column, item.prop);
            }}
          />
        )}
      </span>
    );
  }
  // 渲染tab表格的列
  handleMultiTabColumn() {
    const { pointTime } = this.dimensionParam;
    const curColumn = this.panels.find(item => item.id === this.active);
    return (curColumn.columns || []).map(item => (
      <bk-table-column
        key={`${item.prop}_${pointTime?.startTime}`}
        scopedSlots={{
          default: ({ row }) => {
            const txt = this.formatTableValShow(row[item.prop], item.prop);
            return (
              <span
                class={[
                  'multi-view-table-txt',
                  { 'red-txt': item.prop.startsWith('growth_rates') && row[item.prop] > 0 },
                  { 'green-txt': item.prop.startsWith('growth_rates') && row[item.prop] < 0 },
                ]}
              >
                <span
                  class='item-txt'
                  v-bk-overflow-tips
                >
                  {item.prop.startsWith('growth_rates') && row[item.prop] > 0 ? `+${txt}` : txt}
                </span>
                {/* {!row[item.prop] && (
                  <i
                    class='icon-monitor icon-mc-line tab-row-icon'
                    onClick={() => this.handleDimension(row, 'request')}
                  />
                )} */}
              </span>
            );
          },
        }}
        min-width={160}
        prop={item.prop}
        renderHeader={(h, { column, $index }: any) => this.renderHeader(h, { column, $index }, item)}
        sortable='custom'
      />
    ));
  }
  createOption(dimensions: Record<string, string>) {
    return (
      <div class='options-wrapper'>
        {Object.entries(dimensions)
          .map(([key, value]) => {
            if (key === 'time') return undefined;
            const tag = this.dimensionList.find(item => item.value === key);
            return (
              <div
                key={key}
                class='options-wrapper-item'
              >
                <span>
                  {tag.text}:{value || '--'}
                </span>
              </div>
            );
          })
          .filter(Boolean)}
      </div>
    );
  }
  /** 格式化表格里要展示内容 */
  formatTableValShow(val: number, key: string) {
    const txt = this.hasPrefix(key)
      ? val
        ? `${val}%`
        : // ? `${this.formatToTwoDecimalPlaces(val)}%`
          val === 0
          ? `${val}%`
          : '--'
      : // : this.formatToTwoDecimalPlaces(val) || '--';
        val || '--';
    return txt;
  }
  get appendTabWidth() {
    const current = this.panels.find(item => item.id === this.active);
    return this.tableAppendWidth / current.columns.length;
  }
  /** 渲染表格的汇总 */
  renderTableAppend() {
    if (this.totalList.length === 0) {
      return;
    }
    const current = this.panels.find(item => item.id === this.active);

    return current.columns.map(item => {
      const val = this.totalList[0][item.prop];
      const txt = this.formatTableValShow(val, item.prop);
      return (
        <span
          key={item.prop}
          style={{ width: `${this.appendTabWidth}px` }}
          class={[
            'span-append pl-15',
            { 'red-txt': item.prop.startsWith('growth_rates') && val > 0 },
            { 'green-txt': item.prop.startsWith('growth_rates') && val < 0 },
          ]}
        >
          {item.prop.startsWith('growth_rates') && val > 0 ? `+${txt}` : txt}
        </span>
      );
    });
  }
  handleMenuClick(data: IDataItem) {
    const { dimensions, dimensionKey } = data;
    const ind = this.drillGroupBy.indexOf(dimensionKey);
    if (ind !== -1) {
      this.drillGroupBy.splice(ind, 1);
    }
    this.drillGroupBy.push(dimensionKey);

    Object.keys(dimensions || {}).map(key => {
      const ind = this.drillFilterData.findIndex(item => item.key === key);
      /** 图表下钻带有时间特殊处理 */
      if (key === 'time') {
        const startTime = new Date(dimensions[key]).getTime() / 1000;
        const endTime = startTime + this.panelInterval;
        this.dimensionChartOpt.dimensionTime = { start_time: startTime, end_time: endTime };
      }
      if (ind === -1) {
        this.drillFilterData.push({
          condition: 'and',
          key,
          method: 'eq',
          value: [dimensions[key]],
        });
      }
    });
    this.dimensionChartOpt.drillFilterData = this.drillFilterData.filter(item => item.key !== 'time');
    this.dimensionChartOpt.drillGroupBy = this.drillGroupBy;
  }
  getDimensionsName(id: string) {
    const { dimensionList } = this.dimensionParam;
    const info = dimensionList.find(item => item.value === id);
    return info?.text;
  }
  handleCloseTag(tag: { condition: string; key: string; method: string; value: string[] }) {
    const data = this.drillFilterData.filter(item => item.key !== tag.key);
    this.drillGroupBy.splice(this.drillGroupBy.indexOf(tag.key), 1);
    if (tag.key === 'time') {
      this.dimensionChartOpt.dimensionTime = {};
    }
    this.drillFilterData = data;
    this.dimensionChartOpt.drillFilterData = data.filter(item => item.key !== 'time');
    this.dimensionChartOpt.drillGroupBy = this.drillGroupBy;
    this.$emit('dimensionKeyChange', { drillFilterData: this.drillFilterData });
  }

  render() {
    return (
      <div class='multi-view-table-main'>
        <div class='multi-view-table-view'>
          <div class='multi-view-left'>
            {this.dimensionList && (
              <bk-table
                ext-cls='multi-view-table'
                data={this.showTableList}
                header-border={false}
                header-cell-class-name={() => 'multi-table-head'}
                max-height={600}
                outer-border={false}
                virtual-render={this.pagination.limit > 20}
              >
                {this.handleMultiColumn()}
                <div slot='empty' />
                <div
                  class='multi-view-tab-table-append pl-15 bor-bt'
                  slot='append'
                >
                  {this.$t('汇总')}
                </div>
              </bk-table>
            )}
          </div>
          <div class='multi-view-right'>
            <div class='head-tab'>
              <TabBtnGroup
                height={42}
                activeKey={this.active}
                list={this.panels}
                type='tab'
                onChange={this.changeTab}
              />
            </div>
            <div>
              <bk-table
                ref='tabTableRef'
                ext-cls='multi-view-tab-table'
                data={this.showTableList}
                header-border={false}
                header-cell-class-name={() => 'multi-table-tab-head'}
                max-height={600}
                outer-border={false}
                virtual-render={this.pagination.limit > 10}
                on-sort-change={this.handleSort}
              >
                {this.handleMultiTabColumn()}
                <div slot='empty' />
                <div
                  ref='tableAppendRef'
                  class='multi-view-tab-table-append'
                  slot='append'
                >
                  {this.renderTableAppend()}
                </div>
              </bk-table>
            </div>
          </div>
          {this.isLoading ? (
            <TableSkeleton
              class='view-empty-block pt-8'
              type={1}
            />
          ) : (
            this.showTableList.length < 1 && (
              <div class='view-empty-block'>
                <bk-exception
                  scene='part'
                  type='empty'
                >
                  {this.$t('查无数据')}
                </bk-exception>
              </div>
            )
          )}
        </div>
        {this.tableListData?.length > this.pagination.limit && (
          <bk-pagination
            class='mt-8'
            align='right'
            count={this.tableListData.length}
            current={this.pagination.current}
            limit={this.pagination.limit}
            limit-list={this.pagination.limitList}
            show-limit={false}
            size='small'
            show-total-count
            on-change={this.pageChange}
            on-limit-change={this.limitChange}
            {...{ on: { 'update:current': v => (this.pagination.current = v) } }}
          />
        )}
        {/* 维度趋势图侧栏 */}
        <bk-sideslider
          width={640}
          ext-cls='multi-detail-slider'
          isShow={this.isShowDetail}
          quick-close={true}
          title={this.$t('维度趋势图')}
          transfer={true}
          {...{ on: { 'update:isShow': v => (this.isShowDetail = v) } }}
        >
          {this.isShowDetail && (
            <div
              class='content-wrap'
              slot='content'
            >
              <div class='multi-slider-filter'>
                <span class='filter-title'>{this.$t('维度')} ：</span>
                <bk-select
                  class='filter-select'
                  behavior='simplicity'
                  clearable={false}
                  value={this.filterDimensionValue}
                  searchable
                  onChange={this.handleFilterChange}
                >
                  {this.dimensionOptions.map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={option.name}
                    >
                      {this.createOption(option.dimensions)}
                    </bk-option>
                  ))}
                </bk-select>
              </div>
              <div class='multi-slider-chart'>
                <DashboardPanel
                  id={'apm-table-extra_panels'}
                  column={1}
                  panels={this.panel.extra_panels}
                />
              </div>
            </div>
          )}
        </bk-sideslider>
        {/* 维度值分布弹窗 */}
        <bk-dialog
          width={960}
          ext-cls='multi-detail-dialog'
          v-model={this.isShowDimension}
          position={{
            top: this.dialogTop,
          }}
          header-position={'left'}
          show-footer={false}
          theme='primary'
        >
          <div
            class='multi-dialog-header'
            slot='header'
          >
            <span class='head-title'>{this.$t('维度值分布')}</span>
            <TabBtnGroup
              class='multi-dialog-tab'
              activeKey={this.chartActive}
              list={this.chartPanels}
              onChange={this.changeChartTab}
            />
            <bk-select
              class='multi-dialog-select ml10'
              v-model={this.curDimensionKey}
              clearable={false}
              onChange={this.handleDimensionKeyChange}
            >
              {this.groupByCalculationTypes.map(option => (
                <bk-option
                  id={option.value}
                  key={option.value}
                  name={option.text}
                />
              ))}
            </bk-select>
          </div>
          <div class='multi-dialog-content'>
            <span class='multi-tips'>
              {this.$t(`仅展示前 ${this.groupByChartLimit} 条数据`)}
              <span class='multi-tips-more'>
                <i class='icon-monitor icon-mc-mouse mouse-icon' />
                {this.$t('右键更多操作')}
              </span>
            </span>
            <div class='chart-drill-main'>
              {(this.drillFilterData || []).map(item => (
                <bk-tag
                  key={item.id}
                  closable
                  onClose={() => this.handleCloseTag(item)}
                >
                  {this.getDimensionsName(item.key)} <span class='tag-symbol'>=</span>{' '}
                  {(item?.value || []).map(item => (item === '' ? this.$t('- 空 -') : item)).join('、')}
                </bk-tag>
              ))}
            </div>
            {this.isShowDimension && (
              <DashboardPanel
                id={'apm-table-dimension_panels'}
                column={1}
                panels={this.currentPanels}
                onMenuClick={this.handleMenuClick}
              />
            )}
          </div>
        </bk-dialog>
      </div>
    );
  }
}
