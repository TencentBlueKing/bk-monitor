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
import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import './rum-explore-skeleton.scss';

export const RUM_TABLE_SKELETON_ROW_COUNT = 12;

const line = (width: number | string, className = '') => (
  <span
    style={{ width: typeof width === 'number' ? `${width}px` : width }}
    class={['rum-skeleton-line', className]}
  />
);

/** 在真实表格单元格内占位，列宽、固定列及横向滚动由表格本身保持。 */
export function renderRumLoadingCell(field: string, rowIndex: number) {
  if (field === '__col_setting__') return null;
  const width = [72, 88, 60, 80, 66][rowIndex % 5];
  const isType = field === 'attributes.span_type' || field === 'kind';
  const isStatus = field === 'status.code' || field === 'attributes.outcome.type' || field.endsWith('status_code');
  const isDuration = field === 'elapsed_time' || field.endsWith('duration');
  return (
    <div
      class='rum-skeleton-cell'
      aria-hidden='true'
    >
      {isType && line(14, 'rum-skeleton-icon')}
      {line(isStatus ? 48 : isDuration ? 52 : `${width}%`, isStatus ? 'rum-skeleton-tag' : '')}
      {isDuration && line(16, 'rum-skeleton-unit')}
    </div>
  );
}

export default defineComponent({
  name: 'RumExploreSkeleton',
  props: {
    kind: {
      type: String as PropType<'dimension' | 'filter' | 'table' | 'types'>,
      required: true,
    },
    showResident: {
      type: Boolean,
      default: false,
    },
  },
  setup() {
    const { t } = useI18n();
    return { t };
  },
  render() {
    let content;
    if (this.kind === 'filter') {
      content = (
        <>
          <div class='rum-skeleton-query'>
            <div class='rum-skeleton-mode'>
              {line(28)}
              {line(12, 'rum-skeleton-icon')}
            </div>
            <div class='rum-skeleton-query-input'>{line('38%')}</div>
            <div class='rum-skeleton-query-actions'>
              {[0, 1, 2].map(key => (
                <span key={key}>{line(16, 'rum-skeleton-icon')}</span>
              ))}
            </div>
          </div>
          {this.showResident && (
            <div class='rum-skeleton-resident'>
              {[148, 180, 160].map(width => (
                <div
                  key={width}
                  style={{ width: `${width}px` }}
                  class='rum-skeleton-control'
                >
                  {line(40)}
                  {line('40%')}
                  {line(10, 'rum-skeleton-icon')}
                </div>
              ))}
            </div>
          )}
        </>
      );
    } else if (this.kind === 'dimension') {
      content = (
        <>
          <div class='rum-skeleton-panel-title'>
            {line(14, 'rum-skeleton-icon')}
            {line(68)}
            {line(32, 'rum-skeleton-tag')}
          </div>
          <div class='rum-skeleton-search'>
            {line(14, 'rum-skeleton-icon')}
            {line(56)}
          </div>
          {[3, 4, 3].map((count, group) => (
            <div
              key={group}
              class='rum-skeleton-group'
            >
              <div class='rum-skeleton-group-title'>
                {line(12, 'rum-skeleton-icon')}
                {line(64 + group * 12)}
                {line(18, 'rum-skeleton-tag')}
              </div>
              {Array.from({ length: count }, (_, index) => (
                <div
                  key={index}
                  class='rum-skeleton-field'
                >
                  {line(12, 'rum-skeleton-icon')}
                  {line(`${[64, 48, 72, 56][index]}%`)}
                </div>
              ))}
            </div>
          ))}
        </>
      );
    } else if (this.kind === 'types') {
      content = (
        <>
          <div class='rum-skeleton-type-label'>{line(56)}</div>
          <div class='rum-skeleton-chips'>
            {[52, 82, 104, 76, 88, 98].map((width, index) => (
              <div
                key={width}
                style={{ width: `${width}px` }}
                class='rum-skeleton-chip'
              >
                {!!index && line(14, 'rum-skeleton-icon')}
                {line(index ? '60%' : 24)}
              </div>
            ))}
          </div>
        </>
      );
    } else {
      // 字段接口尚未返回时只占据结构；配置就绪后切换到真实列的 loadingCell。
      const columns = [
        'span_name',
        'attributes.span_type',
        'start_time',
        'elapsed_time',
        'status.code',
        'attributes.view.url_template',
      ];
      content = (
        <div class='rum-skeleton-table-content'>
          <div class='rum-skeleton-table-header'>
            {columns.map(field => (
              <div key={field}>{line(64)}</div>
            ))}
          </div>
          {Array.from({ length: RUM_TABLE_SKELETON_ROW_COUNT }, (_, row) => (
            <div
              key={row}
              class='rum-skeleton-table-row'
            >
              {columns.map(field => (
                <div key={field}>{renderRumLoadingCell(field, row)}</div>
              ))}
            </div>
          ))}
        </div>
      );
    }
    return (
      <div
        class={['rum-skeleton', `rum-skeleton-${this.kind}`]}
        aria-label={this.t('加载中...')}
        role='status'
      >
        <div
          class='rum-skeleton-content'
          aria-hidden='true'
        >
          {content}
        </div>
      </div>
    );
  },
});
