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
import { computed, onScopeDispose, shallowRef, unref, watch } from 'vue';
import type { MaybeRef } from 'vue';

import { MessageStatus } from '@blueking/chat-x';

import { createDiagnosticPanelState } from '../model';
import { diagnosticSessionService } from '../services/diagnostic-session-service';

import type { DiagnosticContext, DiagnosticPanelState } from '../model';
import type { DiagnosticSessionService } from '../services/diagnostic-session-service';
import type { Message, TagSchema, UserMessage } from '@blueking/chat-x';

export interface UseDiagnosticSessionOptions {
  alarmId: MaybeRef<string>;
  bizId: MaybeRef<number>;
  enabled?: MaybeRef<boolean>;
  routeName?: MaybeRef<string>;
  service?: DiagnosticSessionService;
}

const errorMessage = (error: unknown) => {
  if (error instanceof Error) return error.message;
  return typeof error === 'string' ? error : '';
};

const messageText = (content: UserMessage['content']) => {
  if (typeof content === 'string') return content;
  if (content && typeof content === 'object' && 'text' in content && typeof content.text === 'string') {
    return content.text;
  }
  return '';
};

const createMessageId = () => {
  const bytes = new Uint8Array(12);
  globalThis.crypto?.getRandomValues(bytes);
  return `alert-message-${[...bytes].map(item => item.toString(16).padStart(2, '0')).join('')}`;
};

export function useDiagnosticSession(options: UseDiagnosticSessionOptions) {
  const service = options.service || diagnosticSessionService;
  const enabled = computed(() => (options.enabled === undefined ? true : Boolean(unref(options.enabled))));
  const contextKey = computed(() => `${unref(options.bizId)}:${unref(options.alarmId)}`);
  const panelState = shallowRef<DiagnosticPanelState>(createDiagnosticPanelState());
  const sessionCode = shallowRef('');
  const messageStatus = shallowRef(MessageStatus.Disabled);
  const error = shallowRef('');
  let generation = 0;
  let sessionController: AbortController | undefined;
  let streamController: AbortController | undefined;

  const replaceMessage = (messageId: string, update: (message: Message) => Record<string, unknown>) => {
    panelState.value = {
      ...panelState.value,
      messages: panelState.value.messages.map(message =>
        String(message.messageId) === messageId ? ({ ...message, ...update(message) } as unknown as Message) : message
      ),
    };
  };

  const clear = () => {
    generation += 1;
    sessionController?.abort();
    streamController?.abort();
    sessionController = undefined;
    streamController = undefined;
    sessionCode.value = '';
    error.value = '';
    messageStatus.value = MessageStatus.Disabled;
    panelState.value = createDiagnosticPanelState();
  };

  const load = async () => {
    clear();
    if (!enabled.value) return;
    const context: DiagnosticContext = {
      alarmId: String(unref(options.alarmId) || ''),
      bizId: Number(unref(options.bizId)),
    };
    if (!context.alarmId || !Number.isFinite(context.bizId)) return;
    const currentGeneration = generation;
    const controller = new AbortController();
    sessionController = controller;
    messageStatus.value = MessageStatus.Fetching;
    try {
      const session = await service.loadSession(context, { signal: controller.signal });
      if (currentGeneration !== generation || controller.signal.aborted) return;
      sessionCode.value = session.sessionCode;
      panelState.value = { ...panelState.value, messages: session.messages };
      messageStatus.value = MessageStatus.Complete;
    } catch (loadError) {
      if (currentGeneration !== generation || controller.signal.aborted) return;
      error.value = errorMessage(loadError);
      messageStatus.value = MessageStatus.Error;
    }
  };

  watch([contextKey, enabled], load, { immediate: true });

  const handleDraftChange = (draft: DiagnosticPanelState['draft']) => {
    panelState.value = { ...panelState.value, draft };
  };

  const sendMessage = async (content: UserMessage['content'], docSchema?: TagSchema) => {
    const text = messageText(content).trim();
    if (!text || !sessionCode.value || messageStatus.value === MessageStatus.Streaming) return;
    const currentGeneration = generation;
    const context: DiagnosticContext = {
      alarmId: String(unref(options.alarmId) || ''),
      bizId: Number(unref(options.bizId)),
    };
    const controller = new AbortController();
    streamController?.abort();
    streamController = controller;
    const userMessageId = createMessageId();
    error.value = '';
    messageStatus.value = MessageStatus.Fetching;
    try {
      const userMessage = await service.persistUserMessage({
        content: text,
        context,
        messageId: userMessageId,
        sessionCode: sessionCode.value,
        signal: controller.signal,
      });
      if (currentGeneration !== generation || controller.signal.aborted) return;
      if (docSchema) {
        userMessage.property = { ...userMessage.property, docSchema };
      }
      const assistantMessageId = `${userMessageId}-assistant`;
      const assistantDraft = {
        content: '',
        id: assistantMessageId,
        messageId: assistantMessageId,
        role: 'assistant',
        status: MessageStatus.Streaming,
      };
      const assistantMessage = assistantDraft as Message;
      panelState.value = {
        draft: '',
        messages: [...panelState.value.messages, userMessage, assistantMessage],
      };
      messageStatus.value = MessageStatus.Streaming;
      const result = await service.streamCompletion({
        onDelta: (delta, { cover }) => {
          if (currentGeneration !== generation || controller.signal.aborted) return;
          replaceMessage(assistantMessageId, message => ({
            content: cover ? delta : `${message.content || ''}${delta}`,
          }));
        },
        routeName: options.routeName ? String(unref(options.routeName) || '') : undefined,
        sessionCode: sessionCode.value,
        signal: controller.signal,
      });
      if (currentGeneration !== generation || controller.signal.aborted) return;
      replaceMessage(assistantMessageId, message => ({
        content: result.content || message.content,
        property: result.property as unknown as Message['property'],
        status: MessageStatus.Complete,
      }));
      messageStatus.value = MessageStatus.Complete;
    } catch (sendError) {
      if (currentGeneration !== generation || controller.signal.aborted) return;
      error.value = errorMessage(sendError);
      messageStatus.value = MessageStatus.Error;
      const assistantMessageId = `${userMessageId}-assistant`;
      replaceMessage(assistantMessageId, () => ({ status: MessageStatus.Error }));
    }
  };

  const stopStreaming = () => {
    streamController?.abort();
    streamController = undefined;
    messageStatus.value = MessageStatus.Stop;
    panelState.value = {
      ...panelState.value,
      messages: panelState.value.messages.map(message =>
        message.status === MessageStatus.Streaming ? { ...message, status: MessageStatus.Stop } : message
      ),
    };
  };

  onScopeDispose(clear);

  return {
    error,
    handleDraftChange,
    load,
    messageStatus,
    panelState,
    sendMessage,
    sessionCode,
    stopStreaming,
  };
}
