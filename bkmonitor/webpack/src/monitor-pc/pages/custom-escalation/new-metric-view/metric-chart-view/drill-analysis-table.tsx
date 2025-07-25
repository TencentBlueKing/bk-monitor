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
import { Component, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from 'monitor-common/utils/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { timeOffsetDateFormat } from 'monitor-pc/pages/monitor-k8s/components/group-compare-select/utils';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats/valueFormats';

import { formatTipsContent, generateTimeStrings, handleGetMinPrecision, typeEnums } from './utils';

import type { IColumnItem, IDataItem, IDimensionItem, IFilterConfig } from '../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './drill-analysis-table.scss';

/** 维度下钻 - 聚合维度表格 */

interface IDrillAnalysisTableEvent {
  onChooseDrill?: (v: IDimensionItem[], item: string[]) => void;
  onShowDetail?: (v: IDataItem, item: IDimensionItem) => void;
  onUpdateDimensions?: (v: IDimensionItem[]) => void;
}

interface IDrillAnalysisTableProps {
  dimensionsList?: IDimensionItem[];
  filterConfig?: IFilterConfig;
  loading?: boolean;
  tableList?: any[];
  tableLoading?: boolean;
}

@Component
export default class DrillAnalysisTable extends tsc<IDrillAnalysisTableProps, IDrillAnalysisTableEvent> {
  @Prop({ type: Array, default: () => [] }) dimensionsList: IDimensionItem[];
  @Prop({ type: Array, default: () => [] }) tableList: IDataItem[];
  @Prop({ default: false }) loading: boolean;
  @Prop({ default: false }) tableLoading: boolean;
  @Prop({ type: Object, default: () => {} }) filterConfig: IFilterConfig;
  @InjectReactive('timeRange') timeRange: TimeRangeType;

  /** 维度是否支持多选 */
  isMultiple = false;
  /** 选中的维度 */
  activeList = [];
  dimensionSearch = '';
  /** 展示的维度值 */
  showDimensionKeys = [];
  /** 下钻过滤列表 */
  drillList = [];
  /** 已经下钻了的维度值 */
  drillValue = '';
  /** 显示维度趋势图 */
  isShowDetail = false;
  /** 显示维度趋势图 维度id */
  filterDimensionValue = '';
  sortProp: null | string = null;
  sortOrder: 'ascending' | 'descending' | null = null;
  sortColumn: IColumnItem[] = [];

  mounted() {
    setTimeout(() => {
      const list = this.dimensionsList.filter(item => item.checked);
      this.isMultiple = list.length > 1;
      this.activeList = list.map(item => item.name);
    });
  }

  /** 需要展示的维度列 */
  get dimensionsColumn() {
    const list: IColumnItem[] = [];
    this.showDimensionKeys = [];
    this.dimensionsList.map(item => {
      if (item.checked) {
        list.push({
          label: item.alias || item.name,
          prop: `dimensions.${item.name}`,
          renderFn: row => this.renderDimensionRow(row, item),
        });
        this.showDimensionKeys.push(item.name);
      }
    });
    return list;
  }
  /** 根据搜索输入内容过滤要展示的维度 */
  get showDimensionsList() {
    return this.dimensionsList.filter(item => item.name.includes(this.dimensionSearch)) || [];
  }
  /** 维度趋势图下拉选项 */
  get dimensionOptions() {
    if (!this.tableList?.length) return [];
    const options = new Map();
    for (const item of this.tableList) {
      const dimensions = item?.dimensions;
      const name = this.getDimensionId(dimensions || {});
      if (!options.has(name)) {
        options.set(name, { name, id: name, dimensions });
      }
    }
    return Array.from(options.values());
  }
  get showTableList() {
    let list = this.tableList || [];
    if (this.sortProp && this.sortOrder && list.length) {
      list = list.toSorted((a, b) => {
        if (this.sortOrder === 'ascending') {
          return a[this.sortProp] > b[this.sortProp] ? 1 : -1;
        }
        return a[this.sortProp] < b[this.sortProp] ? 1 : -1;
      });
    }
    return list;
  }

  getDimensionId(dimensions: Record<string, string>) {
    let name = '';
    for (const [key, val] of Object.entries(dimensions || {})) {
      if (key === 'time') continue;
      const tag = this.dimensionsList.find(item => item.value === key);
      name += ` ${tag?.text}:${val || '--'} `;
    }
    return name;
  }

  /** 维度选择侧栏 start */
  renderDimensionList() {
    if (this.loading) {
      return (
        <div class='skeleton-loading'>
          {Array(6)
            .fill(null)
            .map((_, index) => (
              <div
                key={index}
                class='skeleton-element'
              />
            ))}
        </div>
      );
    }
    if (this.showDimensionsList.length === 0) {
      return (
        <EmptyStatus
          textMap={{ empty: this.$t('暂无数据') }}
          type={this.dimensionSearch ? 'search-empty' : 'empty'}
          onOperation={() => {
            this.dimensionSearch = '';
          }}
        />
      );
    }
    // const baseView = (item: IDimensionItem) => [
    //   <span>{item.alias || item.name}</span>,
    //   <span class='item-name'>{item.alias ? item.name : ''}</span>,
    // ];
    const baseView = (item: IDimensionItem) => (
      <span
        class='item-alias'
        v-bk-tooltips={{
          content: formatTipsContent(item.name, item.alias),
          placement: 'right',
        }}
      >
        {item.alias || item.name}
      </span>
    );
    /** 单选 */
    if (!this.isMultiple) {
      return this.showDimensionsList.map((item: IDimensionItem) => (
        <div
          key={item.name}
          class={['dimensions-list-item', { active: item.checked }]}
          onClick={() => this.handleDimensionChange([item.name])}
        >
          {baseView(item)}
        </div>
      ));
    }
    /** 多选 */
    return (
      <bk-checkbox-group
        value={this.activeList}
        onChange={v => this.handleDimensionChange(v)}
      >
        {this.showDimensionsList.map(item => (
          <bk-checkbox
            key={item.name}
            class='dimensions-list-item'
            disabled={this.activeList.length === 1 && item.checked}
            value={item.name}
          >
            {baseView(item)}
          </bk-checkbox>
        ))}
      </bk-checkbox-group>
    );
  }

  /** 改变维度是否多选 */
  changeMultiple(val: boolean) {
    this.isMultiple = val;
    const index = this.dimensionsList.findIndex(item => item.checked);
    this.handleDimensionChange([this.dimensionsList[index].name]);
  }
  /** 选中维度的相关处理  */
  handleDimensionChange(checkedList: string[]) {
    this.activeList = checkedList;
    const list = this.dimensionsList.map((dimension: IDimensionItem) =>
      Object.assign(dimension, {
        checked: checkedList.includes(dimension.name),
      })
    );
    this.$emit('updateDimensions', list, this.activeList);
  }

  /** 维度选择侧栏 end */

  /** 维度表格 start  */

  /** 绘制下钻下拉列表 */
  renderOperation(row: IDataItem) {
    const drillKey = this.drillList.map(item => item.key);
    const list = this.dimensionsList.filter(item => !drillKey.includes(item.name) && !item.checked);
    const len = list.length;
    if (len === 0) {
      return (
        <span
          class='disabled-drill-down'
          v-bk-tooltips={{ content: this.$t('暂无维度可下钻') }}
        >
          {this.$t('下钻')}
        </span>
      );
    }
    return (
      <bk-dropdown-menu
        ref='dropdown'
        ext-cls='table-drill-down-popover'
        trigger='click'
        position-fixed
      >
        <div
          class='table-drill-down-btn'
          slot='dropdown-trigger'
        >
          <span>{this.$t('下钻')}</span>
          <i class='icon-monitor icon-mc-arrow-down' />
        </div>
        <ul
          class='table-drill-down-list'
          slot='dropdown-content'
        >
          {(list || []).map(option => {
            const isActive = this.drillValue === option.key;
            return (
              <li
                key={option.key}
                class={['table-drill-down-item', { active: isActive }]}
                v-bk-tooltips={{
                  content: formatTipsContent(option.name, option.alias),
                  placement: 'right',
                }}
                onClick={() => this.chooseDrill(option, row)}
              >
                {option.alias || option.name}
                {/* {option.alias ? ` (${option.name})` : ''} */}
              </li>
            );
          })}
        </ul>
      </bk-dropdown-menu>
    );
  }
  /** 绘制维度列 */
  renderDimensionRow(row: IDataItem, item: IDimensionItem) {
    const showTxt = row?.dimensions[item.name] || '--';
    return (
      <span class='dimensions-value'>
        <span
          class='dimensions-value-text'
          v-bk-overflow-tips
          // onClick={() => this.handleShowDetail(row, item)}
        >
          {showTxt}
        </span>
        {row?.dimensions[item.name] && (
          <i
            class='icon-monitor icon-mc-copy tab-row-icon'
            onClick={() => this.copyValue(showTxt)}
          />
        )}
      </span>
    );
  }
  /** 绘制波动值 */
  renderFluctuation(row: IDataItem, prop: string) {
    const color = row[prop] >= 0 ? '#3AB669' : '#E91414';
    return <span style={{ color: row[prop] ? color : '#313238' }}>{row[prop] ? `${row[prop]}%` : '--'}</span>;
  }
  renderValue(row: IDataItem, prop: string) {
    if (row[prop] === undefined || row[prop] === null) {
      return '--';
    }
    const precision = handleGetMinPrecision(
      this.tableList.map(item => item[prop]).filter((set: any) => typeof set === 'number'),
      getValueFormat(row.unit),
      row.unit
    );
    const unitFormatter = getValueFormat(row.unit);
    const set: any = unitFormatter(row[prop], row.unit !== 'none' && precision < 1 ? 2 : precision);
    return (
      <span>
        {set.text} {set.suffix}
      </span>
    );
  }
  /** 自定义表格头部渲染 */
  renderHeader(h, { column }: any, item: any) {
    const tipsKey = ['1h', '1d', '7d', '30d'];
    const timeUnit = item.prop.split('_')[0];
    const hasEndFix = (fieldName: string) => {
      return ['value'].some(pre => fieldName.endsWith(pre));
    };

    const hasTips = (fieldName: string) => {
      return tipsKey.some(pre => fieldName.startsWith(pre));
    };
    const tips = tipsKey.includes(timeUnit) && hasTips(item.prop) ? generateTimeStrings(timeUnit, this.timeRange) : '';
    return (
      <span class='custom-header-main'>
        <span
          class={[{ 'item-txt': !hasEndFix(item.prop) }, { 'item-txt-no': hasEndFix(item.prop) }]}
          v-bk-overflow-tips
        >
          <span
            class={{ 'custom-header-tips': hasEndFix(item.prop) && hasTips(item.prop) }}
            v-bk-tooltips={hasEndFix(item.prop) && hasTips(item.prop) ? { content: tips } : { disabled: true }}
          >
            {item.label}
          </span>
        </span>
      </span>
    );
  }

  renderPercentage(row) {
    if (row.percentage === undefined || row.percentage === null) {
      return '--';
    }
    return <span>{row.percentage}%</span>;
  }

  /** 绘制表格内容 */
  renderTableColumn() {
    const { time_compare = [] } = this.filterConfig.function;
    const baseColumn: IColumnItem[] = [
      {
        label: '操作',
        prop: 'operation',
        renderFn: row => this.renderOperation(row),
      },
      { label: '占比', prop: 'percentage', sortable: true, renderFn: row => this.renderPercentage(row) },
      { label: '当前值', prop: 'value', sortable: true, renderFn: row => this.renderValue(row, 'value') },
    ];
    let compareColumn: IColumnItem[] = [];
    /** 根据时间对比动态计算要展示的表格列 */
    if (time_compare.length > 0) {
      time_compare.map(val => {
        compareColumn = [
          ...compareColumn,
          ...[
            {
              label: typeEnums[val] || timeOffsetDateFormat(val),
              prop: `${val}_value`,
              sortable: true,
              renderFn: row => this.renderValue(row, `${val}_value`),
            },
            {
              label: '波动',
              prop: `${val}_fluctuation`,
              sortable: true,
              renderFn: row => this.renderFluctuation(row, `${val}_fluctuation`),
            },
          ],
        ];
      });
    }
    this.sortColumn = [...baseColumn, ...compareColumn];

    const columnList = [...this.dimensionsColumn, ...baseColumn, ...compareColumn];
    return columnList.map((item: IColumnItem, ind: number) => {
      return (
        <bk-table-column
          key={`${item.prop}_${ind}`}
          width={item.width}
          scopedSlots={{
            default: ({ row }) => {
              /** 自定义 */
              if (item?.renderFn) {
                return item?.renderFn(row);
              }
              return row[item.prop] === undefined || row[item.prop] === null ? '--' : row[item.prop];
            },
          }}
          label={this.$t(item.label)}
          prop={item.prop}
          renderHeader={(h, { column, $index }: any) => this.renderHeader(h, { column, $index }, item)}
          sortable={item.sortable}
        />
      );
    });
  }
  /** 修改维度趋势图下拉 */
  handleFilterChange(id: string) {
    this.filterDimensionValue = id;
    // this.handleRawCallOptionsChange();
  }
  /** 展示维度趋势侧滑抽屉 */
  handleShowDetail(row: IDataItem, item: IDimensionItem) {
    this.isShowDetail = true;
    this.$emit('showDetail', row, item);
  }

  /** 复制内容 */
  copyValue(text: string) {
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
  /** 下钻操作 */
  chooseDrill(item: IDimensionItem, row: IDataItem) {
    this.drillValue = item.name;
    this.isMultiple = false;
    this.showDimensionKeys.map(key => {
      this.drillList.push({
        key,
        alias: this.showDimensionsList.find(ele => ele.name === key).alias,
        value: row.dimensions[key],
      });
    });
    this.activeList = [item.name];
    this.$emit('chooseDrill', this.drillList, [item.name]);
  }

  /**  清空下钻过滤条件  */
  clearDrillFilter(item: IDimensionItem) {
    this.drillList = this.drillList.filter(drill => item.key !== drill.key);
    this.$emit('chooseDrill', this.drillList, this.activeList);
  }

  createOption(dimensions: Record<string, string>) {
    return (
      <div class='options-wrapper'>
        {Object.entries(dimensions || {})
          .map(([key, value]) => {
            if (key === 'time') return undefined;
            const tag = this.dimensionsList.find(item => item.value === key);
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
  handleSort({ order, prop }) {
    this.sortProp = prop;
    this.sortOrder = order;
  }
  /** 维度表格 end */

  render() {
    return (
      <div class='drill-analysis-table'>
        <div class='table-left'>
          <div class='table-left-header'>
            {this.$t('多维分析')}
            <bk-checkbox
              class='header-checkbox'
              value={this.isMultiple}
              onChange={this.changeMultiple}
            >
              {this.$t('多选')}
            </bk-checkbox>
          </div>
          <bk-input
            class='search-input'
            v-model={this.dimensionSearch}
            placeholder={this.$t('搜索 维度')}
            right-icon={'bk-icon icon-search'}
          />
          <div class='dimensions-list'>{this.renderDimensionList()}</div>
        </div>
        <div class='table-right'>
          {this.drillList.length > 0 && (
            <div class='dimensions-filter'>
              {this.drillList.map(item => (
                <bk-tag
                  key={item.key}
                  class='drill-tag'
                  v-bk-tooltips={{
                    content: formatTipsContent(item.key, item.alias),
                  }}
                  closable
                  onClose={() => this.clearDrillFilter(item)}
                >
                  <span>{item.alias || item.key}</span>
                  <span class='tag-eq'>=</span>
                  <span class='tag-value'>{item.value}</span>
                </bk-tag>
              ))}
            </div>
          )}
          {this.tableLoading ? (
            <TableSkeleton
              class='table-skeleton-block'
              type={1}
            />
          ) : (
            <bk-table
              ext-cls='dimensions-table'
              data={this.showTableList}
              header-border={false}
              outer-border={false}
              stripe={true}
              on-sort-change={this.handleSort}
            >
              {this.renderTableColumn()}
            </bk-table>
          )}
        </div>
        {/* 维度趋势图侧栏 */}
        {/* <bk-sideslider
          width={640}
          ext-cls='drill-multi-detail-slider'
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
              <div class='drill-multi-slider-filter'>
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
              <div class='drill-multi-slider-chart'>
                <DashboardPanel
                  id={'drill-table-extra_panels'}
                  column={1}
                  panels={this.panel}
                />
              </div>
            </div>
          )}
        </bk-sideslider> */}
      </div>
    );
  }
}
