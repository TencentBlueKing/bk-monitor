/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import './llm-skeleton.scss';

/** 与真实布局对齐的占位数量，首块 Trace 模拟「已展开」态 */
const STAT_SKELETON_IDS = ['st-0', 'st-1', 'st-2', 'st-3', 'st-4', 'st-5'];
const TRACE_SKELETON_IDS = [
  'tr-0',
  'tr-1',
  'tr-2',
  'tr-3',
  'tr-4',
  'tr-5',
  'tr-6',
  'tr-7',
  'tr-8',
  'tr-9',
  'tr-10',
  'tr-11',
];
const SPAN_TABLE_SKELETON_ROW_IDS = ['sk-0', 'sk-1', 'sk-2', 'sk-3', 'sk-4', 'sk-5', 'sk-6', 'sk-7'];
const DEFAULT_SPAN_TABLE_ROW_COUNT = 4;

/** 与 Span 表格列对齐的骨架行，供首屏与 flow 懒加载共用 */
export const LlmSpanTableSkeleton = defineComponent({
  name: 'LlmSpanTableSkeleton',
  props: {
    rowCount: {
      type: Number,
      default: DEFAULT_SPAN_TABLE_ROW_COUNT,
    },
    showHead: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { t } = useI18n();

    return () => (
      <div class='llm-span-table-skeleton'>
        {props.showHead ? (
          <div class='llm-span-table-skeleton-head'>
            <span class='is-time'>{t('时间')}</span>
            <span class='is-tree'>{t('关系')}</span>
            <span class='is-span'>Span</span>
            <span class='is-io'>{t('输入 → 输出')}</span>
            <span class='is-duration'>{t('耗时')}</span>
            <span class='is-token'>Token</span>
            <span class='is-action' />
          </div>
        ) : null}
        {SPAN_TABLE_SKELETON_ROW_IDS.slice(0, props.rowCount).map(rowId => (
          <div
            key={rowId}
            class='llm-span-table-skeleton-row'
          >
            <div class='llm-span-table-skeleton-col is-time'>
              <div class='skeleton-element llm-span-table-skeleton-bar is-time-main' />
              <div class='skeleton-element llm-span-table-skeleton-bar is-time-sub' />
            </div>
            <div class='llm-span-table-skeleton-col is-tree'>
              <div class='skeleton-element llm-span-table-skeleton-bar is-tree' />
            </div>
            <div class='llm-span-table-skeleton-col is-span'>
              <div class='skeleton-element llm-span-table-skeleton-bar is-kind' />
              <div class='skeleton-element llm-span-table-skeleton-bar is-name' />
            </div>
            <div class='llm-span-table-skeleton-col is-io'>
              <div class='skeleton-element llm-span-table-skeleton-bar is-io' />
              <div class='skeleton-element llm-span-table-skeleton-bar is-io-arrow' />
              <div class='skeleton-element llm-span-table-skeleton-bar is-io' />
            </div>
            <div class='llm-span-table-skeleton-col is-duration'>
              <div class='skeleton-element llm-span-table-skeleton-bar is-duration' />
            </div>
            <div class='llm-span-table-skeleton-col is-token'>
              <div class='skeleton-element llm-span-table-skeleton-bar is-token' />
            </div>
            <div class='llm-span-table-skeleton-col is-action'>
              <div class='skeleton-element llm-span-table-skeleton-bar is-action' />
            </div>
          </div>
        ))}
      </div>
    );
  },
});

/** LLM 观测首屏骨架：统计卡 + 工具栏 + Trace 列表，首块展开为 Span 表格骨架 */
export default defineComponent({
  name: 'LlmSkeleton',
  setup() {
    return () => (
      <div class='trace-llm-observation-main llm-skeleton'>
        <div class='llm-skeleton-stats'>
          {STAT_SKELETON_IDS.map(statId => (
            <div
              key={statId}
              class='llm-skeleton-stat-item'
            >
              <div class='skeleton-element llm-skeleton-stat-label' />
              <div class='skeleton-element llm-skeleton-stat-value' />
            </div>
          ))}
        </div>
        <div class='trace-llm-observation-timeline'>
          <div class='llm-skeleton-toolbar'>
            <div class='skeleton-element llm-skeleton-toolbar-title' />
            <div class='llm-skeleton-toolbar-row'>
              <div class='llm-skeleton-toolbar-left'>
                <div class='skeleton-element llm-skeleton-session' />
                <div class='skeleton-element llm-skeleton-filters' />
              </div>
              <div class='skeleton-element llm-skeleton-search' />
            </div>
          </div>
          <div class='trace-llm-observation-list'>
            {TRACE_SKELETON_IDS.map((traceId, blockIndex) => (
              <div
                key={traceId}
                class='llm-skeleton-trace-group'
              >
                <div class='skeleton-element llm-skeleton-trace-header' />
                {blockIndex === 0 ? (
                  <LlmSpanTableSkeleton
                    rowCount={DEFAULT_SPAN_TABLE_ROW_COUNT}
                    showHead
                  />
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  },
});
