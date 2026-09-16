/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { shallowRef } from 'vue';

import { askAlarmDetailAiMock } from '@/mock/alarm-detail-ai';

import type { IChatResult } from './chat-result-typing';

export type ChatRole = 'ai' | 'user';

export interface IChatMessage {
  content: string;
  id: string;
  loading?: boolean;
  /** 分析板块回显时携带的结构化结果，纯文字回答没有这个字段 */
  result?: IChatResult;
  role: ChatRole;
}

const FALLBACK_REPLY = window.i18n.t('AI 服务暂未就绪，请稍后再试。');

/** 回显结果已经在本地拼好，这里只留一小段思考时间让会话节奏和追问一致 */
const RESULT_THINKING_MS = 400;

/** AI诊断 追问会话 */
export function useAiChat() {
  const messages = shallowRef<IChatMessage[]>([]);
  /** 是否正在等待回复，等待期间不接受新的提问 */
  const pending = shallowRef(false);
  /** 回显消息的自增序号，连点多个入口时保证 id 不撞 */
  let resultSeq = 0;

  const sendQuestion = async (question: string) => {
    const content = question.trim();
    if (!content || pending.value) return;

    const seq = Date.now();
    const replyId = `ai-${seq}`;
    messages.value = [
      ...messages.value,
      { id: `user-${seq}`, role: 'user', content },
      { id: replyId, role: 'ai', content: '', loading: true },
    ];
    pending.value = true;

    // 【临时联调 mock，联调就绪后改为调用真实追问接口】
    const reply = await (askAlarmDetailAiMock(content) ?? Promise.resolve(FALLBACK_REPLY));

    messages.value = messages.value.map(item =>
      item.id === replyId ? { ...item, content: reply, loading: false } : item
    );
    pending.value = false;
  };

  /**
   * 分析板块里的入口点击后调这个：先落一条用户提问，再给出带结构化结果的回答。
   * 内容本地就有，不问后端，所以不占用 pending——连点多个入口各自出结果，也不挡住输入框。
   */
  const answerWithResult = async (question: string, answer: { content: string; result?: IChatResult }) => {
    resultSeq += 1;
    const replyId = `ai-result-${resultSeq}`;
    const questionId = `user-result-${resultSeq}`;
    messages.value = [
      ...messages.value,
      { id: questionId, role: 'user', content: question },
      { id: replyId, role: 'ai', content: '', loading: true },
    ];

    await new Promise(resolve => setTimeout(resolve, RESULT_THINKING_MS));

    messages.value = messages.value.map(item =>
      item.id === replyId ? { ...item, content: answer.content, result: answer.result, loading: false } : item
    );
  };

  const clear = () => {
    messages.value = [];
    pending.value = false;
  };

  return {
    answerWithResult,
    clear,
    messages,
    pending,
    sendQuestion,
  };
}
