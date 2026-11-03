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
import { computed, defineComponent, shallowRef } from 'vue';

import { ChatContainer, MessageRender, MessageToolsStatus } from '@blueking/chat-x';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { appendDiagnosisReferenceToDraft, diagnosisChatModuleTitleKey } from './chat-reference';
import AlertAnalysisMessageRenderer from './components/alert-analysis-message-renderer';
import AlertListMessage from './components/alert-list-message';
import DiagnosisReadyContent from './components/diagnosis-ready-content';
import DiagnosticStatus from './components/diagnostic-status';
import EventRecordsMessage from './components/event-records-message';
import LogRecordsMessage from './components/log-records-message';
import MetricSeriesMessage from './components/metric-series-message';
import { transformDiagnosisPanelView, transformDiagnosisSummaryView } from './diagnosis-view-adapter';
import { useDiagnosticAnalysis } from './hooks/use-diagnostic-analysis';
import { useDiagnosticSession } from './hooks/use-diagnostic-session';
import { getAlertAnalysisMessage } from './message-protocol';
import { createDiagnosisPreviewMessages } from './mock/diagnosis-preview-messages';
import {
  diagnosisMockSnapshot,
  getDiagnosticMockAdapters,
  isDiagnosticMockEnabled,
} from './mocks/diagnostic-analysis-mock';
import { getAlertListResult, getEventRecordsResult, getLogRecordsResult, getMetricSeriesResult } from './typing';
import { DiagnosisPanelShell } from '@/components/ai-diagnosis';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type {
  DiagnosisAddToChatPayload,
  DiagnosisInteraction,
  DiagnosisPromptAction,
  DiagnosisSummaryVariant,
} from '@/components/ai-diagnosis';
import type { Message } from '@blueking/chat-x';

import './diagnostic-analysis.scss';
import '@blueking/chat-x/dist/index.css';

