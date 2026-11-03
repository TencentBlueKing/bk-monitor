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

import DiagnosisCollapseCard from './diagnosis-collapse-card';
import { useDiagnosisCardsState } from './use-diagnosis-cards-state';

import type { DiagnosisInteraction, DimensionAnalysisViewModel } from './types';

export default defineComponent({
  name: 'DimensionAnalysisRenderer',
  props: {
    items: {
      type: Array as PropType<DimensionAnalysisViewModel[]>,
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
      <div class='ai-diagnosis-domain-renderer ai-diagnosis-dimension'>
        {this.summary && (
          <div class='ai-diagnosis-domain-summary'>
            <strong>{this.t('异常维度分析总结：')}</strong>
            <span>{this.summary}</span>
          </div>
        )}
        {!this.summary && (
          <p class='ai-diagnosis-domain-intro'>{this.t('故障关联的告警，统计出最异常的维度（组合）：')}</p>
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
                    this.handlePrompt(this.t('异常维度（组合）{0}', [index + 1]));
                  }}
                >
                  <i
                    class='icon-monitor icon-fenxiang'
                    aria-hidden='true'
                  />
                </button>
              ),
              footer: () =>
                item.alertCount !== undefined ? (
                  <div class='ai-diagnosis-dimension__alerts'>
                    <span>
                      {this.t('共 {0} 个告警', [item.alertCount])
                        .split(/(\d+)/)
                        .map((part, partIndex) =>
                          /^\d+$/.test(part) ? <strong key={partIndex}>{part}</strong> : part
                        )}
                    </span>
                  </div>
                ) : null,
            }}
            card={{
              id: item.id,
              index: index + 1,
              interaction: item.interaction,
              metric: item.score === undefined ? undefined : `${Math.round(item.score * 100)}%`,
              rows: Object.entries(item.dimensions || {}).flatMap(([key, value]) =>
                value === undefined || value === '' || (Array.isArray(value) && value.length === 0)
                  ? []
                  : [{ key, label: key, value: Array.isArray(value) ? value.join(', ') : value }]
              ),
              title: item.title || this.t('异常维度（组合）{0}', [index + 1]),
            }}
            expanded={this.isExpanded(item.id)}
            metricLabel={this.t('异常程度')}
            onInteraction={this.handleInteraction}
            onToggle={expanded => this.handleToggle(item.id, expanded)}
          />
        ))}
      </div>
    );
  },
});
