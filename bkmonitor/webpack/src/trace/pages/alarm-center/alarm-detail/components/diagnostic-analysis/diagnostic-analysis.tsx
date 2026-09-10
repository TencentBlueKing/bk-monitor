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
import { defineComponent, nextTick, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import AiDiagnosticInfoCard from './ai-diagnostic-info-card';
import AnalysisPanel from './analysis-panel';
import AiChatInput from './chat/ai-chat-input';
import { useAiChat } from './chat/use-ai-chat';
import { DiagnosticTypeEnum } from './constant';
import { useAiCapability } from './use-ai-capability';

import './diagnostic-analysis.scss';

/** 滚动超过这个距离才认为离开了顶部结论区 */
const CONCLUSION_SCROLL_THRESHOLD = 24;

export default defineComponent({
  name: 'DiagnosticAnalysis',
  emits: ['close'],
  setup(_, { emit }) {
    const { t } = useI18n();
    const { bkFaraProcesses, displayIncident, hasIncident } = useAiCapability();
    const { messages, pending, sendQuestion } = useAiChat();
    /** 会话滚动容器 */
    const conversationRef = shallowRef<HTMLDivElement>();
    /** 会话滚动离开结论区后，露出回到结论区的入口 */
    const showBackToConclusion = shallowRef(false);

    const handleConversationScroll = () => {
      showBackToConclusion.value = (conversationRef.value?.scrollTop ?? 0) > CONCLUSION_SCROLL_THRESHOLD;
    };

    const handleBackToConclusion = () => {
      conversationRef.value?.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const handleClosed = () => {
      emit('close');
    };

    const handleSendQuestion = (question: string) => {
      sendQuestion(question);
    };

    // 本面板底部已有 AI 会话入口，展开期间收起宿主右下角的小鲸浮标，避免两个入口重叠
    onMounted(() => {
      window.__BK_WEWEB_DATA__?.setAiWhaleHidden?.(true);
      conversationRef.value?.addEventListener('scroll', handleConversationScroll, { passive: true });
    });

    onBeforeUnmount(() => {
      window.__BK_WEWEB_DATA__?.setAiWhaleHidden?.(false);
      conversationRef.value?.removeEventListener('scroll', handleConversationScroll);
    });

    // 追问消息入列、以及回复内容填充后都要滚到底
    watch(
      () => messages.value,
      async () => {
        await nextTick();
        const el = conversationRef.value;
        if (el) {
          el.scrollTop = el.scrollHeight;
        }
      }
    );

    return {
      t,
      DiagnosticTypeEnum,
      bkFaraProcesses,
      displayIncident,
      hasIncident,
      messages,
      pending,
      conversationRef,
      showBackToConclusion,
      handleBackToConclusion,
      handleClosed,
      handleSendQuestion,
    };
  },
  render() {
    const commonPanels = [
      this.DiagnosticTypeEnum.DIMENSION,
      this.DiagnosticTypeEnum.LINK,
      this.DiagnosticTypeEnum.LOG,
      this.DiagnosticTypeEnum.EVENT,
    ];

    return (
      <div class='diagnostic-analysis-panel-comp'>
        <div class='diagnostic-analysis-wrapper'>
          <div class='diagnostic-analysis-wrapper-header'>
            <div class='title'>{this.t('AI诊断')}</div>
            {this.showBackToConclusion ? (
              <span
                class='back-to-conclusion'
                onClick={this.handleBackToConclusion}
              >
                <i class='icon-monitor icon-arrow-up' />
                {this.t('查看诊断结论')}
              </span>
            ) : undefined}
            <div class='tool-btns'>
              <i
                class='icon-monitor icon-mc-close-copy close-icon'
                v-bk-tooltips={{
                  content: this.t('关闭'),
                }}
                onClick={this.handleClosed}
              />
            </div>
          </div>
          <div
            ref='conversationRef'
            class='diagnostic-analysis-conversation'
          >
            <div class='chat-message is-ai'>
              <div class='chat-message-body'>
                <div class='chat-message-text'>
                  {this.hasIncident
                    ? this.t('这条告警已纳入故障，以下结论结合了故障上下文：')
                    : this.t('这条告警未纳入故障，以下结论只基于告警自身的观测数据：')}
                </div>
                <AiDiagnosticInfoCard
                  bkFaraProcesses={this.bkFaraProcesses}
                  incident={this.displayIncident}
                />
              </div>
            </div>

            <div class='chat-message is-ai'>
              <div class='chat-message-body'>
                <div class='chat-message-text'>{this.t('我还找到这些关联线索，展开可以看明细：')}</div>
                {commonPanels.map(type => (
                  <AnalysisPanel
                    key={type}
                    type={type}
                  />
                ))}
              </div>
            </div>

            {this.messages.map(message =>
              message.role === 'user' ? (
                <div
                  key={message.id}
                  class='chat-message is-user'
                >
                  <div class='chat-message-bubble'>{message.content}</div>
                </div>
              ) : (
                <div
                  key={message.id}
                  class='chat-message is-ai'
                >
                  <div class='chat-message-body'>
                    {message.loading ? (
                      <div class='chat-message-loading'>
                        <span class='dot' />
                        <span class='dot' />
                        <span class='dot' />
                      </div>
                    ) : (
                      <div class='chat-message-text'>{message.content}</div>
                    )}
                  </div>
                </div>
              )
            )}
          </div>
          <div class='diagnostic-analysis-wrapper-footer'>
            <AiChatInput
              pending={this.pending}
              onSend={this.handleSendQuestion}
            />
          </div>
        </div>
      </div>
    );
  },
});
