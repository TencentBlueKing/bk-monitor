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
import { Component, Prop, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { xssFilter } from 'monitor-common/utils/xss';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { timeOffsetDateFormat } from 'monitor-pc/pages/monitor-k8s/components/group-compare-select/utils';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats/valueFormats';
import { Table as TTable, ConfigProvider as TConfigProvider } from 'tdesign-vue';

import { typeEnums } from '../../metric-chart-view/utils';

import type { IColumnItem, IDataItem } from 'monitor-pc/pages/custom-escalation/new-metric-view/type';
import type { ILegendItem } from 'monitor-ui/chart-plugins/typings';
import type { CreateElement } from 'vue';

import './check-view-table.scss';
import 'tdesign-vue/es/style/index.css';

interface ITableData {
  time: string;
  date: number;
  rowKey: number;
  [key: string]: any;
}

interface IFooterData {
  [key: string]: any;
}

@Component
export default class CheckViewTable extends tsc<object, object> {
  @Prop({ default: () => ({}) }) data: { series: IDataItem[] };
  @Prop({ default: () => [] }) legendData: ILegendItem[];
  @Prop({ default: true }) isShowStatistical: boolean;
  @Prop({ default: true }) loading: boolean;
  @Prop({ default: false }) isHasCompare: boolean;
  @Prop({ default: false }) isHasDimensions: boolean;
  @Prop({ default: () => [] }) hoverPoint: number[];
  @Prop({ default: '' }) title: string;
  @Prop({ default: () => [] }) compare: string[];
  @Ref('dataTable') dataTableRef: HTMLElement;
  @Ref('checkViewTable') checkViewTableRef: HTMLElement;

  firstColumn: IColumnItem[] = [
    {
      title: 'Time',
      colKey: 'time',
      minWidth: '180',
      sortType: 'all',
      sorter: true,
      fixed: 'left',
    },
  ];

  fluctuationColumn: IColumnItem[] = [
    {
      label: this.$t('波动') as string,
      title: this.renderColorHead,
      colKey: 'fluctuation0',
      render: this.renderFluctuationCol,
    },
  ];

  baseColumnConfig = {
    title: this.renderColorHead,
    render: this.renderCol,
    foot: this.renderFooter,
    ellipsisTitle: true,
    minWidth: '180',
  };

  selectLegendKey = '';
  sort = {};
  timeData: ITableData[] = [];
  tableData: ITableData[] = [];
  footerDataList: IFooterData[] = [];
  defaultHeight = 400;
  maxHeight = 0;

  globalLocale = {
    table: {
      sortIcon: (h: CreateElement) => h && <i class='icon-monitor icon-mc-arrow-down sort-icon' />,
    },
  };

  worker: null | Worker = null;

  @Watch('loading')
  handleLoading() {
    this.initTableData();
    this.selectLegendKey = '';
  }

  @Watch('hoverPoint')
  handleHoverPoint(val: { value: number }) {
    const { value } = val;
    if (!value) return;
    const targetValue = value;
    const index = this.tableData.findIndex(row => row.date === targetValue);

    const table = this.dataTableRef;
    if (!table?.$el) return;

    const tableBody = table.$el.querySelector('.t-table__body');
    if (!tableBody) return;

    const rows = tableBody.querySelectorAll('tbody tr');
    rows.forEach(row => row.classList.remove('highlight-row'));

    if (index !== -1 && index < rows.length) {
      rows[index].classList.add('highlight-row');
      this.scrollToRow(index);
    }
  }

  mounted() {
    this.initializeTableHeight();
    const resizeObserver = new ResizeObserver(() => {
      this.initializeTableHeight();
    });

    if (this.checkViewTableRef) {
      resizeObserver.observe(this.checkViewTableRef);
    }

    // 组件销毁时清理
    this.$once('hook:beforeDestroy', () => {
      resizeObserver.disconnect();
      if (this.worker) {
        this.worker.terminate();
      }
    });
  }

  get isMergeTable(): boolean {
    return this.isHasCompare && this.isHasDimensions;
  }

  get isCompareNotDimensions(): boolean {
    return this.isHasCompare && !this.isHasDimensions;
  }

  get baseData() {
    const len = Object.keys(this.data).length;
    const columnsData = this.classifyData(this.legendData);

    if (this.data && len > 0) {
      const { series } = this.data;
      this.timeData = [];
      const timeList = series[0]?.datapoints || [];
      this.timeData = timeList.map(item => ({
        time: dayjs(item[1]).format('YYYY-MM-DD HH:mm:ss'),
        date: item[1],
        rowKey: item[1],
      }));
      return {
        data: this.classifyData(series),
        columns: columnsData,
      };
    }
    return {};
  }

  get compareColumn(): IColumnItem[] {
    const { columns = [] } = this.baseData;
    return this.isCompareNotDimensions
      ? this.generateSimpleCompareColumns(columns)
      : this.generateDimensionCompareColumns(columns);
  }

  get columns(): IColumnItem[] {
    return this.isCompareNotDimensions
      ? [...this.firstColumn, ...this.compareColumn, ...this.fluctuationColumn]
      : [...this.firstColumn, ...this.compareColumn];
  }

  get footerData(): IFooterData[] {
    return this.tableData.length > 0 && this.isShowStatistical ? this.footerDataList : [];
  }

  initializeTableHeight() {
    setTimeout(() => {
      if (!this.checkViewTableRef) return;
      const height = this.checkViewTableRef.offsetHeight - 2;
      this.maxHeight = height < this.defaultHeight ? this.defaultHeight : height;
    });
  }

  scrollToRow(index: number): void {
    const table = this.dataTableRef;
    if (!table?.$el) return;

    requestAnimationFrame(() => {
      const tableBody = table.$el.querySelector('.t-table__content');
      if (!tableBody) return;

      const rows = tableBody.querySelectorAll('tr');
      if (rows.length <= index) return;

      const row = rows[index];
      const rowTop = row.offsetTop;
      const rowHeight = row.offsetHeight;
      const tableHeight = tableBody.clientHeight;
      const offset = this.isShowStatistical ? 64 : 32;
      const scrollPosition = rowTop - (tableHeight - rowHeight) / 2 + offset;

      tableBody.scrollTo({
        top: scrollPosition,
        behavior: 'smooth',
      });
    });
  }
  handleAddCol(item: IColumnItem) {
    const len = item.items.length;
    if (len === 1) {
      item.items.push({
        timeOffset: this.compare[0],
      });
    }
  }
  generateSimpleCompareColumns(columns: IColumnItem[]): IColumnItem[] {
    const firstColumn = columns[0] || { items: [] };
    this.handleAddCol(firstColumn);
    return firstColumn.items.map((ele: any) => ({
      ...ele,
      ...this.baseColumnConfig,
      label: this.formatTimeOffset(ele.timeOffset),
      colKey: ele.timeOffset,
    }));
  }

  generateDimensionCompareColumns(columns: IColumnItem[]): IColumnItem[] {
    return columns.map((item: any, index: number) => {
      const title = this.handleProp(item) || '';
      const baseConfig = {
        ...item,
        ...this.baseColumnConfig,
        label: title || this.title,
        colKey: `${title}${item.timeOffset || 'current'}`,
      };

      if (this.isMergeTable) {
        const children = this.generateMergeTableChildren(item, index, title);
        return { ...baseConfig, children };
      }

      const firstColumn = item.items[0] || {};
      return {
        ...baseConfig,
        ...firstColumn,
      };
    });
  }

  generateMergeTableChildren(item: IColumnItem, parentIndex: number, parentKey: string): IColumnItem[] {
    this.handleAddCol(item);
    const children = item.items.map((ele: any, ind: number) => ({
      ...ele,
      ...this.baseColumnConfig,
      label: this.formatTimeOffset(ele.timeOffset),
      colKey: `${parentKey}${ele.timeOffset}${ind}`,
    }));

    children.push({
      label: this.$t('波动') as string,
      title: this.renderColorHead,
      colKey: `fluctuation${parentIndex}`,
      render: this.renderFluctuationCol,
      ellipsisTitle: true,
    });

    return children;
  }

  renderValue(row: IDataItem, prop: string, unit: string): JSX.Element | string {
    if (row[prop] === undefined || row[prop] === null) {
      return '--';
    }
    const unitFormatter = getValueFormat(unit);
    const set: any = unitFormatter(row[prop], 2);
    return (
      <span>
        {set.text} {set.suffix}
      </span>
    );
  }

  renderCol(h: CreateElement, { row, col }: { row: IDataItem; col: IColumnItem }): JSX.Element {
    return <span>{this.renderValue(row, col.colKey, row.unit)}</span>;
  }

  renderFluctuationCol(h: CreateElement, { row, col }: { row: IDataItem; col: IColumnItem }): JSX.Element {
    const data = row[col.colKey];
    const isFix = data !== '--' && data !== 0 && data !== undefined;
    const color = data >= 0 ? '#3AB669' : '#E91414';
    return <span style={{ color: isFix ? color : '#313238' }}>{isFix ? `${data.toFixed(2)}%` : '--'}</span>;
  }

  renderColorHead(h: CreateElement, { col }: { col: IColumnItem }): JSX.Element {
    return (
      <span
        class={[
          'header-cell',
          {
            disabled: this.selectLegendKey && this.selectLegendKey !== col.colKey,
          },
        ]}
        v-bk-tooltips={this.renderTipsContent(col)}
        onClick={e => this.handleRowClick(e, col)}
      >
        {col.color && (
          <span
            style={{
              backgroundColor: col.color,
            }}
            class='color-box'
          />
        )}
        <span class='title'>{col.label}</span>
      </span>
    );
  }

  handleRowClick(e: Event, item: IColumnItem): void {
    e.stopPropagation();
    if (!item.color) {
      return;
    }
    this.selectLegendKey = this.selectLegendKey === item.colKey ? '' : item.colKey;
    this.$emit('headClick', item);
  }

  formatTimeOffset(timeOffset?: string): string {
    return typeEnums[timeOffset] || timeOffsetDateFormat(timeOffset) || '';
  }

  handleProp(item: IDataItem): string {
    const dimensions = Object.values(item.dimensions || {});
    return dimensions.length > 0 ? dimensions.join(' | ') : item.target;
  }

  classifyData(data: ILegendItem[]): any[] {
    const byDimensions = new Map<string, any[]>();
    // biome-ignore lint/complexity/noForEach: <explanation>
    data.forEach(item => {
      const dimensionsKey = JSON.stringify(item.dimensions);
      if (!byDimensions.has(dimensionsKey)) {
        byDimensions.set(dimensionsKey, []);
      }
      // biome-ignore lint/style/noNonNullAssertion: <explanation>
      byDimensions.get(dimensionsKey)!.push(item);
    });

    return Array.from(byDimensions.entries()).map(([dimensionsKey, items]) => ({
      dimensions: JSON.parse(dimensionsKey),
      items,
    }));
  }

  initTableData(): void {
    const { data = [], columns = [] } = this.baseData;
    const compare = [...['current'], ...this.compare];

    if (this.worker) {
      this.worker.terminate();
    }

    this.worker = new Worker(new URL('./tableDataWorker.ts', import.meta.url));

    this.worker.onmessage = e => {
      const { tableData, footerDataList, origin } = e.data;
      if (origin === window.location.origin) {
        this.tableData = tableData;
        this.footerDataList = footerDataList;
      }
      this.worker?.terminate();
      this.worker = null;
    };

    this.worker.postMessage({
      data,
      columns,
      compare,
      timeData: this.timeData,
      isCompareNotDimensions: this.isCompareNotDimensions,
      isMergeTable: this.isMergeTable,
      origin: window.location.origin,
    });
  }

  renderFooter(h: CreateElement, { col, row }: { col: IColumnItem; row: IDataItem }): JSX.Element {
    return (
      <span class='num-cell'>
        {row[col.colKey]}
        {row[`${col.colKey}Time`] && <span class='gray-text'>@{dayjs(row[`${col.colKey}Time`]).format('HH:mm')}</span>}
      </span>
    );
  }

  renderTipsContent(item: IColumnItem): any {
    let name = item.name;
    if (this.isMergeTable && item.items) {
      name = item.items[0]?.name || '';
    }
    const disabled = (!this.isMergeTable && !item.name) || !this.isHasDimensions || (this.isMergeTable && !item.items);
    const tipContent = `<span class='head-tips-view'>
      <span class='tips-name'>${this.$t('维度（组合）')}</span><br/>
      ${
        (name || '')
          .split('|')
          .map((item: string, ind: number) => {
            const className = ind % 2 !== 0 ? 'tips-item' : 'tips-item-even';
            const begin = item.indexOf('-');
            const index = item.indexOf('=');
            return `<span class=${className}><label class='item-name'>${xssFilter(
              item.slice(begin + 1, index)
            )}</label>：${xssFilter(item.slice(index + 1))}</span><br/>`;
          })
          .join('') || ''
      }
    </span>`;
    return {
      extCls: 'check-view-tooltips',
      content: tipContent,
      allowHTML: true,
      placement: 'bottom-start',
      disabled,
    };
  }

  sortChange(sortInfo: { sortBy?: string; descending?: boolean }): void {
    this.sort = sortInfo;
    this.handleSort(sortInfo);
  }

  handleSort(sort: { sortBy?: string; descending?: boolean }): void {
    if (sort) {
      this.tableData = this.timeData.concat().sort((a, b) => (sort.descending ? b.date - a.date : a.date - b.date));
    } else {
      this.tableData = this.timeData.concat();
    }
  }

  render() {
    return (
      <div
        ref='checkViewTable'
        class='check-view-table'
      >
        {this.loading ? (
          <TableSkeleton
            class='table-skeleton-block'
            type={1}
          />
        ) : (
          <TConfigProvider
            class='check-view-table-main'
            globalConfig={this.globalLocale}
          >
            <TTable
              ref='dataTable'
              bordered={'bordered'}
              cache={true}
              columns={this.columns}
              data={this.tableData}
              foot-data={this.footerData}
              max-height={this.maxHeight}
              row-key='key'
              rowHeight={32}
              scroll={{ type: 'lazy', bufferSize: 10 }}
              sort={this.sort}
              virtual={true}
              on-sort-change={this.sortChange}
            />
            {/* 底部显示/隐藏统计值 */}
            <div
              style={{ bottom: this.isShowStatistical ? '155px' : '0' }}
              class='table-foot-btn'
              onClick={() => {
                this.$emit('toggle', !this.isShowStatistical);
              }}
            >
              <i class={`icon-monitor icon-arrow-${this.isShowStatistical ? 'down' : 'up'} foot-btn`} />
            </div>
          </TConfigProvider>
        )}
      </div>
    );
  }
}
