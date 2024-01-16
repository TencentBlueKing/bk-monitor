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
import { PropType } from 'vue/types/options';
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Exception } from 'bk-magic-vue';

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
}

interface ITableChartEvents {
  onUpdateHighlightId: number;
}

@Component
export default class ProfilingTableChart extends tsc<ITableChartProps, ITableChartEvents> {
  @Prop({ required: true, type: String }) unit: string;
  @Prop({ required: true, type: String }) textDirection: TextDirectionType;
  @Prop({ required: true, type: Array as PropType<ProfilingTableItem[]> }) data: ProfilingTableItem[];
  @Prop({ default: -1, type: Number }) highlightId: number;
  @Prop({ default: '', type: String }) filterKeyword: string;

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

  @Emit('updateHighlightId')
  handleHighlightIdChange(val: number) {
    return val;
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
          color,
          displaySelf: this.formatColValue(item.self),
          displayTotal: this.formatColValue(item.total)
        };
      });
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
    const xPosition = TABLE_BGCOLOR_COLUMN_WIDTH - percent;

    return {
      'background-image': `linear-gradient(${color}, ${color})`,
      'background-position': `-${xPosition}px 0px`,
      'background-repeat': 'no-repeat'
    };
  }
  /** 列字段排序 */
  handleSort(col: TableColumn) {
    col.sort = col.sort === 'desc' ? 'asc' : 'desc';
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

    const { name, displaySelf, displayTotal, self, total } = row;
    const totalItem = this.tableData[0];

    this.tipDetail = {
      left: axisLeft,
      top: axisTop,
      title: name,
      displaySelf,
      displayTotal,
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
    return (
      <div class='profiling-table-graph'>
        <table class={`profiling-table ${this.diffMode ? 'diff-table' : ''}`}>
          <thead>
            {this.tableColumns.map(
              col =>
                (!col.mode || (this.diffMode && col.mode === 'diff') || (!this.diffMode && col.mode === 'normal')) && (
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
                          style={`background-color: ${row.color}`}
                        ></span>
                        <span class={`text direction-${this.textDirection}`}>{row.name}</span>
                        {/* <div class='trace-mark'>Trace</div> */}
                      </div>
                    </td>
                    {this.diffMode
                      ? [
                          <td>59%</td>,
                          <td>59%</td>,
                          <td>
                            <span class={`diff-value ${false ? 'is-rise' : 'is-decline'}`}>+45%</span>
                          </td>
                        ]
                      : [
                          <td style={this.getColStyle(row, 'self')}>{row.displaySelf}</td>,
                          <td style={this.getColStyle(row, 'total')}>{row.displayTotal}</td>
                        ]}
                  </tr>
                ))
              ]
            ) : (
              <tr>
                <td colspan={3}>
                  <Exception
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
              <thead>
                <th></th>
                <th>Self (% of total)</th>
                <th>Total (% of total)</th>
              </thead>
              <tbody>
                <tr>
                  <td>&nbsp;&nbsp;</td>
                  <td>{`${this.tipDetail.displaySelf}(${this.tipDetail.selfPercent})`}</td>
                  <td>{`${this.tipDetail.displayTotal}(${this.tipDetail.totalPercent})`}</td>
                </tr>
              </tbody>
            </table>
          ]}
        </div>
      </div>
    );
  }
}
