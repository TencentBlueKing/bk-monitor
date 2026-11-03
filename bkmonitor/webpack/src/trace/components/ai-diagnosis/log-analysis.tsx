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

import DiagnosisContentCard from './diagnosis-content-card';
import DiagnosisInteractiveValue from './diagnosis-interactive-value';
import { useDiagnosisExpandedState } from './use-diagnosis-expanded-state';

import type {
  DiagnosisAddToChatPayload,
  DiagnosisContentCardViewModel,
  DiagnosisDetailAction,
  DiagnosisInteractiveContent,
  DiagnosisPromptAction,
} from './view-types';

const WILDCARD_PATTERN = /#([A-Za-z0-9_]+)#/g;

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** pattern 里的 #TOKEN# 加灰底；sample 里被替换掉的实际值只加粗。 */
const renderLogText = (text: string, pattern = '') => {
  if (!pattern) {
    const nodes: Array<{ kind?: 'wildcard'; text: string }> = [];
    let lastIndex = 0;
    for (const match of text.matchAll(WILDCARD_PATTERN)) {
      const index = match.index ?? 0;
      if (index > lastIndex) nodes.push({ text: text.slice(lastIndex, index) });
      nodes.push({ kind: 'wildcard', text: match[0] });
      lastIndex = index + match[0].length;
    }
    if (lastIndex < text.length) nodes.push({ text: text.slice(lastIndex) });
    return nodes.length ? nodes : [{ text }];
  }

  const pieces = pattern.split(WILDCARD_PATTERN);
  let source = '';
  pieces.forEach((piece, index) => {
    source += index % 2 === 1 ? '([\\s\\S]+?)' : escapeRegExp(piece);
  });
  const matched = text.match(new RegExp(`^${source}$`));
  if (!matched) return [{ text }];
  let captureIndex = 1;
  return pieces.flatMap((piece, index) => {
    if (index % 2 === 0) return piece ? [{ text: piece }] : [];
    const value = matched[captureIndex] || '';
    captureIndex += 1;
    const unchanged = value === `#${piece}#`;
    return [{ kind: unchanged ? undefined : ('value' as const), text: value }];
  });
};

import './ai-diagnosis.scss';

export default defineComponent({
  name: 'LogAnalysis',
  props: {
    expandAll: {
      type: Boolean,
      default: undefined,
    },
    items: {
      type: Array as PropType<DiagnosisContentCardViewModel[]>,
      default: () => [],
    },
    summary: {
      type: Object as PropType<DiagnosisInteractiveContent>,
    },
  },
  emits: {
    'add-to-chat': (_payload: DiagnosisAddToChatPayload) => true,
    detail: (_action: DiagnosisDetailAction) => true,
    prompt: (_action: DiagnosisPromptAction) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const expandedState = useDiagnosisExpandedState({
      defaultExpandedIds: () => props.items.slice(0, 1).map(item => item.id),
      expandAll: () => props.expandAll,
      ids: () => props.items.map(item => item.id),
    });
    return {
      t,
      ...expandedState,
      handleAddToChat: (payload: DiagnosisAddToChatPayload) => emit('add-to-chat', payload),
      handleDetail: (action: DiagnosisDetailAction) => emit('detail', action),
      handlePrompt: (action: DiagnosisPromptAction) => emit('prompt', action),
    };
  },
  render() {
    return (
      <div class='ai-diagnosis-domain-renderer ai-diagnosis-log'>
        {this.summary && (
          <div class='ai-diagnosis-domain-summary'>
            <strong>{this.t('日志分析总结：')}</strong>
            <DiagnosisInteractiveValue
              v-slots={{ markdown: this.$slots.markdown }}
              content={this.summary}
              onAdd-to-chat={this.handleAddToChat}
              onDetail={this.handleDetail}
            />
          </div>
        )}
        {this.items.map(item => (
          <DiagnosisContentCard
            key={item.id}
            v-slots={{
              blockValue: ({
                block,
                card,
              }: {
                block: DiagnosisInteractiveContent;
                card: DiagnosisContentCardViewModel;
              }) => {
                if (block.key !== 'pattern' && block.key !== 'sample') return null;
                const patternBlock = card.blocks.find(entry => entry.key === 'pattern');
                const pattern = block.key === 'sample' ? String(patternBlock?.value ?? '') : '';
                const tokens = renderLogText(String(block.value ?? ''), pattern);
                return (
                  <DiagnosisInteractiveValue
                    class='ai-diagnosis-content-card__block-value ai-diagnosis-log-text'
                    v-slots={{
                      default: () =>
                        tokens.map((token, index) => (
                          <span
                            key={`${block.key}-${index}`}
                            class={token.kind ? `is-${token.kind}` : undefined}
                          >
                            {token.text}
                          </span>
                        )),
                    }}
                    content={block}
                    onAdd-to-chat={this.handleAddToChat}
                    onDetail={this.handleDetail}
                  />
                );
              },
              action: () =>
                item.promptAction ? (
                  <button
                    class='ai-diagnosis-renderer__action'
                    v-tippy={{
                      content: this.t('查看详情'),
                      placement: 'top',
                      delay: 200,
                      appendTo: () => document.body,
                    }}
                    aria-label={this.t('查看详情')}
                    type='button'
                    onClick={(event: MouseEvent) => {
                      event.stopPropagation();
                      this.handlePrompt(item.promptAction);
                    }}
                  >
                    <i
                      class='icon-monitor icon-mc-duanxin'
                      aria-hidden='true'
                    />
                  </button>
                ) : null,
              json: this.$slots.json,
              markdown: this.$slots.markdown,
            }}
            card={item}
            expanded={this.isExpanded(item.id)}
            onAdd-to-chat={this.handleAddToChat}
            onDetail={this.handleDetail}
            onToggle={expanded => this.setExpanded(item.id, expanded)}
          />
        ))}
      </div>
    );
  },
});
