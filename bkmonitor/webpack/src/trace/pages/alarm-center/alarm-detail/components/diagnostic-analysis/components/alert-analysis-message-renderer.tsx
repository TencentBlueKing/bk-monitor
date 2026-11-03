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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { MessageRender } from '@blueking/chat-x';
import { useI18n } from 'vue-i18n';

import { getAlertAnalysisMessage } from '../message-protocol';
import {
  DiagnosisModuleSection,
  DiagnosisSummaryCard,
  DimensionAnalysisRenderer,
  EventAnalysisRenderer,
  LogAnalysisRenderer,
  TraceAnalysisRenderer,
} from '@/components/ai-diagnosis';

import type { DiagnosisInteraction } from '@/components/ai-diagnosis';
import type { Message } from '@blueking/chat-x';

export default defineComponent({
  name: 'AlertAnalysisMessageRenderer',
  props: {
    message: {
      type: Object as PropType<Partial<Message>>,
      required: true,
    },
    expandAll: {
      type: Boolean,
      default: true,
    },
  },
  emits: {
    interaction: (_interaction: DiagnosisInteraction) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const moduleExpanded = shallowRef(props.expandAll);
    watch(
      () => props.expandAll,
      expanded => {
        moduleExpanded.value = expanded;
      }
    );
    return {
      t,
      moduleExpanded,
      handleInteraction: (interaction: DiagnosisInteraction) => emit('interaction', interaction),
    };
  },
  render() {
    const protocol = getAlertAnalysisMessage(this.message);
    if (!protocol) return <MessageRender message={this.message} />;
    if (protocol.type === 'summary') {
      return (
        <DiagnosisSummaryCard
          treatmentPlans={
            protocol.payload.treatmentPlan
              ? [
                  {
                    id: 'chat-treatment-plan',
                    name: protocol.payload.treatmentPlan,
                    status: 'success',
                  },
                ]
              : []
          }
          alertReason={protocol.payload.alertReason}
          recommendation={protocol.payload.recommendation}
          relatedFailure={protocol.payload.relatedFailure}
          variant={protocol.payload.variant || 'unlinked'}
          onInteraction={this.handleInteraction}
        />
      );
    }
    const commonProps = {
      items: protocol.payload.items,
      expandAll: this.expandAll,
      onInteraction: this.handleInteraction,
    };
    const renderer =
      protocol.type === 'dimension_analysis' ? (
        <DimensionAnalysisRenderer {...commonProps} />
      ) : protocol.type === 'trace_analysis' ? (
        <TraceAnalysisRenderer {...commonProps} />
      ) : protocol.type === 'log_analysis' ? (
        <LogAnalysisRenderer {...commonProps} />
      ) : (
        <EventAnalysisRenderer {...commonProps} />
      );
    const titles = {
      dimension_analysis: this.t('告警异常维度分析'),
      trace_analysis: this.t('Trace 分析'),
      log_analysis: this.t('日志分析'),
      event_analysis: this.t('事件分析'),
    };
    const icons = {
      dimension_analysis: 'icon-monitor icon-dimension-line',
      trace_analysis: 'icon-monitor icon-mc-menu-trace',
      log_analysis: 'icon-monitor icon-a-logrizhi',
      event_analysis: 'icon-monitor icon-menu-event',
    };
    return (
      <DiagnosisModuleSection
        anchor={`alert-analysis-${protocol.type}`}
        count={protocol.payload.items.length}
        expanded={this.moduleExpanded}
        icon={icons[protocol.type]}
        summary={protocol.payload.summary}
        title={titles[protocol.type]}
        onUpdate:expanded={expanded => {
          this.moduleExpanded = expanded;
        }}
      >
        {renderer}
      </DiagnosisModuleSection>
    );
  },
});
