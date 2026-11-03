import * as defaultApi from 'monitor-api/modules/ai-whale';

import type { DiagnosticContext, DiagnosticSession } from '../model';
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
import type { Message } from '@blueking/chat-x';

export interface DiagnosticSessionService {
  loadSession(context: DiagnosticContext, options: { signal: AbortSignal }): Promise<DiagnosticSession>;
  persistUserMessage(params: PersistUserMessageParams): Promise<Message>;
  streamCompletion(params: StreamCompletionParams): Promise<CompletionResult>;
}

type CompletionResult = {
  content: string;
  property?: Record<string, unknown>;
};

type PersistUserMessageParams = {
  content: string;
  context: DiagnosticContext;
  messageId: string;
  sessionCode: string;
  signal: AbortSignal;
};

type ServiceOptions = {
  api?: Partial<SessionApi>;
  completionUrl?: string;
  fetch?: typeof fetch;
};

type SessionApi = {
  createChatSession: (payload: Record<string, unknown>, options?: Record<string, unknown>) => Promise<unknown>;
  createChatSessionContent: (payload: Record<string, unknown>, options?: Record<string, unknown>) => Promise<unknown>;
  getChatSessionContents: (payload: Record<string, unknown>, options?: Record<string, unknown>) => Promise<unknown>;
  retrieveChatSession: (payload: Record<string, unknown>, options?: Record<string, unknown>) => Promise<unknown>;
};

type StreamCompletionParams = {
  onDelta: (content: string, options: { cover: boolean }) => void;
  routeName?: string;
  sessionCode: string;
  signal: AbortSignal;
};

const isRecord = (value: unknown): value is Record<string, any> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const hashContext = (value: string) => {
  let hash = 0xcbf29ce484222325n;
  for (const char of value) {
    hash ^= BigInt(char.codePointAt(0) || 0);
    hash = BigInt.asUintN(64, hash * 0x100000001b3n);
  }
  return hash.toString(16).padStart(16, '0');
};

export const buildDiagnosticSessionCode = (context: DiagnosticContext, userName = '') =>
  `alert-analysis-${context.bizId}-${hashContext(`${userName}:${context.bizId}:${context.alarmId}`)}`.slice(0, 64);

const getStatus = (error: unknown) => {
  if (!isRecord(error)) return undefined;
  return error.status ?? error.statusCode ?? error.response?.status;
};

const isNotFound = (error: unknown) => Number(getStatus(error)) === 404;

const unwrapList = (value: unknown): unknown[] => {
  if (Array.isArray(value)) return value;
  if (!isRecord(value)) return [];
  for (const key of ['items', 'list', 'results', 'data']) {
    if (Array.isArray(value[key])) return value[key];
  }
  return [];
};

const normalizeMessage = (value: unknown, fallbackId: string): Message | null => {
  if (!isRecord(value) || typeof value.content !== 'string' || typeof value.role !== 'string') return null;
  const id = value.id ?? value.message_id ?? value.messageId ?? fallbackId;
  const messageId = value.message_id ?? value.messageId ?? value.property?.extra?.client_message_id ?? id;
  const message = {
    ...value,
    id,
    messageId,
    role: value.role,
    status: value.status || 'complete',
  };
  return message as Message;
};

const getWindow = (): Record<string, any> => (typeof window === 'undefined' ? {} : (window as any));

const readCookie = (name: string) => {
  if (!name || typeof document === 'undefined') return '';
  const encodedName = `${encodeURIComponent(name)}=`;
  return (
    document.cookie
      .split(';')
      .map(item => item.trim())
      .find(item => item.startsWith(encodedName))
      ?.slice(encodedName.length) || ''
  );
};

const buildCompletionUrl = () => {
  const runtime = getWindow();
  const host =
    process.env.NODE_ENV === 'development' ? '' : String(runtime.__BK_WEWEB_DATA__?.host || '').replace(/\/$/, '');
  const base = process.env.NODE_ENV === 'production' ? runtime.site_url || '/' : '/';
  return `${host}${base}`.replace(/\/$/, '') + '/ai_whale/chat/chat_completion/';
};

const createTraceparent = () => {
  const bytes = new Uint8Array(24);
  globalThis.crypto?.getRandomValues(bytes);
  const hex = [...bytes].map(item => item.toString(16).padStart(2, '0')).join('');
  return `00-${hex.slice(0, 32)}-${hex.slice(32)}-01`;
};

