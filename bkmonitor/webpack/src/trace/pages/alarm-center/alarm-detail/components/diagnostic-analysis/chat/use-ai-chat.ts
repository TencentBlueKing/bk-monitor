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

export type ChatRole = 'ai' | 'user';

export interface IChatMessage {
  content: string;
  id: string;
  loading?: boolean;
  role: ChatRole;
}

const FALLBACK_REPLY = window.i18n.t('AI 服务暂未就绪，请稍后再试。');

/** AI诊断 追问会话 */
export function useAiChat() {
  const messages = shallowRef<IChatMessage[]>([]);
  /** 是否正在等待回复，等待期间不接受新的提问 */
  const pending = shallowRef(false);

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

  const clear = () => {
    messages.value = [];
    pending.value = false;
  };

  return {
    clear,
    messages,
    pending,
    sendQuestion,
  };
}
