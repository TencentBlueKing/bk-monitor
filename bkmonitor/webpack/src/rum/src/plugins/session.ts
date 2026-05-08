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

import type { BkOTRumConfig } from '../core/config';
import type { BkOTPlugin } from '../core/plugin';

const DEFAULT_SESSION_STORAGE_KEY = 'bk_ot_session';
const DEFAULT_INACTIVITY_MS = 30 * 60 * 1000;

interface SessionRecord {
  id: string;
  // 会话上次活跃时间戳
  ts: number;
}

const createId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const readRecord = (storageKey: string): null | SessionRecord => {
  try {
    const raw = window.sessionStorage.getItem(storageKey) ?? window.localStorage.getItem(storageKey);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as SessionRecord;
    if (typeof parsed?.id === 'string' && typeof parsed?.ts === 'number') {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
};

const writeRecord = (storageKey: string, record: SessionRecord) => {
  try {
    const serialized = JSON.stringify(record);
    window.sessionStorage.setItem(storageKey, serialized);
    // 同时写到 localStorage，让多 tab / 关闭页后短期内复用同一个 session
    window.localStorage.setItem(storageKey, serialized);
  } catch {
    /* storage 不可用时忽略，运行期仍能继续 */
  }
};

const resolveSessionId = (storageKey: string, inactivityMs: number) => {
  const now = Date.now();
  const existed = readRecord(storageKey);
  if (existed && now - existed.ts < inactivityMs) {
    const record: SessionRecord = { id: existed.id, ts: now };
    writeRecord(storageKey, record);
    return record.id;
  }
  const record: SessionRecord = { id: createId(), ts: now };
  writeRecord(storageKey, record);
  return record.id;
};

/**
 * 会话级标识：带不活跃过期时间，超过 inactivityMs 视为新会话。
 * 与 device 插件互补：device 是设备终身标识，session 反映"用户连续访问"语义。
 */
export const createSessionPlugin = (option: BkOTRumConfig['session']): BkOTPlugin => {
  let teardown: (() => void) | undefined;

  return {
    name: 'session',
    enabled: Boolean(option),
    init(context) {
      const storageKey =
        typeof option === 'object' ? (option.storageKey ?? DEFAULT_SESSION_STORAGE_KEY) : DEFAULT_SESSION_STORAGE_KEY;
      const inactivityMs =
        typeof option === 'object' ? (option.inactivityMs ?? DEFAULT_INACTIVITY_MS) : DEFAULT_INACTIVITY_MS;

      const refresh = () => {
        const sessionId = typeof window === 'undefined' ? createId() : resolveSessionId(storageKey, inactivityMs);
        context.setRuntimeAttributes({ 'session.id': sessionId });
      };

      refresh();

      if (typeof window === 'undefined' || typeof document === 'undefined') {
        return;
      }

      // 用户回到页面时检查是否过期，过期则轮换 sessionId
      const onVisibilityChange = () => {
        if (document.visibilityState === 'visible') {
          refresh();
        }
      };
      document.addEventListener('visibilitychange', onVisibilityChange);
      teardown = () => document.removeEventListener('visibilitychange', onVisibilityChange);
    },
    shutdown() {
      teardown?.();
      teardown = undefined;
    },
  };
};
