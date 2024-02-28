/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getValueFormat } from '../../../../monitor-echarts/valueFormats';
import { ColorTypes, ITableTipsDetail, ProfilingTableItem, TableColumn, TextDirectionType } from '../../../typings';
import { getHashVal } from '../flame-graph/utils';

import './table-graph.scss';

const TABLE_BGCOLOR_COLUMN_WIDTH = 120;

interface ITableChartProps {
  unit: string;
  textDirection: TextDirectionType;
  data: ProfilingTableItem[];
  highlightId: number;
  filterKeyword: string;
  isCompared: boolean;
  dataType: string;
}

interface ITableChartEvents {
  onUpdateHighlightId: number;
  onSortChange: string;
}

@Component
export default class ProfilingTableChart extends tsc<ITableChartProps, ITableChartEvents> {
  @Prop({ required: true, type: String }) unit: string;
  @Prop({ required: true, type: String }) textDirection: TextDirectionType;
  @Prop({ required: true, type: Array }) data: ProfilingTableItem[];
  @Prop({ default: -1, type: Number }) highlightId: number;
  @Prop({ default: '', type: String }) filterKeyword: string;
  @Prop({ default: false, type: Boolean }) isCompared: boolean;
  @Prop({ default: '', type: String }) dataType: string;

  maxItem: { self: number; total: number } = {
    self: 0,
    total: 0
  };
  /** 表格数据 */
  tableData: ProfilingTableItem[] = [];
  tableColumns: TableColumn[] = [
    { id: 'Location', name: 'Location', sort: '' },
    { id: 'Self', name: 'Self', mode: 'normal', sort: '' },
    { id: 'Total', name: 'Total', mode: 'normal', sort: '' },
    { id: 'baseline', name: window.i18n.t('查询项'), mode: 'diff', sort: '' },
    { id: 'comparison', name: window.i18n.t('对比项'), mode: 'diff', sort: '' },
    { id: 'diff', name: 'Diff', mode: 'diff', sort: '' }
  ];
  tipDetail: ITableTipsDetail = {};
  diffMode = false;
  localIsCompared = false;

  @Emit('updateHighlightId')
  handleHighlightIdChange(val: number) {
    return val;
  }

  @Emit('sortChange')
  handleSortChange(sortKey) {
    return sortKey;
  }

  @Watch('data', { immediate: true, deep: true })
  handleDataChange(val: ProfilingTableItem[]) {
    this.maxItem = {
      self: Math.max(...val.map(item => item.self)),
      total: Math.max(...val.map(item => item.total))
    };
    this.getTableData();
  }

  @Watch('filterKeyword')
  handleFilterKeywordChange() {
    this.getTableData();
  }

  getTableData() {
    this.tableData = (this.data || [])
      .filter(item => (!!this.filterKeyword ? item.name.includes(this.filterKeyword) : true))
      .map(item => {
        const palette = Object.values(ColorTypes);
        const colorIndex = getHashVal(item.name) % palette.length;
        const color = palette[colorIndex];
        return {
          ...item,
          color
        };
      });
    this.localIsCompared = this.isCompared;
  }
  // Self 和 Total 值的展示
  formatColValue(val: number) {
    switch (this.unit) {
      case 'nanoseconds': {
        const nsFormat = getValueFormat('ns');
        const { text, suffix } = nsFormat(val);
        return text + suffix;
      }
      default:
        return '';
    }
  }
  // 获取对应值与列最大值所占百分比背景色
  getColStyle(row: ProfilingTableItem, field: string) {
    const { color } = row;
    const value = row[field] || 0;
    const percent = (value * TABLE_BGCOLOR_COLUMN_WIDTH) / this.maxItem[field];
    let xPosition = TABLE_BGCOLOR_COLUMN_WIDTH - percent;
    if (TABLE_BGCOLOR_COLUMN_WIDTH - 2 < xPosition && xPosition < TABLE_BGCOLOR_COLUMN_WIDTH) {
      xPosition = TABLE_BGCOLOR_COLUMN_WIDTH - 2; // 保留 2px 最小宽度可见
    }

    return {
      'background-image': `linear-gradient(${color}, ${color})`,
      'background-position': `-${xPosition}px 0px`,
      'background-repeat': 'no-repeat'
    };
  }
  /** 列字段排序 */
  handleSort(col: TableColumn) {
    let sortKey;
    switch (col.sort) {
      case 'asc':
        col.sort = 'desc';
        sortKey = `-${col.id}`;
        break;
      case 'desc':
        col.sort = '';
        sortKey = undefined;
        break;
      default:
        col.sort = 'asc';
        sortKey = col.id;
    }
    this.handleSortChange(sortKey);
    this.tableColumns = this.tableColumns.map(item => {
      return {
        ...item,
        sort: col.id === item.id ? col.sort : ''
      };
    });
  }
  handleRowMouseMove(e: MouseEvent, row: ProfilingTableItem) {
    let axisLeft = e.pageX;
    let axisTop = e.pageY;
    if (axisLeft + 394 > window.innerWidth) {
      axisLeft = axisLeft - 394 - 20;
    } else {
      axisLeft = axisLeft + 20;
    }
    if (axisTop + 120 > window.innerHeight) {
      axisTop = axisTop - 120;
    } else {
      axisTop = axisTop;
    }

    const { name, self, total, baseline, comparison, mark = '' } = row;
    const totalItem = this.tableData[0];

    this.tipDetail = {
      left: axisLeft,
      top: axisTop,
      title: name,
      self,
      total,
      baseline,
      comparison,
      mark,
      selfPercent: `${((self / totalItem.self) * 100).toFixed(2)}%`,
      totalPercent: `${((total / totalItem.total) * 100).toFixed(2)}%`
    };
  }
  handleRowMouseout() {
    this.tipDetail = {};
  }
  handleHighlightClick(id) {
    let hightlightId = -1;
    if (this.highlightId !== id) {
      hightlightId = id;
    }
    this.handleHighlightIdChange(hightlightId);
  }

