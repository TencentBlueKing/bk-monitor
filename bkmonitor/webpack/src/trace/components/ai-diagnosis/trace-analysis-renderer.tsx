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

import type { DiagnosisInteraction, TraceAnalysisViewModel } from './types';

export default defineComponent({
  name: 'TraceAnalysisRenderer',
  props: {
    items: {
      type: Array as PropType<TraceAnalysisViewModel[]>,
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
    };
  },
  render() {
    return (
      <div class='ai-diagnosis-domain-renderer ai-diagnosis-trace'>
        {this.summary && (
          <div class='ai-diagnosis-domain-summary'>
            <strong>{this.t('Trace 分析总结：')}</strong>
            <span>{this.summary}</span>
          </div>
        )}
        {this.items.map((item, index) => (
          <DiagnosisCollapseCard
            key={item.id}
            v-slots={{
              lead: () => (
                <div class='ai-diagnosis-trace__lead'>
                  {item.pattern && (
                    <div class='ai-diagnosis-trace__pattern'>
                      <strong>{this.t('Pattern:')}</strong>
                      <code>{item.pattern}</code>
                    </div>
                  )}
                  <div class='ai-diagnosis-trace__span-title'>{this.t('示例 Span:')}</div>
                </div>
              ),
            }}
            card={{
              id: item.id,
              index: index + 1,
              interaction: item.interaction,
              title: this.t('分析结果 {0}（共 {1} 条 Span）', [index + 1, item.logCount || 1]),
              rows: [
                { key: 'spanId', label: this.t('Span ID'), value: item.spanId || '', interaction: item.interaction },
                {
                  key: 'traceId',
                  label: this.t('所属 Trace'),
                  value: item.traceId || '',
                  interaction: item.interaction,
                },
                { key: 'appName', label: this.t('所属应用'), value: item.appName || '' },
                { key: 'serviceName', label: this.t('所属服务'), value: item.serviceName || '' },
                { key: 'kind', label: this.t('调用类型'), value: item.kind || '' },
                { key: 'error', label: this.t('异常信息'), value: item.error || '' },
              ].filter(row => row.value),
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
