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
import { type PropType, defineComponent, useId } from 'vue';

import { useI18n } from 'vue-i18n';

import type { DiagnosisCollapseCardViewModel, DiagnosisInteraction } from './types';

import './ai-diagnosis.scss';

export default defineComponent({
  name: 'DiagnosisCollapseCard',
  props: {
    card: {
      type: Object as PropType<DiagnosisCollapseCardViewModel>,
      required: true,
    },
    expanded: {
      type: Boolean,
      default: false,
    },
    metricLabel: {
      type: String,
      default: '',
    },
    contentId: {
      type: String,
      default: '',
    },
  },
  emits: {
    'update:expanded': (_expanded: boolean) => true,
    toggle: (_expanded: boolean) => true,
    interaction: (_interaction: DiagnosisInteraction) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const generatedContentId = props.contentId ? '' : `ai-diagnosis-card-${useId().replace(/[^\w-]/g, '-')}`;
    const handleToggle = (expanded: boolean) => {
      emit('update:expanded', expanded);
      emit('toggle', expanded);
    };
    return {
      t,
      resolvedContentId: props.contentId || generatedContentId,
      handleToggle,
      handleInteraction: (interaction?: DiagnosisInteraction) => {
        if (interaction) emit('interaction', interaction);
      },
    };
  },
  render() {
    return (
      <article class={['ai-diagnosis-collapse-card', { 'is-expanded': this.expanded }]}>
        <div
          class='ai-diagnosis-collapse-card__header'
          onClick={() => this.handleToggle(!this.expanded)}
        >
          <button
            class='ai-diagnosis-collapse-card__toggle'
            aria-controls={this.resolvedContentId}
            aria-expanded={this.expanded}
            type='button'
            onKeydown={(event: KeyboardEvent) => {
              if (event.key !== ' ' && event.key !== 'Enter') return;
              event.preventDefault();
              this.handleToggle(!this.expanded);
            }}
          >
            <i
              class='icon-monitor icon-arrow-solid-right ai-diagnosis-collapse-card__arrow'
              aria-hidden='true'
            />
            <span class='ai-diagnosis-collapse-card__title'>
              {this.card.title || this.t('分析项 {0}', [this.card.index || 1])}
            </span>
          </button>
          {this.$slots.action?.({
            card: this.card,
            interact: this.handleInteraction,
          })}
          {this.card.metric && (
            <span class='ai-diagnosis-collapse-card__metric'>
              {this.metricLabel || this.t('异常程度')} <strong>{this.card.metric}</strong>
            </span>
          )}
        </div>
        {this.expanded && (
          <div
            id={this.resolvedContentId}
            class='ai-diagnosis-collapse-card__content'
          >
            {this.$slots.lead?.({
              card: this.card,
              interact: this.handleInteraction,
            })}
            {this.card.rows.map(row => (
              <div
                key={row.key}
                class='ai-diagnosis-collapse-card__row'
              >
                <span class='ai-diagnosis-collapse-card__label'>{row.label}</span>
                {row.interaction ? (
                  <button
                    class='ai-diagnosis-collapse-card__value is-link'
                    type='button'
                    onClick={() => this.handleInteraction(row.interaction)}
                  >
                    {row.value}
                  </button>
                ) : (
                  <span class='ai-diagnosis-collapse-card__value'>{row.value}</span>
                )}
              </div>
            ))}
            {this.$slots.footer && (
              <div class='ai-diagnosis-collapse-card__footer'>
                {this.$slots.footer({
                  card: this.card,
                  interact: this.handleInteraction,
                })}
              </div>
            )}
          </div>
        )}
      </article>
    );
  },
});
