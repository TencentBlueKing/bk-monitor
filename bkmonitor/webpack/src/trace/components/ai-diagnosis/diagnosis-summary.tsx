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

import DiagnosisInteractiveValue from './diagnosis-interactive-value';
import failureIcon from '@/static/img/ai-diagnosis/failure.svg';
import failedStatusIcon from '@/static/img/ai-diagnosis/status-failed.svg';
import successStatusIcon from '@/static/img/ai-diagnosis/status-success.svg';

import type {
  DiagnosisAddToChatPayload,
  DiagnosisDetailAction,
  DiagnosisInteractiveContent,
  DiagnosisSummaryViewModel,
} from './view-types';

import './ai-diagnosis.scss';

export default defineComponent({
  name: 'DiagnosisSummary',
  props: {
    summary: {
      type: Object as PropType<DiagnosisSummaryViewModel>,
      required: true,
    },
  },
  emits: {
    'add-to-chat': (_payload: DiagnosisAddToChatPayload) => true,
    detail: (_action: DiagnosisDetailAction) => true,
  },
  setup(_, { emit }) {
    const { t } = useI18n();
    return {
      t,
      handleAddToChat: (payload: DiagnosisAddToChatPayload) => emit('add-to-chat', payload),
      handleDetail: (action: DiagnosisDetailAction) => emit('detail', action),
    };
  },
  render() {
    const rows: Array<{ content?: DiagnosisInteractiveContent; key: string; label: string }> = [
      { content: this.summary.alertReason, key: 'alertReason', label: this.t('告警原因：') },
      ...(this.summary.variant === 'linked'
        ? [
            {
              content: this.summary.relatedFailure,
              key: 'relatedFailure',
              label: this.t('关联故障：'),
            },
          ]
        : []),
      { content: this.summary.recommendation, key: 'recommendation', label: this.t('处理建议：') },
    ].filter(row => row.content);
    const renderValue = (content: DiagnosisInteractiveContent, className: string) => (
      <DiagnosisInteractiveValue
        class={className}
        v-slots={{
          json: this.$slots.json,
          markdown: this.$slots.markdown,
        }}
        content={content}
        onAdd-to-chat={this.handleAddToChat}
        onDetail={this.handleDetail}
      />
    );
    return (
      <section class={['ai-diagnosis-summary-card', `is-${this.summary.variant}`]}>
        <div class='ai-diagnosis-summary-card__heading'>
          {this.summary.variant === 'linked' ? (
            <span class='ai-diagnosis-summary-card__failure-icon'>
              <img
                alt=''
                src={failureIcon}
              />
            </span>
          ) : (
            <i
              class='icon-monitor icon-alert ai-diagnosis-summary-card__alert-icon'
              aria-hidden='true'
            />
          )}
          <div class='ai-diagnosis-summary-card__heading-copy'>
            {this.summary.variant === 'linked' ? (
              <span class='ai-diagnosis-summary-card__linked-copy'>
                <strong>{this.t('已纳入故障')}</strong>
                <span>{this.t('以下结论，结合了故障上下文：')}</span>
              </span>
            ) : (
              <span>
                {this.t('该告警')} <strong>{this.t('未纳入')}</strong>{' '}
                {this.t('故障，以下结论只基于告警自身的观测数据：')}
              </span>
            )}
          </div>
        </div>
        <div class='ai-diagnosis-summary-card__content'>
          {rows.map(row => (
            <div
              key={row.key}
              class='ai-diagnosis-summary-card__row'
            >
              <span class='ai-diagnosis-summary-card__label'>{row.label}</span>
              {renderValue(
                row.content,
                row.key === 'relatedFailure'
                  ? 'ai-diagnosis-summary-card__value is-link'
                  : 'ai-diagnosis-summary-card__value'
              )}
            </div>
          ))}
          {this.summary.variant === 'linked' && this.summary.treatmentPlans.length > 0 && (
            <div class='ai-diagnosis-summary-card__row ai-diagnosis-summary-card__plans'>
              <span class='ai-diagnosis-summary-card__label'>{this.t('处理套餐：')}</span>
              <div class='ai-diagnosis-summary-card__plan-list'>
                {this.summary.treatmentPlans.map(plan => (
                  <div
                    key={plan.id}
                    class='ai-diagnosis-summary-card__plan'
                  >
                    {renderValue(plan.content, 'ai-diagnosis-summary-card__plan-name')}
                    {plan.time && <span class='ai-diagnosis-summary-card__plan-time'>{plan.time}</span>}
                    <span class='ai-diagnosis-summary-card__plan-status'>
                      <img
                        class='ai-diagnosis-summary-card__status-icon'
                        alt=''
                        src={plan.status === 'success' ? successStatusIcon : failedStatusIcon}
                      />
                      {plan.status === 'success' ? this.t('成功') : this.t('失败')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    );
  },
});
