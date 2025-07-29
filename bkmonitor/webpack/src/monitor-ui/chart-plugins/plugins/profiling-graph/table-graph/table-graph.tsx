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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  type ProfileDataUnit,
  parseProfileDataTypeValue,
} from 'monitor-ui/chart-plugins/plugins/profiling-graph/utils';

import {
  type ITableTipsDetail,
  type ProfilingTableItem,
  type TableColumn,
  type TextDirectionType,
  ColorTypes,
} from '../../../typings';
import { getHashVal } from '../flame-graph/utils';
import { sortTableGraph } from './utils';

import './table-graph.scss';
const TABLE_PAGE_SIZE = 30;
const TABLE_BGCOLOR_COLUMN_WIDTH = 120;

interface ITableChartEvents {
  onSortChange: string;
  onUpdateHighlightName: string;
}

interface ITableChartProps {
  data: ProfilingTableItem[];
  dataType: string;
  filterKeyword: string;
  highlightName: string;
  isCompared: boolean;
  textDirection: TextDirectionType;
  unit: ProfileDataUnit;
}

@Component
export default class ProfilingTableChart extends tsc<ITableChartProps, ITableChartEvents> {
  @Prop({ required: true, type: String }) unit: ProfileDataUnit;
  @Prop({ required: true, type: String }) textDirection: TextDirectionType;
  @Prop({ required: true, type: Array }) data: ProfilingTableItem[];
  @Prop({ default: '', type: String }) highlightName: string;
  @Prop({ default: '', type: String }) filterKeyword: string;
  @Prop({ default: false, type: Boolean }) isCompared: boolean;
  @Prop({ default: '', type: String }) dataType: string;
  @Ref() tabelLoadingRef: HTMLDivElement;
  maxItem: { self: number; total: number } = {
    self: 0,
    total: 0,
  };
  /** 表格数据 */
  tableData: ProfilingTableItem[] = [];
  tableColumns: TableColumn[] = [
    { id: 'name', name: 'Location', sort: '' },
    { id: 'self', name: 'Self', mode: 'normal', sort: '' },
    { id: 'total', name: 'Total', mode: 'normal', sort: '' },
    { id: 'baseline', name: window.i18n.t('查询项'), mode: 'diff', sort: '' },
    { id: 'comparison', name: window.i18n.t('对比项'), mode: 'diff', sort: '' },
    { id: 'diff', name: 'Diff', mode: 'diff', sort: '' },
  ];
  tipDetail: ITableTipsDetail = {};
  diffMode = false;
  localIsCompared = false;
  sortKey = '';
  sortType = '';
  hiddenLoading = false;
  renderTableData = [];
  intersectionObserver = null;
  @Emit('updateHighlightName')
  handleHighlightNameChange(val: string) {
    return val;
  }

  @Emit('sortChange')
  handleSortChange(sortKey) {
    return sortKey;
  }

  @Watch('data', { immediate: true })
  handleDataChange(val: ProfilingTableItem[]) {
    this.maxItem = {
      self: Math.max(...val.map(item => item.self)),
      total: Math.max(...val.map(item => item.total)),
    };
    this.sortKey = '';
    this.getTableData();
    this.tableColumns = this.tableColumns.map(item => ({ ...item, sort: '' }));
  }

  @Watch('filterKeyword')
  handleFilterKeywordChange() {
    this.getTableData();
  }

