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

import type { IColumnItem, IDataItem } from 'monitor-pc/pages/custom-escalation/new-metric-view/type';
import type { ILegendItem } from 'monitor-ui/chart-plugins/typings';

import './check-view-table.scss';

@Component
export default class CheckViewTable extends tsc<object, object> {
  @Prop({ default: () => ({}) }) data: any;
  @Prop({ default: () => [] }) legendData: ILegendItem[];
  @Prop({ default: true }) isShowStatistical: boolean;
  @Prop({ default: true }) loading: boolean;

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

  /** 动态生成对比列 */
  get compareColumn(): IColumnItem[] {
    return this.legendData.map(item => {
      const label = this.handleProp(item);
      return { ...item, label, prop: label };
    });
  }

  /** 转换后的表格数据 */
  get tableDataList() {
    const length = Object.keys(this.data).length;
    if (this.data && length > 0) {
      const { series } = this.data;
      if (!series || !Array.isArray(series)) return [];
      const list = {};
      series.map(item => {
        const key = this.handleProp(item);
        list[key] = item.datapoints;
      });
      let formateData = this.convertData(list);
      const len = formateData.length;
      /** 排序 */
      if (this.sortProp && this.sortOrder && len) {
        formateData = formateData.toSorted((a, b) => {
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

  /** 统计行数据 */
  get statisticalDataList() {
    if (this.compareColumn.length === 0) return [];
    return Object.keys(this.typeArr).map(type => {
      const res: Record<string, any> = {
        type: this.$t(this.typeArr[type]),
        key: type,
      };
      this.keys.map(key => {
        const data = this.compareColumn.find(item => item.prop === key);
        res[key] = data ? data[type] : '--';
        // 兼容时间戳
        if (data?.[`${type}Time`]) {
          res[`${key}Time`] = data[`${type}Time`];
        }
      });
      return res;
    });
  }

  /** 数据转换 */
  convertData(originalData: Record<string, any[]>): IDataItem[] {
    const keys = Object.keys(originalData);
    this.keys = keys;
    if (keys.length === 0) return [];
    // 取第一个key的时间戳为基准
    const referenceKey = keys[0];
    const timestampList = (originalData[referenceKey] || []).map(item => item[1]);
    return timestampList.map((timestamp, index) => {
      const result: Record<string, any> = {
        time: dayjs.tz(timestamp).format('YYYY-MM-DD HH:mm:ss'),
        date: timestamp,
      };
      keys.map(key => {
        result[key] = originalData[key]?.[index]?.[0] ?? '--';
      });
      return result;
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
  renderHeader(h, data: any, item: any) {
    const { $index } = data;
    if (item.color) {
      return (
        <span
          class={`color-head ${this.selectLegendInd >= 1 && this.selectLegendInd !== $index ? 'disabled' : ''}`}
          v-bk-tooltips={{
            extCls: 'check-view-tooltips',
            content: `<span class='head-tips-view'>
              <span class='tips-name'>${this.$t('维度（组合）')}</span><br/>
              ${
                item.name
                  .split('|')
                  .map((item, ind) => {
                    const className = ind % 2 !== 0 ? 'tips-item' : 'tips-item-even';
                    const index = item.indexOf('=');
                    return `<span class=${className}><label class='item-name'>${xssFilter(item.slice(0, index))}</label>：${xssFilter(item.slice(index + 1))}</span><br/>`;
                  })
                  .join('') || ''
              }
            </span>`,
            allowHTML: true,
            placement: 'bottom',
          }}
          onClick={() => this.handleRowClick(item, $index)}
        >
          <span
            style={{ backgroundColor: item.color }}
            class='color-box'
          />
          <span class='color-label'>{item.label}</span>
        </span>
      );
    }
    return <span class='color-label'>{item.label}</span>;
  }

  /** 渲染主表格列 */
  renderTableColumn() {
    const baseColumn: IColumnItem[] = [{ label: 'Time', prop: 'time', sortable: true, fixed: 'left', minWidth: 200 }];
    const columnList = [...baseColumn, ...this.compareColumn];
    return columnList.map((item: IColumnItem, ind: number) => (
      <bk-table-column
        key={`${item.prop}_${ind}`}
        width={item.width}
        scopedSlots={{
          default: ({ row }) => (row[item.prop] === undefined || row[item.prop] === null ? '--' : row[item.prop]),
        }}
        fixed={item.fixed || false}
        label={this.$t(item.label)}
        min-width={item.minWidth}
        prop={item.prop}
        renderHeader={(h, { column, $index }: any) => this.renderHeader(h, { column, $index }, item)}
        sortable={item.sortable}
        show-overflow-tooltip
      />
    ));
  }

  /** 渲染统计表格列 */
  renderStatisticalColumn() {
    const baseColumn: IColumnItem[] = [{ label: 'type', prop: 'type', fixed: 'left', minWidth: 200 }];
    const columnList = [...baseColumn, ...this.compareColumn];
    return columnList.map((item: IColumnItem, ind: number) => (
      <bk-table-column
        key={`${item.prop}_${ind}`}
        width={item.width}
        scopedSlots={{
          default: ({ row }) => (
            <span class='num-cell'>
              {row[item.prop] === undefined || row[item.prop] === null ? '--' : row[item.prop]}
              {item.prop !== 'type' && row[`${item.prop}Time`] && (
                <span class='gray-text'>@{dayjs(row[`${item.prop}Time`]).format('HH:mm')}</span>
              )}
            </span>
          ),
        }}
        fixed={item.fixed || false}
        label={this.$t(item.label)}
        min-width={item.minWidth}
        show-overflow-tooltip
      />
    ));
  }
  /** 排序 */
  handleSort({ order, prop }) {
    this.sortProp = prop;
    this.sortOrder = order;
  }
  getCellName = ({ column }) => {
    // console.log(column, 'column');
    // const id = column.property;
    // const columnData = this.columns.find(item => item.id === id);
    // return columnData?.[HEADER_PRE_ICON_NAME] ? 'has-header-pre-icon' : '';
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
            ext-cls='check-view-table-main'
            cell-class-name={this.getCellName}
            data={this.tableDataList}
            header-border={false}
            outer-border={false}
            on-sort-change={this.handleSort}
          >
            {this.renderTableColumn()}
          </bk-table>
        )}
        {!this.loading && this.isShowStatistical && this.statisticalDataList.length > 0 && (
          <bk-table
            ext-cls='check-view-table-statistical'
            data={this.statisticalDataList}
            header-border={false}
            outer-border={false}
            show-header={false}
          >
            {this.renderStatisticalColumn()}
          </bk-table>
        )}
      </div>
    );
  }
}
