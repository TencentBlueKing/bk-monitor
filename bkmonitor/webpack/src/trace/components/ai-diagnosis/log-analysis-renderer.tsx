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
import { type PropType, type VNode, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import DiagnosisCollapseCard from './diagnosis-collapse-card';
import { useDiagnosisCardsState } from './use-diagnosis-cards-state';

import type { DiagnosisInteraction, LogAnalysisViewModel } from './types';

const LOG_PLACEHOLDER = /#(?:NUMBER|TIME)#/;

const highlightPattern = (pattern: string) =>
  pattern.split(/(#(?:NUMBER|TIME)#)/g).map((piece, index) =>
    LOG_PLACEHOLDER.test(piece) ? (
      <span
        key={index}
        class='ai-diagnosis-log__token'
      >
        {piece}
      </span>
    ) : (
      piece
    )
  );

const highlightSample = (pattern: string, sample: string) => {
  const pieces = pattern.split(/(#(?:NUMBER|TIME)#)/g).filter(piece => piece !== '');
  const nodes: Array<string | VNode> = [];
  let cursor = 0;
  let pendingToken = '';
  pieces.forEach((piece, index) => {
    if (LOG_PLACEHOLDER.test(piece)) {
      pendingToken = piece;
      return;
    }
    const found = sample.indexOf(piece, cursor);
    if (found < 0) {
      nodes.push(sample.slice(cursor));
      cursor = sample.length;
      pendingToken = '';
      return;
    }
    if (found > cursor) {
      const gap = sample.slice(cursor, found);
      nodes.push(
        gap === pendingToken ? (
          gap
        ) : (
          <strong
            key={`gap-${index}`}
            class='ai-diagnosis-log__emphasis'
          >
            {gap}
          </strong>
        )
      );
    }
    nodes.push(piece);
    cursor = found + piece.length;
    pendingToken = '';
  });
  if (cursor < sample.length) {
    const rest = sample.slice(cursor);
    nodes.push(
      rest === pendingToken ? (
        rest
      ) : (
        <strong
          key='rest'
          class='ai-diagnosis-log__emphasis'
        >
          {rest}
        </strong>
      )
    );
  }
  return nodes;
};

export default defineComponent({
  name: 'LogAnalysisRenderer',
  props: {
    items: {
      type: Array as PropType<LogAnalysisViewModel[]>,
      default: () => [],
    },
    summary: {
      type: String,
      default: '',
    },
    expandedIds: {
      type: Array as PropType<string[]>,
      default: undefined,
    },
    expandAll: {
      type: Boolean,
      default: undefined,
    },
  },
  emits: {
    interaction: (_interaction: DiagnosisInteraction) => true,
    prompt: (_prompt: string) => true,
    'update:expandedIds': (_expandedIds: string[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const cardsState = useDiagnosisCardsState({
      getCardIds: () => props.items.map(item => item.id),
      getControlledExpandedIds: () => props.expandedIds,
      getDefaultExpandedIds: () => props.items.slice(0, 1).map(item => item.id),
      getExpandAll: () => props.expandAll,
      onUpdate: expandedIds => emit('update:expandedIds', expandedIds),
      onInteraction: interaction => emit('interaction', interaction),
    });
    return {
      t,
      ...cardsState,
      handlePrompt: (prompt: string) => emit('prompt', prompt),
    };
  },
  render() {
    return (
      <div class='ai-diagnosis-domain-renderer ai-diagnosis-log'>
        {this.summary && (
          <div class='ai-diagnosis-domain-summary'>
            <strong>{this.t('日志分析总结：')}</strong>
            <span>{this.summary}</span>
          </div>
        )}
        {this.items.map((item, index) => (
          <DiagnosisCollapseCard
            key={item.id}
            v-slots={{
              action: () => (
                <button
                  class='ai-diagnosis-renderer__action'
                  v-tippy={{ content: this.t('查看详情'), placement: 'top', delay: 200, appendTo: () => document.body }}
                  aria-label={this.t('查看详情')}
                  type='button'
                  onClick={(event: MouseEvent) => {
                    event.stopPropagation();
                    this.handlePrompt(this.t('展开查看聚类结果 {0} 的日志明细', [index + 1]));
                  }}
                >
                  <i
                    class='icon-monitor icon-fenxiang'
                    aria-hidden='true'
                  />
                </button>
              ),
              lead: () => (
                <div class='ai-diagnosis-log__content'>
                  {item.pattern && (
                    <div class='ai-diagnosis-log__pattern'>
                      <strong>{this.t('Pattern:')}</strong>
                      <p>{highlightPattern(item.pattern)}</p>
                    </div>
                  )}
                  {item.sample && (
                    <div class='ai-diagnosis-log__sample'>
                      <strong>{this.t('示例日志:')}</strong>
                      <p>{item.pattern ? highlightSample(item.pattern, item.sample) : item.sample}</p>
                    </div>
                  )}
                </div>
              ),
            }}
            card={{
              id: item.id,
              index: index + 1,
              interaction: item.interaction,
              rows: [],
              title: this.t('聚类结果 {0} (共 {1} 条日志)', [index + 1, item.logCount || 1]),
            }}
            expanded={this.isExpanded(item.id)}
            onInteraction={this.handleInteraction}
            onToggle={expanded => this.handleToggle(item.id, expanded)}
          />
        ))}
      </div>
    );
  },
});