  getTableData() {
    const copyData = structuredClone(this.data || []);
    const filterList = copyData
      .filter(item =>
        this.filterKeyword ? item.name.toLocaleLowerCase().includes(this.filterKeyword.toLocaleLowerCase()) : true
      )
      .map(item => {
        const palette = Object.values(ColorTypes);
        const colorIndex = getHashVal(item.name) % palette.length;
        const color = palette[colorIndex];
        return {
          ...item,
          color,
        };
      });
    this.tableData = Object.freeze(sortTableGraph(filterList, this.sortKey, this.sortType));
    this.renderTableData = this.tableData.slice(0, TABLE_PAGE_SIZE);
    this.handleTriggerObserver();
    this.localIsCompared = this.isCompared;
  }
  // Self 和 Total 值的展示
  formatColValue(val: number) {
    const { value } = parseProfileDataTypeValue(val, this.unit);
    return value;
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
      'background-repeat': 'no-repeat',
    };
  }
  /** 列字段排序 */
  handleSort(col: TableColumn) {
    switch (col.sort) {
      case 'asc':
        col.sort = 'desc';
        this.sortType = 'desc';
        this.sortKey = col.id;
        break;
      case 'desc':
        col.sort = '';
        this.sortType = '';
        this.sortKey = undefined;
        break;
      default:
        col.sort = 'asc';
        this.sortType = 'asc';
        this.sortKey = col.id;
    }
    this.handleSortChange(this.sortKey);
    this.getTableData();
    this.tableColumns = this.tableColumns.map(item => {
      return {
        ...item,
        sort: col.id === item.id ? col.sort : '',
      };
    });
  }
  handleRowMouseMove(e: MouseEvent, row: ProfilingTableItem) {
    let axisLeft = e.pageX;
    let axisTop = e.pageY;
    if (axisLeft + 360 > window.innerWidth) {
      axisLeft = axisLeft - 360 - 20;
    } else {
      axisLeft = axisLeft + 20;
    }
    if (axisTop + 120 > window.innerHeight) {
      axisTop = axisTop - 120;
    }

    const { name, self, total, baseline, comparison, mark = '', diff = 0 } = row;
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
      diff,
      selfPercent: `${((self / totalItem.self) * 100).toFixed(2)}%`,
      totalPercent: `${((total / totalItem.total) * 100).toFixed(2)}%`,
    };
  }
  handleRowMouseout() {
    this.tipDetail = {};
  }
  handleHighlightClick(name) {
    let highlightName = '';
    if (this.highlightName !== name) {
      highlightName = name;
    }
    this.handleHighlightNameChange(highlightName);
  }
  isInViewport(element: Element) {
    const rect = element.getBoundingClientRect();
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
  }
  handleTriggerObserver() {
    this.hiddenLoading = true;
    window.requestIdleCallback(() => {
      this.hiddenLoading = false;
    });
  }

  observerTableLoading() {
    this.intersectionObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.intersectionRatio <= 0) return;
        if (this.renderTableData.length >= this.tableData.length) return;
        this.renderTableData.push(
          ...this.tableData.slice(this.renderTableData.length, this.renderTableData.length + TABLE_PAGE_SIZE)
        );
        this.$nextTick(() => {
          if (this.isInViewport(this.tabelLoadingRef) && this.renderTableData.length < this.tableData.length) {
            this.handleTriggerObserver();
          }
        });
      }
    });
    this.intersectionObserver.observe(this.tabelLoadingRef);
  }
  mounted() {
    this.observerTableLoading();
  }
  beforeDestroy() {
    this.intersectionObserver?.unobserve(this.tabelLoadingRef);
  }
  render() {
    const getDiffTpl = row => {
      if (['removed', 'added'].includes(row.mark)) {
        return <span style={`color: ${row.mark === 'removed' ? '#ff5656' : '#2dcb56'}`}>{row.mark}</span>;
      }

      const { diff } = row;

      if (diff === 0) return <span style='color:#dddfe3'>0%</span>;

      return <span style={`color:${diff > 0 ? '#ff5656' : '#2dcb56'}`}>{`${(diff * 100).toFixed(2)}%`}</span>;
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
                        <i class={`icon-monitor icon-mc-arrow-down asc ${col.sort === 'asc' ? 'active' : ''}`} />
                        <i class={`icon-monitor icon-mc-arrow-down desc ${col.sort === 'desc' ? 'active' : ''}`} />
                      </div>
                    </div>
                  </th>
                )
            )}
          </thead>
          <tbody>
            {this.tableData.length ? (
              [
                this.renderTableData.map(row => (
                  <tr
                    key={row.id}
                    class={row.name === this.highlightName ? 'highlight' : ''}
                    onClick={() => this.handleHighlightClick(row.name)}
                    onMousemove={e => this.handleRowMouseMove(e, row)}
                    onMouseout={() => this.handleRowMouseout()}
                  >
                    <td>
                      <div class='location-info'>
                        <span
                          style={`background-color: ${!this.localIsCompared ? row.color : '#dcdee5'}`}
                          class='color-reference'
                        />
                        <span class={`text direction-${this.textDirection}`}>{row.name}</span>
                        {/* <div class='trace-mark'>Trace</div> */}
                      </div>
                    </td>
                    {this.localIsCompared
                      ? [
                          <td key={1}>{this.formatColValue(row.baseline)}</td>,
                          <td key={2}>{this.formatColValue(row.comparison)}</td>,
                          <td key={3}>{getDiffTpl(row)}</td>,
                        ]
                      : [
                          <td
                            key={1}
                            style={this.getColStyle(row, 'self')}
                          >
                            {this.formatColValue(row.self)}
                          </td>,
                          <td
                            key={2}
                            style={this.getColStyle(row, 'total')}
                          >
                            {this.formatColValue(row.total)}
                          </td>,
                        ]}
                  </tr>
                )),
              ]
            ) : (
              <tr>
                <td colspan={3}>
                  <bk-exception
                    class='empty-table-exception'
                    description={this.$t('搜索为空')}
                    scene='part'
                    type='search-empty'
                  />
                </td>
              </tr>
            )}
            <tr>
              <td colspan={3}>
                <div
                  ref='tabelLoadingRef'
                  style={{
                    display:
                      this.hiddenLoading || this.tableData.length <= this.renderTableData.length ? 'none' : 'flex',
                  }}
                  class='table-loading'
                >
                  {this.$t('加载中...')}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <div
          style={{
            left: `${this.tipDetail.left || 0}px`,
            top: `${this.tipDetail.top || 0}px`,
            display: this.tipDetail.title ? 'block' : 'none',
          }}
          class='table-graph-row-tips'
        >
          {this.tipDetail.title && [
            <div
              key={1}
              class='funtion-name'
            >
              {this.tipDetail.title}
            </div>,
            <table
              key={2}
              class='tips-table'
            >
              {this.localIsCompared
                ? [
                    <thead key={1}>
                      <th />
                      <th>{this.$t('当前')}</th>
                      <th>{this.$t('参照')}</th>
                      <th>{this.$t('差异')}</th>
                    </thead>,
                  ]
                : [
                    <thead key={1}>
                      <th />
                      <th>Self (% of total)</th>
                      <th>Total (% of total)</th>
                    </thead>,
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
            </table>,
          ]}
        </div>
      </div>
    );
  }
}
