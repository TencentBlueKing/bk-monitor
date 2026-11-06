/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './collector-config-skeleton.scss';

interface IProps {
  columns?: ISkeletonColumn[];
  operationWidth?: number;
  rowCount?: number;
  section?: 'stats' | 'table';
  size?: string;
  tabCount?: number;
}

interface ISkeletonColumn {
  label: string;
  minWidth?: number;
  prop: string;
  width?: number;
}

@Component
export default class CollectorConfigSkeleton extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) columns: ISkeletonColumn[];
  @Prop({ type: Number, default: 260 }) operationWidth: number;
  @Prop({ type: Number, default: 10 }) rowCount: number;
  @Prop({ type: String, default: 'table' }) section: IProps['section'];
  @Prop({ type: String, default: 'small' }) size: string;
  @Prop({ type: Number, default: 4 }) tabCount: number;

  get tableColumns(): ISkeletonColumn[] {
    return [
      ...this.columns,
      { prop: 'operation', label: String(this.$t('操作')), width: this.operationWidth },
      { prop: 'setting', label: '', width: 42 },
    ];
  }

  get rowHeight() {
    const height = { small: 43, medium: 54, large: 72 }[this.size] || 43;
    return this.columns.some(column => column.prop === 'updateUser') ? Math.max(height, 59) : height;
  }

  renderBar(width: string, className = '') {
    return (
      <span
        style={{ width }}
        class={['skeleton-element', className]}
      />
    );
  }

  renderCell(column: ISkeletonColumn, row: number, index: number) {
    if (column.prop === 'setting') return null;
    if (column.prop === 'operation') {
      return (
        <div class='skeleton-actions'>
          {this.renderBar('48px')}
          {this.renderBar('36px')}
          {this.renderBar('24px')}
          {this.renderBar('12px')}
        </div>
      );
    }
    if (column.prop === 'updateUser') {
      return (
        <div class='skeleton-update'>
          {this.renderBar(`${48 + (row % 3) * 12}px`)}
          {this.renderBar('132px', 'skeleton-secondary')}
        </div>
      );
    }
    if (column.prop === 'status') {
      return (
        <div class='skeleton-status'>
          {this.renderBar('8px', 'skeleton-dot')}
          {this.renderBar('48px')}
        </div>
      );
    }
    return this.renderBar(column.prop === 'id' ? '30px' : `${[64, 82, 48, 72][(row + index) % 4]}%`);
  }

  render() {
    if (this.section === 'stats') {
      return (
        <div
          class='collector-config-skeleton skeleton-stats'
          aria-hidden='true'
        >
          <div class='skeleton-tabs'>
            {Array.from({ length: this.tabCount }, (_, index) => (
              <div
                key={index}
                class='skeleton-tab'
              >
                {this.renderBar(`${[42, 56, 48, 64][index % 4]}px`)}
                {this.renderBar('24px', 'skeleton-badge')}
              </div>
            ))}
          </div>
          <div class='skeleton-metrics'>
            {Array.from({ length: 4 }, (_, index) => (
              <div
                key={index}
                class='skeleton-metric'
              >
                {this.renderBar(`${[54, 38, 46, 38][index]}px`, 'skeleton-number')}
                {this.renderBar('72px', 'skeleton-secondary')}
              </div>
            ))}
          </div>
        </div>
      );
    }

    const columns = this.tableColumns;
    const gridStyle = {
      gridTemplateColumns: columns
        .map(column => (column.width ? `${column.width}px` : `minmax(${column.minWidth}px, ${column.minWidth}fr)`))
        .join(' '),
      minWidth: `${columns.reduce((width, column) => width + (column.width || column.minWidth), 0)}px`,
    };
    return (
      <div
        class='collector-config-skeleton skeleton-table'
        aria-hidden='true'
      >
        <div class='skeleton-table-scroll'>
          <div
            style={gridStyle}
            class='skeleton-table-header'
          >
            {columns.map(column => (
              <div
                key={column.prop}
                class='skeleton-cell'
              >
                {column.label}
              </div>
            ))}
          </div>
          {Array.from({ length: this.rowCount }, (_, row) => (
            <div
              key={row}
              style={{ ...gridStyle, height: `${this.rowHeight}px` }}
              class='skeleton-table-row'
            >
              {columns.map((column, index) => (
                <div
                  key={column.prop}
                  class='skeleton-cell'
                >
                  {this.renderCell(column, row, index)}
                </div>
              ))}
            </div>
          ))}
        </div>
        <div class='skeleton-pagination'>
          {this.renderBar('112px')}
          <div class='skeleton-pages'>
            {this.renderBar('64px')}
            {this.renderBar('24px', 'skeleton-page')}
            {this.renderBar('24px', 'skeleton-page')}
            {this.renderBar('24px', 'skeleton-page')}
            {this.renderBar('56px')}
          </div>
        </div>
      </div>
    );
  }
}
