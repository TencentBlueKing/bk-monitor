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

import { ITableSeries } from '../options/type-interface';

import './table-chart.scss';

interface TableChartProps {
  series: ITableSeries;
  maxHeight: number;
}
@Component({
  name: 'table-chart'
})
export default class TableChart extends tsc<TableChartProps> {
  @Prop({ type: Object, default: () => ({}) }) series: ITableSeries;
  @Prop({ type: Number, default: 174 }) maxHeight: number;

  tableColumn: ITableSeries['columns'] = [];
  tableData: { [propName: string]: any }[] = [];

  @Watch('series', { immediate: true, deep: true })
  handleSeries(series: ITableSeries) {
    this.tableColumn = series.columns;
    this.tableData =
      this.series.rows?.map(item => {
        const obj: any = {};
        this.tableColumn?.forEach((column, index) => {
          if (column.type === 'time') {
            obj[column.text] = dayjs.tz(String(item[index])).format('YYYY-MM-DD HH:mm:ss');
          } else {
            obj[column.text] = item[index];
          }
        });
        return obj;
      }) || [];
  }

  render() {
    return (
      <bk-table
        data={this.tableData}
        size={'small'}
        ext-cls='chart-table'
        max-height={this.maxHeight - 10}
        outer-border={false}
      >
        {this.tableColumn?.map(column => (
          <bk-table-column
            label={column.text}
            show-overflow-tooltip={true}
            scopedSlots={{
              default: ({ row }) => row[column.text]
            }}
          ></bk-table-column>
        ))}
      </bk-table>
    );
  }
}
