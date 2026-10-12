/* eslint-disable vue/one-component-per-file */
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

import './alarm-skeleton.scss';

const widths = [76, 58, 88, 66, 80, 52, 72, 62];
const barHeights = [22, 34, 28, 46, 38, 62, 48, 32, 54, 76, 60, 42, 68, 86, 72, 56, 40, 64, 50, 30, 44, 58, 36, 24];
const block = (width: number | string, className = '') => (
  <span
    style={{ width: typeof width === 'number' ? `${width}px` : width }}
    class={['alarm-skeleton-block', className]}
  />
);

export const AlarmTrendSkeleton = defineComponent({
  name: 'AlarmTrendSkeleton',
  props: {
    compact: Boolean,
    seriesCount: { type: Number, default: 1 },
  },
  render() {
    return (
      <div
        class={['alarm-trend-skeleton', { 'is-compact': this.compact }]}
        aria-hidden='true'
      >
        {!this.compact && (
          <div class='axis-labels'>
            {[0, 1, 2].map(i => (
              <span key={i}>{block(20)}</span>
            ))}
          </div>
        )}
        <div class='plot'>
          <div class='bars'>
            {barHeights.map((height, index) => (
              <span
                key={index}
                style={{ height: `${height}%` }}
                class='alarm-skeleton-block'
              />
            ))}
          </div>
          {!this.compact && (
            <div class='time-labels'>
              {[0, 1, 2, 3, 4].map(i => (
                <span key={i}>{block(40)}</span>
              ))}
            </div>
          )}
        </div>
        {!this.compact && (
          <div class='legend'>
            {Array.from({ length: this.seriesCount }, (_, i) => (
              <span key={i}>
                {block(8, 'dot')}
                {block(40)}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  },
});

export const AlarmTableSkeletonCell = defineComponent({
  name: 'AlarmTableSkeletonCell',
  props: {
    columnKey: { type: String, default: '' },
    rowIndex: { type: Number, default: 0 },
    variant: { type: String as PropType<'default' | 'incident' | 'issues'>, default: 'default' },
  },
  render() {
    const key = this.columnKey;
    const width = widths[this.rowIndex % widths.length];
    let content;
    if (key === 'row-select') {
      content = block(14, 'checkbox');
    } else if (key === 'trend') {
      content = <AlarmTrendSkeleton compact />;
    } else if (
      (this.variant === 'issues' && key === 'name') ||
      (this.variant === 'incident' && ['incident_name', 'incident_reason'].includes(key))
    ) {
      content = (
        <div class='text-lines'>
          {block(`${width}%`)}
          {block(`${Math.max(35, width - 22)}%`, 'secondary')}
        </div>
      );
    } else if (key.includes('time') && (this.variant === 'issues' || this.variant === 'incident')) {
      content = (
        <div class='text-lines'>
          {block(72)}
          {block(128, 'secondary')}
        </div>
      );
    } else if (key.includes('time')) {
      content = block(124, 'date');
    } else if (['alert_name', 'action_name', 'id'].includes(key)) {
      content = (
        <>
          {block(3, 'severity')}
          {block(`${width}%`)}
        </>
      );
    } else if (['status', 'stage_display', 'priority'].includes(key)) {
      content = (
        <>
          {block(8, 'dot')}
          {block(key === 'priority' ? 24 : 48)}
        </>
      );
    } else if (['labels', 'tags'].includes(key)) {
      content = (
        <>
          {block(48, 'tag')}
          {block(36, 'tag')}
        </>
      );
    } else if (['assignee', 'assignees', 'appointee', 'operator', 'follower'].includes(key)) {
      content = (
        <>
          {block(20, 'avatar')}
          {block(48)}
        </>
      );
    } else if (key.includes('count') || key === 'duration') {
      content = block(32);
    } else if (key === 'operation') {
      content = (
        <>
          {block(36)}
          {block(28)}
        </>
      );
    } else {
      content = block(`${width}%`);
    }
    return (
      <div
        class={['alarm-skeleton-cell', `alarm-skeleton-cell--${this.variant}`]}
        aria-hidden='true'
      >
        {content}
      </div>
    );
  },
});

export const AlarmFilterSkeleton = defineComponent({
  name: 'AlarmFilterSkeleton',
  render() {
    return (
      <div
        class='alarm-filter-skeleton'
        aria-hidden='true'
      >
        {[3, 4, 5, 3, 4].map((count, group) => (
          <div
            key={group}
            class='filter-group'
          >
            <div class='group-heading'>
              {block(48 + group * 8, 'group-title')}
              <span class='group-chevron' />
            </div>
            {Array.from({ length: count }, (_, row) => (
              <div
                key={row}
                class='filter-row'
              >
                {block(14, 'checkbox')}
                {block(4, 'filter-marker')}
                <span class='filter-label'>{block(`${widths[(row + group) % widths.length]}%`)}</span>
                {block(14 + (row % 3) * 4, 'count')}
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  },
});

export const AlarmAnalysisSkeleton = defineComponent({
  name: 'AlarmAnalysisSkeleton',
  props: { count: { type: Number, default: 3 } },
  render() {
    return (
      <div
        class='collapse-content alarm-analysis-skeleton'
        aria-hidden='true'
      >
        {Array.from({ length: this.count }, (_, card) => (
          <div
            key={card}
            class='panel-item'
          >
            <div class='panel-item-header'>
              <div class='header-left'>
                {block(72)}
                {block(24, 'tag')}
              </div>
            </div>
            {[0, 1, 2, 3, 4].map(row => (
              <div
                key={row}
                class='analysis-row'
              >
                <div class='analysis-label'>
                  {block(`${widths[(row + card) % widths.length] / 2}%`)}
                  {block(48, 'count')}
                </div>
                <div class='analysis-track'>{block(`${88 - row * 14}%`)}</div>
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  },
});