const extractContent = (event: Record<string, any>) => {
  if (typeof event.content === 'string') return event.content;
  if (typeof event.data?.content === 'string') return event.data.content;
  if (typeof event.delta === 'string') return event.delta;
  return '';
};

const parseEvent = (source: string) => {
  const data = source
    .split(/\r?\n/)
    .filter(line => line.startsWith('data:'))
    .map(line => line.slice(5).trimStart())
    .join('\n');
  if (!data || data === '[DONE]') return null;
  try {
    const value = JSON.parse(data);
    return isRecord(value) ? value : null;
  } catch {
    return null;
  }
};

const readCompletionResponse = async (
  response: Response,
  onDelta: (content: string, options: { cover: boolean }) => void
): Promise<CompletionResult> => {
  if (!response.ok || !response.body) throw new Error(`AI completion request failed: ${response.status}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let content = '';
  let property: Record<string, unknown> | undefined;

  const consume = (block: string) => {
    const event = parseEvent(block);
    if (!event) return;
    if (event.event === 'error' || event.result === false) {
      throw new Error(event.message || 'AI completion stream failed');
    }
    const nextContent = extractContent(event);
    if (event.event === 'done') {
      content = nextContent || content;
      property = isRecord(event.property) ? event.property : property;
      return;
    }
    if (event.event === 'text' && nextContent) {
      const cover = event.cover === true;
      content = cover ? nextContent : content + nextContent;
      onDelta(nextContent, { cover });
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || '';
    blocks.forEach(consume);
    if (done) break;
  }
  if (buffer.trim()) consume(buffer);
  return { content, property };
};

export const createDiagnosticSessionService = (options: ServiceOptions = {}): DiagnosticSessionService => {
  const apiSource = { ...defaultApi, ...options.api };
  const api = apiSource as SessionApi;
  const fetcher = options.fetch || globalThis.fetch;

  return {
    async loadSession(context, { signal }) {
      const runtime = getWindow();
      const sessionCode = buildDiagnosticSessionCode(context, String(runtime.user_name || runtime.username || ''));
      try {
        await api.retrieveChatSession({ session_code: sessionCode }, { needMessage: false, reject403: true, signal });
      } catch (error) {
        if (!isNotFound(error)) throw error;
        await api.createChatSession(
          {
            is_temporary: false,
            session_code: sessionCode,
            session_name: `Alert ${context.alarmId}`,
          },
          { needMessage: false, signal }
        );
      }
      const history = await api.getChatSessionContents({ session_code: sessionCode }, { needMessage: false, signal });
      return {
        messages: unwrapList(history)
          .map((item, index) => normalizeMessage(item, `${sessionCode}-${index}`))
          .filter(Boolean) as Message[],
        sessionCode,
      };
    },

    async persistUserMessage({ content, context, messageId, sessionCode, signal }) {
      const property = {
        extra: {
          client_message_id: messageId,
          context: [
            {
              __key: 'alert_id',
              __label: 'alert_id',
              __value: context.alarmId,
              alert_id: context.alarmId,
              context_type: 'input',
            },
            {
              __key: 'bk_biz_id',
              __label: 'bk_biz_id',
              __value: String(context.bizId),
              bk_biz_id: String(context.bizId),
              context_type: 'input',
            },
          ],
        },
      };
      const result = await api.createChatSessionContent(
        { content, property, role: 'user', session_code: sessionCode },
        { needMessage: false, signal }
      );
      return {
        content,
        id: isRecord(result) ? result.id || messageId : messageId,
        messageId,
        property,
        role: 'user',
        status: 'complete',
      } as unknown as Message;
    },

    async streamCompletion({ onDelta, routeName, sessionCode, signal }) {
      const runtime = getWindow();
      const token = runtime.__BK_WEWEB_DATA__?.token || runtime.token;
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'Source-App': runtime.source_app || '',
        'X-CSRFToken': runtime.csrf_token || readCookie(runtime.csrf_cookie_name),
        'X-Requested-With': 'XMLHttpRequest',
        traceparent: createTraceparent(),
      };
      if (routeName) headers['Monitor-Route-Name'] = routeName;
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetcher(options.completionUrl || buildCompletionUrl(), {
        body: JSON.stringify({ execute_kwargs: { stream: true }, session_code: sessionCode }),
        credentials: 'include',
        headers,
        method: 'POST',
        signal,
      });
      return readCompletionResponse(response, onDelta);
    },
  };
};

export const diagnosticSessionService = createDiagnosticSessionService();
