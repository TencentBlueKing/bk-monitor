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

import { Component, Prop, Watch, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from 'monitor-common/utils/utils';
import DashboardPanel from 'monitor-ui/chart-plugins/components/dashboard-panel';

import CallerBarChart from '../chart/caller-bar-chart';
import CallerPieChart from '../chart/caller-pie-chart';
import { TAB_TABLE_TYPE, CHART_TYPE, LIMIT_TYPE_LIST } from '../utils';
import TabBtnGroup from './common-comp/tab-btn-group';

import type { IServiceConfig, IColumn, IDataItem, IListItem } from '../type';

import './multi-view-table.scss';
interface IMultiViewTableProps {
  tableColumn: IColumn[];
  tableColData: IColumn[];
  searchList: IServiceConfig[];
  tableListData: IDataItem[];
  tableTabData: IDataItem[];
}
interface IMultiViewTableEvent {
  onShowDetail?: () => void;
  onDrill?: () => void;
}
@Component({
  name: 'MultiViewTable',
  components: {},
})
export default class MultiViewTable extends tsc<IMultiViewTableProps, IMultiViewTableEvent> {
  @Prop({ type: Array, default: () => [] }) supportedCalculationTypes: IListItem[];
  @Prop({ required: true, type: Array }) tableColumn: IColumn[];
  @Prop({ required: true, type: Array }) tableColData: IColumn[];
  @Prop({ required: true, type: Array }) searchList: IServiceConfig[];
  @Prop({ required: true, type: Array }) tableListData: IDataItem[];
  @Prop({ required: true, type: Array }) tableTabData: IDataItem[];
  active = 'request';
  cachePanels = TAB_TABLE_TYPE;
  panels = TAB_TABLE_TYPE;
  isShowDetail = false;
  isShowDimension = false;
  chartPanels = CHART_TYPE;
  chartActive = 'caller-pie-chart';
  dimensionValue = 1;
  dashboardPanels = [];
  drillValue = '';
  column = [
    {
      label: '被调 IP',
      prop: 'caller_service',
    },
    {
      label: '被调接口',
      prop: 'formal',
      props: {},
    },
  ];
  curDimensionKey = '';
  curRowData = {};
  request = ['request_total'];
  timeout = ['success_rate', 'timeout_rate', 'exception_rate'];
  consuming = ['avg_duration', 'p50_duration', 'p95_duration', 'p99_duration'];

  @Watch('supportedCalculationTypes', { immediate: true })
  handlePanelChange(val) {
    const txtVal = {
      avg_duration: 'AVG',
      p95_duration: 'p95',
      p99_duration: 'p99',
      p50_duration: 'p50',
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

  get dialogSelectList() {
    return LIMIT_TYPE_LIST;
  }
  get dialogPanel() {
    return {};
  }
  mounted() {
    TAB_TABLE_TYPE.find(item => item.id === 'request').handle = this.handleGetDistribution;
  }
  handleGetDistribution() {
    this.isShowDimension = true;
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
  handleChangeCol(val) {
    const key = {
      '1d': '昨天',
      '0s': '当前',
      '1w': '上周',
    };
    const mapList = {};
    val.map(item => (mapList[item] = key[item] || item));
    this.panels = JSON.parse(JSON.stringify(this.cachePanels));
    // biome-ignore lint/complexity/noForEach: <explanation>
    this.panels.forEach(item => {
      if (item.id === 'request' && val.length > 0) {
        item.columns = item.columns.slice(1);
      }
      item.columns = item.columns.flatMap(col => {
        let defaultCol = [];
        const isRequest = item.id !== 'request';
        const baseKey = isRequest ? col.value : 'request_total';
        defaultCol = [{ label: this.$t('波动'), prop: `growth_rates_${baseKey}_${val[0]}` }];
        const cache = val.length === 1 ? ['0s', ...val] : val;
        const additionalCols = cache.map((v, ind) => ({
          label: isRequest ? `${key[v] || v}${ind === 0 && key[v] ? col.label || '' : ''}` : `${key[v] || v}`,
          prop: `${baseKey}_${v}`,
        }));
        defaultCol = isRequest ? [...additionalCols, ...defaultCol] : [...additionalCols, col, ...defaultCol];
        return val.length > 0 ? defaultCol : col;
      });
    });
    console.log(this.panels);
  }

  @Emit('showDetail')
  handleShowDetail(row, key) {
    if (row[key]) {
      this.isShowDetail = true;
      this.curRowData = row;
      return { row, key };
    }
  }
  handleFilterChange() {}

  handleDimension(row, key) {
    this.isShowDimension = true;
    this.curDimensionKey = key;
  }
  // 下钻选择key值之后的处理
  @Emit('drill')
  chooseSelect(option) {
    this.drillValue = option.label;
    return option;
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
  // 渲染左侧表格的列
  handleMultiColumn() {
    const operationCol = (
      <bk-table-column
        scopedSlots={{
          default: () => {
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
                    {this.searchList.map(option => {
                      const isActive = this.drillValue === option.label;
                      return (
                        <li
                          key={option.label}
                          class={['drill-down-item', { active: isActive }]}
                          onClick={() => this.chooseSelect(option)}
                        >
                          {option.name}
                        </li>
                      );
                    })}
                  </ul>
                </bk-dropdown-menu>
              </div>
            );
          },
        }}
        label={this.$t('操作')}
        min-width='100'
      />
    );
    const baseCol = this.tableColumn.map(item => (
      <bk-table-column
        key={item.prop}
        scopedSlots={{
          default: ({ row }) => (
            <span
              class={['multi-view-table-link', { 'block-link': !row[item.prop] }]}
              v-bk-overflow-tips
            >
              <span onClick={() => this.handleShowDetail(row, item.prop)}>{row[item.prop] || '--'}</span>
              <i
                class='icon-monitor icon-mc-copy tab-row-icon'
                onClick={() => this.copyValue(row[item.prop])}
              />
            </span>
          ),
        }}
        label={item.label}
        prop={item.prop}
      />
    ));
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
  // 渲染tab表格的列
  handleMultiTabColumn() {
    const curColumn = this.panels.find(item => item.id === this.active);
    const prefix = ['growth_rates', 'proportions', 'success_rate', 'exception_rate', 'timeout_rate'];
    /** 是否需要展示百分号 */
    const hasPrefix = (fieldName: string) => prefix.some(pre => fieldName.startsWith(pre));
    return (curColumn.columns || []).map(item => (
      <bk-table-column
        key={item.prop}
        scopedSlots={{
          default: ({ row }) => {
            const txt = hasPrefix(item.prop)
              ? row[item.prop]
                ? `${this.formatToTwoDecimalPlaces(row[item.prop])}%`
                : '--'
              : this.formatToTwoDecimalPlaces(row[item.prop]) || '--';
            return (
              <span
                class='multi-view-table-txt'
                v-bk-overflow-tips
              >
                <span onClick={() => this.handleShowDetail(row, item.prop)}>{txt}</span>
                <i
                  class='icon-monitor icon-mc-line tab-row-icon'
                  onClick={() => this.handleDimension(row, 'request')}
                />
              </span>
            );
          },
        }}
        label={item.label}
        prop={item.prop}
        sortable
      />
    ));
  }
  render() {
    return (
      <div class='multi-view-table-main'>
        <div class='multi-view-left'>
          {this.tableColumn && (
            <bk-table
              ext-cls='multi-view-table'
              data={this.tableListData}
              header-border={false}
              header-cell-class-name={() => 'multi-table-head'}
              outer-border={false}
            >
              {this.handleMultiColumn()}
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
              ext-cls='multi-view-tab-table'
              data={this.tableTabData}
              header-border={false}
              header-cell-class-name={() => 'multi-table-tab-head'}
              outer-border={false}
            >
              {this.handleMultiTabColumn()}
            </bk-table>
          </div>
        </div>
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
          <div
            class='content-wrap'
            slot='content'
          >
            <div class='multi-slider-filter'>
              <span class='filter-title'>{this.$t('维度')} ：</span>
              {this.column.map(item => (
                <div
                  key={item.prop}
                  class='filter-item'
                >
                  <span class='filter-item-title'>{item.label}</span>
                  <bk-select
                    style='width: 140px;'
                    v-model={this.curRowData[item.prop]}
                    behavior='simplicity'
                    clearable={false}
                    onChange={() => this.handleFilterChange()}
                  >
                    {this.tableListData.map(option => (
                      <bk-option
                        id={option[item.prop]}
                        key={option[item.prop]}
                        name={option[item.prop]}
                      />
                    ))}
                  </bk-select>
                </div>
              ))}
            </div>
            <div class='multi-slider-chart'>
              <DashboardPanel
                id={'multi-view-table'}
                panels={this.dashboardPanels}
              />
            </div>
          </div>
        </bk-sideslider>
        {/* 维度值分布弹窗 */}
        <bk-dialog
          width={640}
          ext-cls='multi-detail-dialog'
          v-model={this.isShowDimension}
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
              v-model={this.dimensionValue}
            >
              {this.dialogSelectList.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
          </div>
          <div class='multi-dialog-content'>
            <span class='tips'>{this.$t('仅展示前 30 条数据')}</span>
            {this.isShowDimension &&
              (this.chartActive === 'caller-pie-chart' ? (
                <CallerPieChart panel={this.dialogPanel} />
              ) : (
                <CallerBarChart panel={this.dialogPanel} />
              ))}
          </div>
        </bk-dialog>
      </div>
    );
  }
}
