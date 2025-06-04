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
import { xssFilter } from 'monitor-common/utils/xss';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { timeOffsetDateFormat } from 'monitor-pc/pages/monitor-k8s/components/group-compare-select/utils';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats/valueFormats';

import { handleGetMinPrecision, typeEnums } from '../../metric-chart-view/utils';

import type { IColumnItem, IDataItem } from 'monitor-pc/pages/custom-escalation/new-metric-view/type';
import type { ILegendItem } from 'monitor-ui/chart-plugins/typings';

import './check-view-table.scss';

@Component
export default class CheckViewTable extends tsc<object, object> {
  @Prop({ default: () => ({}) }) data: any;
  @Prop({ default: () => [] }) legendData: ILegendItem[];
  @Prop({ default: true }) isShowStatistical: boolean;
  @Prop({ default: true }) loading: boolean;
  @Prop({ default: false }) isHasCompare: boolean;
  @Prop({ default: false }) isHasDimensions: boolean;
  @Prop({ default: '' }) title: string;
  fluctuationColumn: IColumnItem[] = [{ label: '波动', prop: 'fluctuation' }];

  // 统计类型映射
  typeArr = {
    max: '最大值',
    min: '最小值',
    latest: '最新值',
    avg: '平均值',
    total: '累计值',
  };

  keys: string[] = [];
  selectLegendInd = 0;
  sortProp: null | string = null;
  sortOrder: 'ascending' | 'descending' | null = null;

  @Watch('loading')
  handleLoading() {
    this.selectLegendInd = 0;
  }

  get rawDataList() {
    const len = Object.keys(this.data).length;
    if (this.data && len > 0) {
      const { series } = this.data;
      return this.classifyData(series);
    }
    return [];
  }

  classifyData(data: any[]) {
    const byDimensions: Record<string, any[]> = {};
    // eslint-disable-next-line @typescript-eslint/prefer-for-of
    for (let i = 0; i < data.length; i++) {
      const item = data[i];
      const dimensionsKey = JSON.stringify(item.dimensions);
      if (!byDimensions[dimensionsKey]) {
        byDimensions[dimensionsKey] = [];
      }
      byDimensions[dimensionsKey].push(item);
    }

    return Object.entries(byDimensions).map(([dimensionsKey, items]) => ({
      dimensions: JSON.parse(dimensionsKey),
      items,
    }));
  }
  /** 有维度且有时间对比 */
  get isMergeTable() {
    return this.isHasCompare && this.isHasDimensions;
  }
  /** 有时间对比没有维度 */
  get isCompareNotDimensions() {
    return this.isHasCompare && !this.isHasDimensions;
  }

  /** 动态生成对比列 */
  get compareColumn(): IColumnItem[] {
    const newData = this.classifyData(this.legendData);
    if (this.isCompareNotDimensions) {
      const data = newData[0] || { items: [] };
      return data.items.map(ele => ({ ...ele, label: ele.name, prop: ele.timeOffset }));
    }
    return newData.map(item => {
      const label = this.handleProp(item);
      return { ...item, label, prop: label || 'current' };
    });
  }

  /** 转换后的表格数据 */
  get tableDataList() {
    const length = this.rawDataList.length;
    if (length > 0) {
      const formateData = this.transformData(this.rawDataList);
      const len = formateData.length;
      /** 排序 */
      if (this.sortProp && this.sortOrder && len) {
        formateData.sort((a, b) => {
          if (this.sortOrder === 'ascending') {
            return a[this.sortProp] > b[this.sortProp] ? 1 : -1;
          }
          return a[this.sortProp] < b[this.sortProp] ? 1 : -1;
        });
      }
      return formateData;
    }
    return [];
  }

  transformData(data: any[]) {
    const resultMap = new Map<
      number,
      {
        time: string;
        date: number;
        list: {
          [timeOffset: string]: { [key: string]: number };
        };
        unit: string;
      }
    >();

    for (const item of data) {
      const key = this.handleProp(item);
      for (const subItem of item.items) {
        const { time_offset = 'current', unit, datapoints } = subItem;
        for (const [value, timestamp] of datapoints) {
          if (!resultMap.has(timestamp)) {
            const time = dayjs.tz(timestamp).format('YYYY-MM-DD HH:mm:ss');
            resultMap.set(timestamp, {
              time,
              date: timestamp,
              list: {},
              unit,
            });
          }

          const entry = resultMap.get(timestamp)!;
          if (!entry.list[time_offset]) {
            entry.list[time_offset] = {};
          }
          entry.list[time_offset][key || time_offset] = value;
        }
      }
    }

    return Array.from(resultMap.values());
  }