  render() {
    const getDiffTpl = row => {
      if (['removed', 'added'].includes(row.mark)) {
        return <span style={`color: ${row.mark === 'removed' ? '#ff5656' : '#2dcb56'}`}>{row.mark}</span>;
      }

      const { baseline, comparison } = row;
      const diffVal = (baseline - comparison) / comparison;

      if (diffVal === 0) return <span style='color:#dddfe3'>0%</span>;

      return <span style={`color:${diffVal > 0 ? '#ff5656' : '#2dcb56'}`}>{`${(diffVal * 100).toFixed(0)}%`}</span>;
    };

    return (
      <div class='profiling-table-graph'>
        <table class={`profiling-table ${this.localIsCompared ? 'diff-table' : ''}`}>
          <thead>
            {this.tableColumns.map(
              col =>
                (!col.mode ||
                  (this.localIsCompared && col.mode === 'diff') ||
                  (!this.localIsCompared && col.mode === 'normal')) && (
                  <th onClick={() => this.handleSort(col)}>
                    <div class='thead-content'>
                      <span>{col.name}</span>
                      <div class='sort-button'>
                        <i class={`icon-monitor icon-mc-arrow-down asc ${col.sort === 'asc' ? 'active' : ''}`}></i>
                        <i class={`icon-monitor icon-mc-arrow-down desc ${col.sort === 'desc' ? 'active' : ''}`}></i>
                      </div>
                    </div>
                  </th>
                )
            )}
          </thead>
          <tbody>
            {this.tableData.length ? (
              [
                this.tableData.map(row => (
                  <tr
                    class={row.id === this.highlightId ? 'hightlight' : ''}
                    onMousemove={e => this.handleRowMouseMove(e, row)}
                    onMouseout={() => this.handleRowMouseout()}
                    onClick={() => this.handleHighlightClick(row.id)}
                  >
                    <td>
                      <div class='location-info'>
                        <span
                          class='color-reference'
                          style={`background-color: ${!this.localIsCompared ? row.color : '#dcdee5'}`}
                        ></span>
                        <span class={`text direction-${this.textDirection}`}>{row.name}</span>
                        {/* <div class='trace-mark'>Trace</div> */}
                      </div>
                    </td>
                    {this.localIsCompared
                      ? [
                          <td>{this.formatColValue(row.baseline)}</td>,
                          <td>{this.formatColValue(row.comparison)}</td>,
                          <td>{getDiffTpl(row)}</td>
                        ]
                      : [
                          <td style={this.getColStyle(row, 'self')}>{this.formatColValue(row.self)}</td>,
                          <td style={this.getColStyle(row, 'total')}>{this.formatColValue(row.total)}</td>
                        ]}
                  </tr>
                ))
              ]
            ) : (
              <tr>
                <td colspan={3}>
                  <bk-exception
                    class='empty-table-exception'
                    type='search-empty'
                    scene='part'
                    description={this.$t('搜索为空')}
                  />
                </td>
              </tr>
            )}
          </tbody>
        </table>

        <div
          class='table-graph-row-tips'
          style={{
            left: `${this.tipDetail.left || 0}px`,
            top: `${this.tipDetail.top || 0}px`,
            display: this.tipDetail.title ? 'block' : 'none'
          }}
        >
          {this.tipDetail.title && [
            <div class='funtion-name'>{this.tipDetail.title}</div>,
            <table class='tips-table'>
              {this.localIsCompared
                ? [
                    <thead>
                      <th></th>
                      <th>Baseline</th>
                      <th>Comparison</th>
                      <th>Diff</th>
                    </thead>
                  ]
                : [
                    <thead>
                      <th></th>
                      <th>Self (% of total)</th>
                      <th>Total (% of total)</th>
                    </thead>
                  ]}
              {this.localIsCompared ? (
                <tbody>
                  <tr>
                    <td>{this.dataType}</td>
                    <td>{this.formatColValue(this.tipDetail.baseline)}</td>
                    <td>{this.formatColValue(this.tipDetail.comparison)}</td>
                    <td>{getDiffTpl(this.tipDetail)}</td>
                  </tr>
                </tbody>
              ) : (
                <tbody>
                  <tr>
                    <td>{this.dataType}</td>
                    <td>{`${this.formatColValue(this.tipDetail.self)}(${this.tipDetail.selfPercent})`}</td>
                    <td>{`${this.formatColValue(this.tipDetail.total)}(${this.tipDetail.totalPercent})`}</td>
                  </tr>
                </tbody>
              )}
            </table>
          ]}
        </div>
      </div>
    );
  }
}