export default defineComponent({
  name: 'DiagnosticAnalysis',
  emits: ['close'],
  setup(_, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const panelRef = shallowRef<HTMLElement>();
    const allExpanded = shallowRef(false);
    const interactionError = shallowRef('');
    const { alarmId, bizId } = storeToRefs(useAlarmCenterDetailStore());
    const mockAdapters = getDiagnosticMockAdapters();
    const analysis = useDiagnosticAnalysis({ alarmId, bizId, service: mockAdapters.dataService });
    const diagnosisVariant = computed<DiagnosisSummaryVariant>(() => {
      const locationQuery = typeof window === 'undefined' ? '' : window.location.search;
      const hashQuery = typeof window === 'undefined' ? '' : window.location.hash.split('?')[1] || '';
      const mockVariant =
        route.query.diagnosisMockVariant ||
        new URLSearchParams(locationQuery).get('diagnosisMockVariant') ||
        new URLSearchParams(hashQuery).get('diagnosisMockVariant');
      return isDiagnosticMockEnabled() && mockVariant === 'unlinked'
        ? 'unlinked'
        : analysis.incident.value
          ? 'linked'
          : 'unlinked';
    });
    const session = useDiagnosticSession({
      alarmId,
      bizId,
      enabled: computed(() => analysis.status.value === 'ready'),
      routeName: computed(() => String(route.name || '')),
      service: mockAdapters.sessionService,
    });
    const chatMessages = computed(() => {
      const sessionMessages = session.panelState.value.messages;
      if (!isDiagnosticMockEnabled()) return sessionMessages;
      return [...createDiagnosisPreviewMessages(), ...sessionMessages];
    });
    const mockDiagnosisView = computed(() => {
      if (!isDiagnosticMockEnabled()) return undefined;
      const panelKeys = ['alerts_analysis', 'trace_analysis', 'logs_analysis', 'events_analysis'] as const;
      const linked = diagnosisVariant.value === 'linked';
      return {
        panelViews: Object.fromEntries(
          panelKeys.map(key => [key, transformDiagnosisPanelView(key, diagnosisMockSnapshot.panels[key])])
        ),
        subPanels: Object.fromEntries(panelKeys.map(key => [key, { enabled: true, loading: false }])),
        summary: transformDiagnosisSummaryView({
          alertReason: diagnosisMockSnapshot.alertReason,
          recommendation: diagnosisMockSnapshot.recommendation,
          relatedFailure: linked ? { label: diagnosisMockSnapshot.incidentName } : undefined,
          treatmentPlans: linked ? diagnosisMockSnapshot.treatmentPlans : [],
          variant: diagnosisVariant.value,
        }),
      };
    });

    const anchors = computed(() => {
      const result = [];
      if (analysis.subPanels.value.alerts_analysis?.enabled) {
        result.push({ id: 'alert-analysis-dimension', label: t('告警异常维度分析') });
      }
      if (analysis.subPanels.value.trace_analysis?.enabled) {
        result.push({ id: 'alert-analysis-trace', label: t('Trace 分析') });
      }
      if (analysis.subPanels.value.logs_analysis?.enabled) {
        result.push({ id: 'alert-analysis-log', label: t('日志分析') });
      }
      if (analysis.subPanels.value.events_analysis?.enabled) {
        result.push({ id: 'alert-analysis-event', label: t('事件分析') });
      }
      return result;
    });

    const handleLocate = (anchor: string) => {
      panelRef.value?.querySelector<HTMLElement>(`#${anchor}`)?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    };
    const handleInteraction = async (interaction: DiagnosisInteraction) => {
      interactionError.value = '';
      if (interaction.type === 'drawer') {
        await analysis.loadPanelDetail(interaction);
        return;
      }
      if (interaction.type === 'link' && /^(https?:\/\/|\/(?!\/)|#)/.test(interaction.target)) {
        window.open(interaction.target, '_blank', 'noopener,noreferrer');
        return;
      }
      if (interaction.type === 'error') interactionError.value = interaction.message;
    };

    return {
      ...analysis,
      allExpanded,
      chatMessages,
      mockDiagnosisView,
      anchors,
      commonTippyOptions: { appendTo: () => panelRef.value },
      diagnosisVariant,
      handleClosed: () => emit('close'),
      handleAddToChat: (payload: DiagnosisAddToChatPayload) => {
        const moduleName = t(diagnosisChatModuleTitleKey(payload.reference?.panel));
        session.handleDraftChange(appendDiagnosisReferenceToDraft(session.panelState.value.draft, payload, moduleName));
      },
      handleInteraction,
      handlePrompt: (action: DiagnosisPromptAction) => session.sendMessage(action.text),
      handleLocate,
      interactionError: computed(() => interactionError.value || analysis.panelDetail.value?.error || ''),
      panelRef,
      handleSessionDraftChange: session.handleDraftChange,
      sendSessionMessage: session.sendMessage,
      sessionMessageStatus: session.messageStatus,
      sessionPanelState: session.panelState,
      stopSessionStreaming: session.stopStreaming,
      t,
    };
  },
  render() {
    const messageText = (message: Message) => (typeof message.content === 'string' ? message.content : '');
    const renderChatMessage = (
      message: Message,
      messageToolsStatus?: (typeof MessageToolsStatus)[keyof typeof MessageToolsStatus],
      onInterruptResume?: (payload: unknown) => void
    ) => {
      const content = messageText(message);
      const metricResult = getMetricSeriesResult(message);
      if (metricResult) {
        return (
          <MessageRender
            v-slots={{
              default: () => (
                <MetricSeriesMessage
                  content={content}
                  result={metricResult}
                />
              ),
            }}
            message={message}
            messageToolsStatus={messageToolsStatus}
            tippyOptions={this.commonTippyOptions}
            onInterruptResume={onInterruptResume}
          />
        );
      }
      const alertListResult = getAlertListResult(message);
      if (alertListResult) {
        return (
          <MessageRender
            v-slots={{
              default: () => (
                <AlertListMessage
                  content={content}
                  result={alertListResult}
                />
              ),
            }}
            message={message}
            messageToolsStatus={messageToolsStatus}
            tippyOptions={this.commonTippyOptions}
            onInterruptResume={onInterruptResume}
          />
        );
      }
      const logResult = getLogRecordsResult(message);
      if (logResult) {
        return (
          <MessageRender
            v-slots={{
              default: () => (
                <LogRecordsMessage
                  content={content}
                  result={logResult}
                />
              ),
            }}
            message={message}
            messageToolsStatus={messageToolsStatus}
            tippyOptions={this.commonTippyOptions}
            onInterruptResume={onInterruptResume}
          />
        );
      }
      const eventResult = getEventRecordsResult(message);
      if (eventResult) {
        return (
          <MessageRender
            v-slots={{
              default: () => (
                <EventRecordsMessage
                  content={content}
                  result={eventResult}
                />
              ),
            }}
            message={message}
            messageToolsStatus={messageToolsStatus}
            tippyOptions={this.commonTippyOptions}
            onInterruptResume={onInterruptResume}
          />
        );
      }
      if (getAlertAnalysisMessage(message)) {
        return (
          <AlertAnalysisMessageRenderer
            expandAll={this.allExpanded}
            message={message}
            onInteraction={this.handleInteraction}
          />
        );
      }
      return (
        <MessageRender
          message={message}
          messageToolsStatus={messageToolsStatus}
          tippyOptions={this.commonTippyOptions}
          onInterruptResume={onInterruptResume}
        />
      );
    };
    const hasColleagueResult = (message: Message) =>
      Boolean(
        getMetricSeriesResult(message) ||
        getAlertListResult(message) ||
        getLogRecordsResult(message) ||
        getEventRecordsResult(message)
      );
    const renderMockDiagnosis = () =>
      this.mockDiagnosisView ? (
        <DiagnosisReadyContent
          expandAll={this.allExpanded}
          panelViews={this.mockDiagnosisView.panelViews}
          subPanels={this.mockDiagnosisView.subPanels}
          summary={this.mockDiagnosisView.summary}
          onAdd-to-chat={this.handleAddToChat}
          onDetail={this.handleInteraction}
          onPrompt={this.handlePrompt}
        />
      ) : null;
    const renderDiagnosisOverview = () =>
      this.diagnosisStatus ? (
        <DiagnosticStatus
          status={this.diagnosisStatus}
          onConfigure={this.handleConfigure}
          onContactAdmin={this.handleContactAdmin}
          onDiagnose={this.startDiagnosis}
          onRetry={this.retryDiagnosis}
        />
      ) : this.status === 'ready' ? (
        <DiagnosisReadyContent
          summary={transformDiagnosisSummaryView({
            alertReason: this.summary,
            recommendation: this.suggestion,
            relatedFailure:
              this.diagnosisVariant === 'linked' && this.incident
                ? {
                    label: this.incident.name,
                  }
                : undefined,
            treatmentPlans: this.diagnosisVariant === 'linked' ? this.incident?.treatmentPlans || [] : [],
            variant: this.diagnosisVariant,
          })}
          expandAll={this.allExpanded}
          panelViews={this.panelViews}
          subPanels={this.subPanels}
          onAdd-to-chat={this.handleAddToChat}
          onDetail={this.handleInteraction}
          onPrompt={this.handlePrompt}
        />
      ) : null;

    return (
      <section
        ref='panelRef'
        class='diagnostic-analysis-panel-comp'
      >
        <DiagnosisPanelShell
          allExpanded={this.allExpanded}
          anchors={this.anchors}
          title={this.t('AI 诊断')}
          onClose={this.handleClosed}
          onLocate={this.handleLocate}
          onUpdate:allExpanded={expanded => {
            this.allExpanded = expanded;
          }}
        >
          <div class='diagnostic-analysis-content'>
            {this.interactionError && (
              <div
                class='diagnostic-analysis-interaction-error'
                role='alert'
              >
                {this.interactionError}
              </div>
            )}
            <ChatContainer
              key={this.contextKey}
              v-slots={{
                default: ({
                  messages,
                  messageToolsStatus,
                  onInterruptResume,
                }: {
                  messages?: Message[];
                  messageToolsStatus?: (typeof MessageToolsStatus)[keyof typeof MessageToolsStatus];
                  onInterruptResume?: (payload: unknown) => void;
                }) => {
                  const visibleMessages = messages ?? [];
                  const showDiagnosis = visibleMessages.some(hasColleagueResult);
                  return (
                    <div class='diagnostic-analysis-scroll-content'>
                      {showDiagnosis ? renderMockDiagnosis() || renderDiagnosisOverview() : renderDiagnosisOverview()}
                      {!!visibleMessages.length && (
                        <div class='diagnostic-analysis-conversation'>
                          {visibleMessages.map(message => (
                            <div
                              id={String(message.messageId || message.id)}
                              key={String(message.messageId || message.id)}
                            >
                              {renderChatMessage(message, messageToolsStatus, onInterruptResume)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                },
                welcome: () => <div class='diagnostic-analysis-scroll-content'>{renderDiagnosisOverview()}</div>,
              }}
              asideCollapsed={true}
              commonTippyOptions={this.commonTippyOptions}
              menuSources={[]}
              messages={this.chatMessages}
              messageStatus={this.sessionMessageStatus}
              messageToolsStatus={MessageToolsStatus.Hidden}
              models={[]}
              modelValue={this.sessionPanelState.draft}
              placeholder={this.t('在页面上划词，可添加至聊天继续追问...')}
              resizeProps={{ disabled: true, initialDivide: 0, min: 0 }}
              shortcuts={[]}
              supportUpload={false}
              onSendMessage={this.sendSessionMessage}
              onStopSending={async () => this.stopSessionStreaming()}
              onStopStreaming={async () => this.stopSessionStreaming()}
              onUpdate:modelValue={this.handleSessionDraftChange}
            />
          </div>
        </DiagnosisPanelShell>
      </section>
    );
  },
});
