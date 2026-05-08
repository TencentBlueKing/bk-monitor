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
import type { Attributes } from '@opentelemetry/api';

// 复用旧 session 插件的 storageKey，避免升级后丢失现网累计的设备标识
const DEFAULT_DEVICE_STORAGE_KEY = 'bk_ot_session_id';

const createId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `device-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const readDeviceId = (storageKey: string) => {
  try {
    const existed = window.localStorage.getItem(storageKey);
    if (existed) {
      return existed;
    }
    const deviceId = createId();
    window.localStorage.setItem(storageKey, deviceId);
    return deviceId;
  } catch {
    return createId();
  }
};

const getViewportAttributes = (): Attributes => {
  if (typeof window === 'undefined') {
    return {};
  }
  const connection = (
    navigator as Navigator & {
      connection?: { effectiveType?: string; type?: string };
    }
  ).connection;

  return {
    'browser.viewport.width': window.innerWidth,
    'browser.viewport.height': window.innerHeight,
    'browser.screen.width': window.screen?.width,
    'browser.screen.height': window.screen?.height,
    'network.effective_type': connection?.effectiveType ?? connection?.type,
  };
};

/**
 * 设备级永久标识 + 视口 / 网络元数据。
 * 与 session 插件区分：device 跨会话持久，session 有过期与续期。
 */
export const createDevicePlugin = (option: BkOTRumConfig['device']): BkOTPlugin => ({
  name: 'device',
  enabled: Boolean(option),
  init(context) {
    const storageKey =
      typeof option === 'object' ? (option.storageKey ?? DEFAULT_DEVICE_STORAGE_KEY) : DEFAULT_DEVICE_STORAGE_KEY;
    const deviceId = typeof window === 'undefined' ? createId() : readDeviceId(storageKey);

    context.setRuntimeAttributes({
      'device.id': deviceId,
      ...getViewportAttributes(),
    });
  },
});
