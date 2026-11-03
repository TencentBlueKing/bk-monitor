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
} from './view-types';

import './ai-diagnosis.scss';

export default defineComponent({
  name: 'TraceAnalysis',
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
    };
  },
  render() {
    return (
      <div class='ai-diagnosis-domain-renderer ai-diagnosis-trace'>
        {this.summary && (
          <div class='ai-diagnosis-domain-summary'>
            <strong>{this.t('Trace 分析总结：')}</strong>
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