  /** 统计行数据 */
  get statisticalDataList() {
    if (this.compareColumn.length === 0) return [];
    return Object.keys(this.typeArr).map(type => {
      const res: Record<string, any> = {
        type: this.$t(this.typeArr[type]),
        key: type,
      };
      this.compareColumn.map(item => {
        res[item.prop] = item.items || [item];
      });
      return res;
    });
  }

  /** prop值处理 */
  handleProp(item: any): string {
    const dimensions = Object.values(item.dimensions || {});
    return dimensions.length > 0 ? dimensions.join(' | ') : item.target;
  }

  /** 点击表格的图例，与图表联动 */
  handleRowClick(item: ILegendItem, index: number) {
    this.selectLegendInd = this.selectLegendInd === index ? 0 : index;
    this.$emit('headClick', item);
  }

  /** 自定义表头渲染，支持颜色和维度提示 */
  renderHeader(h: any, data: any, item: any) {
    const { $index } = data;
    if ((item.items || []).length > 1) {
      return (
        <span
          class={`color-head ${this.selectLegendInd >= 1 && this.selectLegendInd !== $index ? 'disabled' : ''}`}
          v-bk-tooltips={{
            extCls: 'check-view-tooltips',
            content: `<span class='head-tips-view'>
              <span class='tips-name'>${this.$t('维度（组合）')}</span><br/>
              ${
                item.items[0].name
                  .split('|')
                  .map((item: string, ind: number) => {
                    const className = ind % 2 !== 0 ? 'tips-item' : 'tips-item-even';
                    const index = item.indexOf('=');
                    return `<span class=${className}><label class='item-name'>${xssFilter(
                      item.slice(0, index)
                    )}</label>：${xssFilter(item.slice(index + 1))}</span><br/>`;
                  })
                  .join('') || ''
              }
            </span>`,
            allowHTML: true,
            placement: 'bottom',
          }}
          // onClick={() => this.handleRowClick(item, $index)}
        >
          <span
            style={{ backgroundColor: item.color }}
            class='color-box'
          />
          <span class='color-label'>{item.label}</span>
          {this.isMergeTable && (
            <span class='head-list'>
              {(item.items || []).map((ele: any, ind: number) => (
                <span
                  key={`${ele.timeOffset}${ind}`}
                  class='head-list-item'
                >
                  <span
                    style={{ backgroundColor: ele.color }}
                    class='color-box'
                  />
                  {typeEnums[ele.timeOffset] || timeOffsetDateFormat(ele.timeOffset)}
                </span>
              ))}
              <span class='head-list-item'>{this.$t('波动')}</span>
            </span>
          )}
        </span>
      );
    }
    if (item.prop !== 'time') {
      return (
        <span class='color-head no-compare'>
          <span
            style={{
              backgroundColor: item?.items ? item.items[0].color : item.color,
            }}
            class='color-box'
          />
          <span class='color-label not-color'>{item.label || this.title}</span>
        </span>
      );
    }
    return <span class='color-label not-color'>{item.label}</span>;
  }

  renderValue(row: IDataItem, prop: string, unit: string) {
    if (row[prop] === undefined || row[prop] === null) {
      return '--';
    }
    const precision = handleGetMinPrecision(
      this.tableDataList.map(item => item[prop]).filter((set: any) => typeof set === 'number'),
      getValueFormat(unit),
      unit
    );
    const unitFormatter = getValueFormat(unit);
    const set: any = unitFormatter(row[prop], unit !== 'none' && precision < 1 ? 2 : precision);
    return (
      <span>
        {set.text} {set.suffix}
      </span>
    );
  }

