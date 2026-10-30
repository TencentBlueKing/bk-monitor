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
import { defineComponent, shallowRef } from 'vue';

import { ChatContainer, MessageRender, MessageToolsStatus, type Message } from '@blueking/chat-x';
import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import AlertListMessage from './components/alert-list-message';
import DiagnosticStatus from './components/diagnostic-status';
import EventRecordsMessage from './components/event-records-message';
import LogRecordsMessage from './components/log-records-message';
import MetricSeriesMessage from './components/metric-series-message';
import { useDiagnosticAnalysis } from './hooks/use-diagnostic-analysis';
import { getAlertListResult, getEventRecordsResult, getLogRecordsResult, getMetricSeriesResult } from './typing';

import './diagnostic-analysis.scss';
import '@blueking/chat-x/dist/index.css';
export default defineComponent({
  name: 'DiagnosticAnalysis',
  emits: ['close'],
  setup(_, { emit }) {
    const { t } = useI18n();
    const panelRef = shallowRef<HTMLElement>();
    const controller = useDiagnosticAnalysis();

    /**
     * 将带告警分析结果 envelope 的消息解析为对应的数据卡片插槽。
     * 按结果种类逐一匹配，未命中则返回 undefined 走 chat-x 默认渲染。
     */
    const resolveMessageSlot = (message: Message) => {
      const metricResult = getMetricSeriesResult(message);
      if (metricResult) {
        return {
          default: ({ content }: { content: string }) => (
            <MetricSeriesMessage
              content={content}
              result={metricResult}
            />
          ),
        };
      }
      const alertListResult = getAlertListResult(message);
      if (alertListResult) {
        return {
          default: ({ content }: { content: string }) => (
            <AlertListMessage
              content={content}
              result={alertListResult}
            />
          ),
        };
      }
      const logResult = getLogRecordsResult(message);
      if (logResult) {
        return {
          default: ({ content }: { content: string }) => (
            <LogRecordsMessage
              content={content}
              result={logResult}
            />
          ),
        };
      }
      const eventResult = getEventRecordsResult(message);
      if (eventResult) {
        return {
          default: ({ content }: { content: string }) => (
            <EventRecordsMessage
              content={content}
              result={eventResult}
            />
          ),
        };
      }
      return undefined;
    };

    return {
      t,
      panelRef,
      ...controller,
      commonTippyOptions: { appendTo: () => panelRef.value },
      handleClosed: () => emit('close'),
      resolveMessageSlot,
    };
  },
  render() {
    return (
      <section
        ref='panelRef'
        class='diagnostic-analysis-panel-comp'
        aria-label={this.t('AI 诊断')}
      >
        <div class='diagnostic-analysis-wrapper'>
          <header class='diagnostic-analysis-wrapper-header'>
            <div class='title'>{this.t('AI 诊断')}</div>
            <div class='tool-btns'>
              <Button
                class='diagnostic-tool-btn'
                aria-label={this.t('目录')}
                title={this.t('目录')}
                disabled
                text
              >
                <i
                  class='icon-monitor icon-a-Contentmulu'
                  aria-hidden='true'
                />
              </Button>
              <Button
                class='diagnostic-tool-btn'
                aria-label={this.t('全部展开')}
                title={this.t('全部展开')}
                disabled
                text
              >
                <i
                  class='icon-monitor icon-shouqi3'
                  aria-hidden='true'
                />
              </Button>
              <Button
                class='diagnostic-tool-btn'
                aria-label={this.t('关闭')}
                title={this.t('关闭')}
                text
                onClick={this.handleClosed}
              >
                <i
                  class='icon-monitor icon-mc-close-copy'
                  aria-hidden='true'
                />
              </Button>
            </div>
          </header>
          <div class='diagnostic-analysis-wrapper-content'>
            {!this.panelState.messages.length ? (
              <DiagnosticStatus
                status={this.diagnosisStatus}
                onConfigure={this.handleConfigure}
                onContactAdmin={this.handleContactAdmin}
              />
            ) : (
              <ChatContainer
                key={this.contextKey}
                v-slots={{
                  message: ({ message, messageToolsStatus, onInterruptResume }) => (
                    <MessageRender
                      message={message}
                      messageToolsStatus={messageToolsStatus}
                      tippyOptions={this.commonTippyOptions}
                      onInterruptResume={onInterruptResume}
                      v-slots={this.resolveMessageSlot(message)}
                    />
                  ),
                }}
                asideCollapsed={true}
                commonTippyOptions={this.commonTippyOptions}
                menuSources={[]}
                messages={this.panelState.messages}
                messageStatus={this.messageStatus}
                messageToolsStatus={MessageToolsStatus.Hidden}
                models={[]}
                modelValue={this.panelState.draft}
                placeholder={this.t('请输入你的问题')}
                resizeProps={{ disabled: true, initialDivide: 0, min: 0 }}
                shortcuts={[]}
                supportUpload={false}
                onUpdate:modelValue={this.handleDraftChange}
              />
            )}
          </div>
        </div>
      </section>
    );
  },
});
