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

import { type PropType, defineComponent } from 'vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { formatDuration } from '../../../../../components/trace-view/utils/date';
import { formatCompactToken, LLM_KIND_CLASS } from '../utils/transform';
import SpanExpandPanel from './span-expand-panel';

import type { LlmIoPreview, LlmSpanRowView } from '../utils/typings';

import './span-row.scss';

/** 关系列展开按钮的竖线层级：根节点与嵌套 Agent 分支规则不同 */
const resolveTreeToggleLevel = (row: LlmSpanRowView): number | null => {
  if (!row.hasChildren) return null;
  if (row.depth === 0) return row.lineGuideLevel;
  if (row.kind === 'AGENT') return row.lineGuideLevel + 1;
  return row.lineGuideLevel;
};

/** 表格「Span」列类型标签；未归类 kind 时不渲染该徽章 */
const SPAN_KIND_LABEL: Record<string, string> = {
  AGENT: 'Agent',
  LLM: window.i18n.t('模型') as string,
  TOOL: window.i18n.t('工具') as string,
};

/** Agent 执行线表格单行：树形关系线、I/O 预览列、点击展开 SpanExpandPanel */
export default defineComponent({
  name: 'LlmSpanRow',
  props: {
    detailExpanded: {
      type: Boolean,
      default: false,
    },
    expanded: {
      type: Boolean,
      default: false,
    },
    row: {
      type: Object as PropType<LlmSpanRowView>,
      required: true,
    },
  },
  emits: {
    'toggle-detail': (_spanId: string) => true,
    'toggle-expand': (_spanId: string) => true,
    'view-detail': (_spanId: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** overflow-tips 内容过长时截断，避免 Popover 撑满视口 */
    const sliceTooltipContent = (content: string): string => {
      return content.length > 200 ? `${content.substring(0, 200)}...` : content;
    };

    /** Tool 行展示 KV 对；LLM/Agent 展示单行文本预览 */
    const renderIoSide = (preview: LlmIoPreview, side: 'input' | 'output') => {
      if (preview.type === 'kv') {
        const pairs = preview[side];
        if (!pairs.length) return <span class='llm-span-io-empty'>—</span>;
        return (
          <div class='llm-span-io-kvs'>
            {pairs.map(item => (
              <span
                key={item.key}
                class='llm-span-io-kv'
              >
                <span
                  class='llm-span-io-kv-key'
                  v-overflow-tips={{ content: sliceTooltipContent(item.key), placement: 'top' }}
                >
                  {item.key}
                </span>
                <span style='margin: 0 2px;'>:</span>
                <span
                  class='llm-span-io-kv-value'
                  v-overflow-tips={{ content: sliceTooltipContent(item.value), placement: 'top' }}
                >
                  {item.value}
                </span>
              </span>
            ))}
          </div>
        );
      }
      const text = preview[side];
      if (!text) return <span class='llm-span-io-empty'>—</span>;
      return (
        <span
          class='llm-span-io-text'
          v-overflow-tips={{ content: sliceTooltipContent(text), placement: 'top' }}
        >
          {text}
        </span>
      );
    };

    return () => {
      const { row } = props;
      // startTime 为微秒，与 trace-block 头部一致
      const time = dayjs(row.startTime / 1000);
      const hasTokens = row.inputTokens > 0 || row.outputTokens > 0;
      const toggleLevel = resolveTreeToggleLevel(row);
      const isNestedAgentBranch = row.depth > 0 && row.kind === 'AGENT' && row.hasChildren;
      const treeStyle = {
        '--tree-line-level': String(row.lineGuideLevel),
        ...(toggleLevel !== null ? { '--tree-toggle-level': String(toggleLevel) } : {}),
      } as Record<string, string>;

      return (
        <div class={['llm-span-item', { 'is-open': props.detailExpanded }]}>
          <div
            class={['llm-span-row', { 'is-error': row.isError }]}
            onClick={() => emit('toggle-detail', row.spanId)}
          >
            <div class='llm-span-col is-time'>
              <span>{time.format('HH:mm:ss')}</span>
              <span class='llm-span-date'>{time.format('MM/DD')}</span>
            </div>
            <div
              class={[
                'llm-span-col',
                'is-tree',
                {
                  'is-nested': row.depth > 0,
                  'is-nested-agent-branch': isNestedAgentBranch,
                },
              ]}
              style={treeStyle}
            >
              <span
                class={[
                  'llm-span-tree-line',
                  {
                    'is-last': row.isLast,
                    'is-root-leaf': row.depth === 0 && !row.hasChildren,
                  },
                ]}
              />
              {row.depth > 0 ? (
                <span
                  class={['llm-span-tree-branch', { 'is-to-toggle': isNestedAgentBranch }]}
                />
              ) : null}
              {toggleLevel !== null ? (
                <span
                  class={['llm-span-tree-toggle', { 'is-collapsed': !props.expanded }]}
                  onClick={e => {
                    e.stopPropagation();
                    emit('toggle-expand', row.spanId);
                  }}
                />
              ) : null}
            </div>
            <div class='llm-span-col is-span'>
              {row.kind ? (
                <span class={['llm-span-kind', LLM_KIND_CLASS[row.kind]]}>
                  <i class={['llm-span-kind-icon', `icon-monitor icon-${LLM_KIND_CLASS[row.kind]}`]} />
                  <span>{SPAN_KIND_LABEL[row.kind]}</span>
                </span>
              ) : null}
              <span class='llm-span-title'>
                {row.isError ? (
                  <i
                    class='icon-monitor icon-yichang llm-span-error-icon'
                    // v-bk-tooltips={{ content: row.errorMessage || '--', placement: 'top' }}
                  />
                ) : null}
                <span
                  class='llm-span-name'
                  v-overflow-tips={{ content: row.name, placement: 'top' }}
                >
                  {row.name}
                </span>
              </span>
              {row.subtitle ? <span class='llm-span-subtitle'>{row.subtitle}</span> : null}
              {row.kind === 'AGENT' && row.childCount > 0 ? <span class='llm-span-count'>{row.childCount}</span> : null}
            </div>
            <div class='llm-span-col is-io'>
              {renderIoSide(row.io, 'input')}
              <i class='icon-monitor icon-next-one llm-span-io-arrow' />
              {renderIoSide(row.io, 'output')}
            </div>
            <div class='llm-span-col is-duration'>
              <span class='llm-span-duration'>
                <i class='icon-monitor icon-jishiqi' />
                {formatDuration(row.elapsedTime)}
              </span>
            </div>
            <div class='llm-span-col is-token'>
              {hasTokens ? (
                <span class='llm-span-tokens'>
                  <i class='icon-monitor icon-mc-ai-input' />
                  <span>{formatCompactToken(row.inputTokens)}</span>
                  <span class='llm-span-tokens-divider' />
                  <i class='icon-monitor icon-mc-ai-output is-output' />
                  <span class='is-output'>{formatCompactToken(row.outputTokens)}</span>
                </span>
              ) : null}
            </div>
            <div class='llm-span-col is-action'>
              <span
                class='llm-span-detail-btn'
                v-bk-tooltips={{ content: t('查看详情'), placement: 'top' }}
                onClick={e => {
                  e.stopPropagation();
                  emit('view-detail', row.spanId);
                }}
              >
                <i class='icon-monitor icon-arrow-right' />
              </span>
            </div>
          </div>
          {props.detailExpanded ? (
            <SpanExpandPanel
              row={row}
              onView-detail={spanId => emit('view-detail', spanId)}
            />
          ) : null}
        </div>
      );
    };
  },
});