  renderFluctuation(row: IDataItem, prop: string, keys: string[]) {
    const color = row[prop] >= 0 ? '#3AB669' : '#E91414';
    const data = ((row[keys[1]][prop] - row[keys[0]][prop]) / row[keys[0]][prop]) * 100;
    const isShow = !Number.isNaN(data) && Number.isFinite(data);
    return <span style={{ color: row[prop] ? color : '#313238' }}>{isShow ? `${data}%` : '--'}</span>;
  }

  /** 渲染表格列 */
  renderColumns(isStatistical = false): IColumnItem[] {
    const baseColumn: IColumnItem[] = [
      {
        label: isStatistical ? 'type' : 'Time',
        prop: isStatistical ? 'type' : 'time',
        sortable: !isStatistical,
        fixed: 'left',
        minWidth: 200,
      },
    ];
    const columnList = this.isCompareNotDimensions
      ? [...baseColumn, ...this.compareColumn, ...this.fluctuationColumn]
      : [...baseColumn, ...this.compareColumn];

    return columnList.map((item: IColumnItem, ind: number) => (
      <bk-table-column
        key={`${item.prop}_${ind}`}
        width={item.width}
        scopedSlots={{
          default: (data: any) => {
            const { row } = data;
            if (isStatistical) {
              if (item.prop !== 'type') {
                const data = row[item.prop];
                const len = (data || []).length;
                return (data || []).map((item: any, ind: number) => (
                  <span
                    key={`${row.key}-${ind}`}
                    style={{ width: len > 1 ? '33.33%' : '100%' }}
                    class='num-cell'
                  >
                    {item[row.key] === undefined || item[row.key] === null ? '--' : item[row.key]}
                    <span class='gray-text'>@{dayjs(item[`${row.key}Time`]).format('HH:mm')}</span>
                  </span>
                ));
              }
              return row[item.prop];
            }

            const { list, unit } = row;
            const keys = Object.keys(list);
            if (item.prop === 'time') {
              return row[item.prop] === undefined || row[item.prop] === null ? '--' : row[item.prop];
            }
            if (this.isMergeTable) {
              return (
                <span class='check-table-merge'>
                  {keys.map((key: string, ind: number) => (
                    <span
                      key={`${key}-${ind}`}
                      class='check-table-merge-item'
                      v-bk-overflow-tips
                    >
                      {this.renderValue(list[key], item.prop, unit)}
                    </span>
                  ))}
                  <span
                    class='check-table-merge-item'
                    v-bk-overflow-tips
                  >
                    {this.renderFluctuation(list, item.prop, keys)}
                  </span>
                </span>
              );
            }
            if (this.isCompareNotDimensions) {
              return list[item.prop]
                ? this.renderValue(list[item.prop], item.prop, unit)
                : this.renderFluctuation(list, item.prop, keys);
            }
            return this.renderValue(list[keys[0]], item.prop, unit);
          },
        }}
        fixed={item.fixed || false}
        label={this.$t(item.label)}
        min-width={item.minWidth || (this.isMergeTable ? 240 : 120)}
        prop={item.prop}
        renderHeader={(h: any, { column, $index }: any) => this.renderHeader(h, { column, $index }, item)}
        sortable={item.sortable}
        show-overflow-tooltip
      />
    ));
  }

  /** 排序 */
  handleSort({ order, prop }: { order: string; prop: string }) {
    this.sortProp = prop;
    this.sortOrder = order as 'ascending' | 'descending' | null;
  }

  getCellName = ({ column }: { column: any }) => {
    return '';
  };

  render() {
    return (
      <div class='check-view-table'>
        {this.loading ? (
          <TableSkeleton
            class='table-skeleton-block'
            type={1}
          />
        ) : (
          <bk-table
            height={300}
            ext-cls={`check-view-table-main ${this.isMergeTable ? 'is-nowrap' : ''}`}
            cell-class-name={this.getCellName}
            data={this.tableDataList}
            header-border={false}
            outer-border={false}
            on-sort-change={this.handleSort}
          >
            {this.renderColumns()}
          </bk-table>
        )}
        {!this.loading && this.isShowStatistical && this.statisticalDataList.length > 0 && (
          <bk-table
            ext-cls='check-view-table-statistical'
            data={this.statisticalDataList}
            outer-border={false}
            show-header={false}
          >
            {this.renderColumns(true)}
          </bk-table>
        )}
      </div>
    );
  }
}
