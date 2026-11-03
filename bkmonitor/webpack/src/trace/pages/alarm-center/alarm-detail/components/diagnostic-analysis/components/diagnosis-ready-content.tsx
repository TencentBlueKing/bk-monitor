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

import {
  DiagnosisModuleSection,
  DiagnosisSummary,
  DimensionAnalysis,
  EventAnalysis,
  LogAnalysis,
  TraceAnalysis,
  useDiagnosisExpandedState,
} from '@/components/ai-diagnosis';
import MarkdownViewer from '@/components/markdown-editor/viewer';
import bcsSourceIcon from '@/static/img/ai-diagnosis/source-bcs.svg';
import itsmSourceIcon from '@/static/img/ai-diagnosis/source-itsm.svg';

import type { DiagnosisPanelView } from '../diagnosis-view-adapter';
import type { DiagnosticSubPanelsState } from '../model';
import type { DiagnosticPanelKey } from '../typing';
import type {
  DiagnosisAddToChatPayload,
  DiagnosisAnalysisViewModel,
  DiagnosisContentCardViewModel,
  DiagnosisDetailAction,
  DiagnosisPromptAction,
  DiagnosisSummaryViewModel,
  DimensionDiagnosisViewModel,
  EventDiagnosisAnalysisViewModel,
} from '@/components/ai-diagnosis';

type AnalysisPanelKey = Extract<
  DiagnosticPanelKey,
  'alerts_analysis' | 'events_analysis' | 'logs_analysis' | 'trace_analysis'
>;

const MODULE_KEYS: AnalysisPanelKey[] = ['alerts_analysis', 'trace_analysis', 'logs_analysis', 'events_analysis'];
const MODULE_ANCHORS: Record<AnalysisPanelKey, string> = {
  alerts_analysis: 'alert-analysis-dimension',
  events_analysis: 'alert-analysis-event',
  logs_analysis: 'alert-analysis-log',
  trace_analysis: 'alert-analysis-trace',
};
const resolveEventIcon = (id: string, title: string) => {
  if (/k8s|bcs/i.test(`${id} ${title}`)) return bcsSourceIcon;
  if (/itsm|ticket/i.test(`${id} ${title}`)) return itsmSourceIcon;
  return '';
};

