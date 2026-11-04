/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

type MessageCarrier = {
  message?: unknown;
  data?: { message?: unknown };
};

function readMessage(value: unknown): string {
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return '';
}

export function getSaveFailureMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'string' && payload.trim()) {
    return payload.trim();
  }
  if (payload && typeof payload === 'object') {
    const body = payload as MessageCarrier;
    return readMessage(body.message) || readMessage(body.data?.message) || fallback;
  }
  return fallback;
}

export function getFormValidateMessage(error: unknown, fallback: string): string {
  if (typeof error === 'string' && error.trim()) {
    return error.trim();
  }
  if (error && typeof error === 'object') {
    for (const value of Object.values(error as Record<string, unknown>)) {
      if (typeof value === 'string' && value.trim()) {
        return value.trim();
      }
      if (Array.isArray(value) && typeof value[0] === 'string' && value[0].trim()) {
        return value[0].trim();
      }
    }
  }
  return fallback;
}

export function isRequestErrorAlreadyShown(error: unknown): boolean {
  if (error == null) {
    return false;
  }
  if (typeof error === 'string') {
    return true;
  }
  if (typeof error !== 'object') {
    return false;
  }
  const err = error as {
    __CANCEL__?: boolean;
    code?: string;
    name?: string;
    isAxiosError?: boolean;
    config?: unknown;
    response?: unknown;
  };
  if (err.__CANCEL__ || err.code === 'ERR_CANCELED' || err.name === 'CanceledError' || err.name === 'AbortError') {
    return true;
  }
  if (err.response || err.isAxiosError || err.config) {
    return true;
  }
  return false;
}
