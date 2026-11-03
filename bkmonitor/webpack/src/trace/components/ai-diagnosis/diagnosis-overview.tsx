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

import { useI18n } from 'vue-i18n';

import DiagnosisModuleSection from './diagnosis-module-section';
import DiagnosisSummaryCard from './diagnosis-summary-card';
import DimensionAnalysisRenderer from './dimension-analysis-renderer';
import EventAnalysisRenderer from './event-analysis-renderer';
import LogAnalysisRenderer from './log-analysis-renderer';
import TraceAnalysisRenderer from './trace-analysis-renderer';

import type {
  DiagnosisInteraction,
  DiagnosisRelatedFailure,
  DiagnosisSummaryVariant,
  DiagnosisTreatmentPlan,
  DimensionAnalysisViewModel,
  EventAnalysisGroupViewModel,
  LogAnalysisViewModel,
  TraceAnalysisViewModel,
} from './types';

const MODULE_KEYS = ['dimension', 'trace', 'log', 'event'] as const;
type ModuleKey = (typeof MODULE_KEYS)[number];

export default defineComponent({
  name: 'DiagnosisOverview',
  props: {
    variant: {
      type: String as PropType<DiagnosisSummaryVariant>,
      required: true,
    },
    alertReason: {
      type: String,
      default: '',
    },
    relatedFailure: {
      type: Object as PropType<DiagnosisRelatedFailure>,
    },
    recommendation: {
      type: String,
      default: '',
    },
    treatmentPlans: {
      type: Array as PropType<DiagnosisTreatmentPlan[]>,
      default: () => [],
    },
    dimensions: {
      type: Array as PropType<DimensionAnalysisViewModel[]>,
      default: () => [],
    },
    traces: {
      type: Array as PropType<TraceAnalysisViewModel[]>,
      default: () => [],
    },
    logs: {
      type: Array as PropType<LogAnalysisViewModel[]>,
      default: () => [],
    },
    events: {
      type: Array as PropType<EventAnalysisGroupViewModel[]>,
      default: () => [],
    },
    summaries: {
      type: Object as PropType<Partial<Record<ModuleKey, string>>>,
      default: () => ({}),
    },
    expandAll: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    interaction: (_interaction: DiagnosisInteraction) => true,
    prompt: (_prompt: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const expandedModules = shallowRef<ModuleKey[]>(props.expandAll ? [...MODULE_KEYS] : []);
    watch(
      () => props.expandAll,
      expanded => {
        expandedModules.value = expanded ? [...MODULE_KEYS] : [];
      }
    );
    return {
      t,
      expandedModules,
      handleInteraction: (interaction: DiagnosisInteraction) => emit('interaction', interaction),
      handlePrompt: (prompt: string) => emit('prompt', prompt),
      setModuleExpanded: (key: ModuleKey, expanded: boolean) => {
        expandedModules.value = expanded
          ? [...new Set([...expandedModules.value, key])]
          : expandedModules.value.filter(item => item !== key);
      },
    };
  },
  render() {
    const modules = [
      {
        key: 'dimension' as const,
        title: this.t('告警异常维度分析'),
        icon: 'icon-monitor icon-dimension',
        count: this.dimensions.length,
        content: (
          <DimensionAnalysisRenderer
            items={this.dimensions}
            summary={this.summaries.dimension}
            onInteraction={this.handleInteraction}
            onPrompt={this.handlePrompt}
          />
        ),
      },
      {
        key: 'trace' as const,
        title: this.t('Trace 分析'),
        icon: 'icon-monitor icon-trace',
        count: this.traces.length,
        content: (
          <TraceAnalysisRenderer
            items={this.traces}
            summary={this.summaries.trace}
            onInteraction={this.handleInteraction}
          />
        ),
      },
      {
        key: 'log' as const,
        title: this.t('日志分析'),
        icon: 'icon-monitor icon-log',
        count: this.logs.length,
        content: (
          <LogAnalysisRenderer
            items={this.logs}
            summary={this.summaries.log}
            onInteraction={this.handleInteraction}
            onPrompt={this.handlePrompt}
          />
        ),
      },
      {
        key: 'event' as const,
        title: this.t('事件分析'),
        icon: 'icon-monitor icon-event',
        count: this.events.length,
        content: (
          <EventAnalysisRenderer
            items={this.events}
            summary={this.summaries.event}
            onInteraction={this.handleInteraction}
            onPrompt={this.handlePrompt}
          />
        ),
      },
    ];
    return (
      <div class='ai-diagnosis-overview'>
        <DiagnosisSummaryCard
          alertReason={this.alertReason}
          recommendation={this.recommendation}
          relatedFailure={this.relatedFailure}
          treatmentPlans={this.treatmentPlans}
          variant={this.variant}
          onInteraction={this.handleInteraction}
        />
        <p class='ai-diagnosis-overview__lead'>{this.t('我还找到这些关联线索，展开可以查看明细：')}</p>
        <div class='ai-diagnosis-overview__modules'>
          {modules.map(module => (
            <DiagnosisModuleSection
              key={module.key}
              class={module.key === 'event' ? 'is-event-title' : undefined}
              anchor={`alert-analysis-${module.key}`}
              count={module.count}
              expanded={this.expandedModules.includes(module.key)}
              icon={module.icon}
              title={module.title}
              onUpdate:expanded={expanded => this.setModuleExpanded(module.key, expanded)}
            >
              {module.content}
            </DiagnosisModuleSection>
          ))}
        </div>
      </div>
    );
  },
});