export default defineComponent({
  name: 'DiagnosisReadyContent',
  props: {
    expandAll: {
      type: Boolean,
      default: false,
    },
    panelViews: {
      type: Object as PropType<Partial<Record<DiagnosticPanelKey, DiagnosisPanelView>>>,
      default: () => ({}),
    },
    subPanels: {
      type: Object as PropType<DiagnosticSubPanelsState>,
      default: () => ({}),
    },
    summary: {
      type: Object as PropType<DiagnosisSummaryViewModel>,
      required: true,
    },
  },
  emits: {
    'add-to-chat': (_payload: DiagnosisAddToChatPayload) => true,
    detail: (_action: DiagnosisDetailAction) => true,
    prompt: (_action: DiagnosisPromptAction) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const moduleState = useDiagnosisExpandedState({
      expandAll: () => props.expandAll,
      ids: () => MODULE_KEYS.filter(key => props.subPanels[key]?.enabled),
    });
    return {
      t,
      moduleState,
      handleAddToChat: (payload: DiagnosisAddToChatPayload) => emit('add-to-chat', payload),
      handleDetail: (action: DiagnosisDetailAction) => emit('detail', action),
      handlePrompt: (action: DiagnosisPromptAction) => emit('prompt', action),
    };
  },
  render() {
    const definitions = [
      {
        key: 'alerts_analysis' as const,
        title: this.t('告警异常维度分析'),
        icon: 'icon-monitor icon-dimension',
        count: (this.panelViews.alerts_analysis as DiagnosisAnalysisViewModel<DimensionDiagnosisViewModel> | undefined)
          ?.items.length,
        content: () => {
          const panel = this.panelViews.alerts_analysis as
            | DiagnosisAnalysisViewModel<DimensionDiagnosisViewModel>
            | undefined;
          return panel ? (
            <DimensionAnalysis
              v-slots={{ markdown: ({ value }) => <MarkdownViewer value={String(value || '')} /> }}
              expandAll={this.expandAll}
              items={panel.items}
              summary={panel.summary}
              onAdd-to-chat={this.handleAddToChat}
              onDetail={this.handleDetail}
              onPrompt={this.handlePrompt}
            />
          ) : null;
        },
      },
      {
        key: 'trace_analysis' as const,
        title: this.t('Trace 分析'),
        icon: 'icon-monitor icon-trace',
        count: (this.panelViews.trace_analysis as DiagnosisAnalysisViewModel<DiagnosisContentCardViewModel> | undefined)
          ?.items.length,
        content: () => {
          const panel = this.panelViews.trace_analysis as
            | DiagnosisAnalysisViewModel<DiagnosisContentCardViewModel>
            | undefined;
          return panel ? (
            <TraceAnalysis
              v-slots={{ markdown: ({ value }) => <MarkdownViewer value={String(value || '')} /> }}
              expandAll={this.expandAll}
              items={panel.items}
              summary={panel.summary}
              onAdd-to-chat={this.handleAddToChat}
              onDetail={this.handleDetail}
            />
          ) : null;
        },
      },
      {
        key: 'logs_analysis' as const,
        title: this.t('日志分析'),
        icon: 'icon-monitor icon-log',
        count: (this.panelViews.logs_analysis as DiagnosisAnalysisViewModel<DiagnosisContentCardViewModel> | undefined)
          ?.items.length,
        content: () => {
          const panel = this.panelViews.logs_analysis as
            | DiagnosisAnalysisViewModel<DiagnosisContentCardViewModel>
            | undefined;
          return panel ? (
            <LogAnalysis
              v-slots={{ markdown: ({ value }) => <MarkdownViewer value={String(value || '')} /> }}
              expandAll={this.expandAll}
              items={panel.items}
              summary={panel.summary}
              onAdd-to-chat={this.handleAddToChat}
              onDetail={this.handleDetail}
              onPrompt={this.handlePrompt}
            />
          ) : null;
        },
      },
      {
        key: 'events_analysis' as const,
        title: this.t('事件分析'),
        icon: 'icon-monitor icon-event',
        count: (this.panelViews.events_analysis as EventDiagnosisAnalysisViewModel | undefined)?.groups.length,
        content: () => {
          const panel = this.panelViews.events_analysis as EventDiagnosisAnalysisViewModel | undefined;
          return panel ? (
            <EventAnalysis
              v-slots={{ markdown: ({ value }) => <MarkdownViewer value={String(value || '')} /> }}
              groups={panel.groups.map(group => ({
                ...group,
                iconSrc: resolveEventIcon(group.id, group.title),
              }))}
              expandAll={this.expandAll}
              summary={panel.summary}
              onAdd-to-chat={this.handleAddToChat}
              onDetail={this.handleDetail}
              onPrompt={this.handlePrompt}
            />
          ) : null;
        },
      },
    ];
    const enabledModules = definitions.filter(module => this.subPanels[module.key]?.enabled);
    return (
      <div class='ai-diagnosis-overview'>
        <DiagnosisSummary
          v-slots={{ markdown: ({ value }) => <MarkdownViewer value={String(value || '')} /> }}
          summary={this.summary}
          onAdd-to-chat={this.handleAddToChat}
          onDetail={this.handleDetail}
        />
        {enabledModules.length > 0 && (
          <p class='ai-diagnosis-overview__lead'>{this.t('我还找到这些关联线索，展开可以查看明细：')}</p>
        )}
        <div class='ai-diagnosis-overview__modules'>
          {enabledModules.map(module => {
            const state = this.subPanels[module.key];
            return (
              <DiagnosisModuleSection
                key={module.key}
                class={module.key === 'events_analysis' ? 'is-event-title' : undefined}
                anchor={MODULE_ANCHORS[module.key]}
                count={module.count}
                expanded={this.moduleState.isExpanded(module.key)}
                icon={module.icon}
                title={module.title}
                onUpdate:expanded={expanded => this.moduleState.setExpanded(module.key, expanded)}
              >
                {state?.loading ? (
                  <div class='diagnostic-analysis-module-state'>{this.t('加载中')}</div>
                ) : state?.error ? (
                  <div
                    class='diagnostic-analysis-module-state is-error'
                    role='alert'
                  >
                    {state.error}
                  </div>
                ) : (
                  module.content()
                )}
              </DiagnosisModuleSection>
            );
          })}
        </div>
      </div>
    );
  },
});
