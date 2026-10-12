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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import './rum-events-skeleton.scss';

/** 骨架屏占位行数 */
const SKELETON_ROW_COUNT = 10;

/** 序号列宽，与抽屉真实表格一致 */
const INDEX_COLUMN_WIDTH = 64;

/**
 * @description 单元格骨架：在真实表格单元格内占位，表头与列宽由表格本身保持。
 *              用于「列集合不变、只换行数据」的场景，视觉与整体骨架同源。
 * @param {string} colKey 列键，序号列走短条
 * @param {number} rowIndex 行下标，用于错落线条宽度
 * @returns {JSX.Element} 单元格骨架
 */
export function renderEventsLoadingCell(colKey: string, rowIndex: number) {
  /** 整体骨架按 (row + column) 错落，此处只有行下标可用，退化为按行错落 */
  const width = colKey === 'index' ? 14 : `${[72, 48, 60, 80][rowIndex % 4]}%`;
  return (
    <span
      style={{ width: typeof width === 'number' ? `${width}px` : width }}
      class='events-skeleton-line'
      aria-hidden='true'
    />
  );
}

export default defineComponent({
  name: 'RumEventsSkeleton',
  props: {
    /** events 列数（不含序号列） */
    columnCount: {
      type: Number,
      required: true,
    },
    /** events 列宽，与抽屉真实表格列宽一致 */
    columnWidth: {
      type: Number,
      required: true,
    },
  },
  setup() {
    const { t } = useI18n();
    return { t };
  },
  render() {
    /** 列少时 events 列按 1fr 摊满容器避免右侧留白，列多时保底列宽与真实表格一致 */
    const gridTemplateColumns = `${INDEX_COLUMN_WIDTH}px repeat(${Math.max(this.columnCount, 1)}, minmax(${this.columnWidth}px, 1fr))`;
    const cell = (key: string, width: number | string) => (
      <div key={key}>
        <span
          style={{ width: typeof width === 'number' ? `${width}px` : width }}
          class='events-skeleton-line'
        />
      </div>
    );
    return (
      <div
        class='events-skeleton'
        aria-label={this.t('加载中...')}
        role='status'
      >
        <div
          class='events-skeleton-content'
          aria-hidden='true'
        >
          <div
            style={{ gridTemplateColumns }}
            class='events-skeleton-header'
          >
            {cell('index', 16)}
            {Array.from({ length: this.columnCount }, (_, column) => cell(`h${column}`, 64))}
          </div>
          {Array.from({ length: SKELETON_ROW_COUNT }, (_, row) => (
            <div
              key={row}
              style={{ gridTemplateColumns }}
              class='events-skeleton-row'
            >
              {cell(`i${row}`, 14)}
              {Array.from({ length: this.columnCount }, (_, column) =>
                cell(`${row}-${column}`, `${[72, 48, 60, 80][(row + column) % 4]}%`)
              )}
            </div>
          ))}
        </div>
      </div>
    );
  },
});
