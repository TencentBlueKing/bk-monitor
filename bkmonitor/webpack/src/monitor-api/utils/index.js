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
let vue;
export const axiosError = [
  'ERR_BAD_OPTION_VALUE',
  'ERR_BAD_OPTION',
  'ERR_NOT_SUPPORT',
  'ERR_DEPRECATED',
  'ERR_INVALID_URL',
  'ECONNABORTED',
  'ERR_CANCELED',
  'ETIMEDOUT',
  'ERR_NETWORK',
  'ERR_FR_TOO_MANY_REDIRECTS',
  'ERR_BAD_RESPONSE',
  'ERR_BAD_REQUEST',
];
export const setVue = function (instance) {
  vue = instance;
};

export const bkMessage = message => {
  if (vue?.prototype?.$bkMessage) {
    vue.prototype.$bkMessage(message);
  } else {
    vue.config.globalProperties.$Message(message);
  }
};

export const authorityStore = () => {
  if (vue.prototype?.$authorityStore) {
    return vue.prototype.$authorityStore;
  }
  return vue.config?.globalProperties?.$authorityStore;
};

const formatJson = str => {
  const trimmed = str.trim();
  // 扩展预检查：允许所有 JSON 值类型（对象、数组、字符串、数字、布尔、null）
  const isLikelyJson = /^(\s*)({|\[|"|true|false|null|-?\d|\.\d)/.test(trimmed);
  if (!isLikelyJson) return false;
  try {
    return JSON.parse(str);
  } catch {
    return false;
  }
};

export const makeMessage = (message, traceparent, needTraceId) => {
  const list = traceparent?.split('-');
  let traceId = traceparent;
  if (list?.length) {
    traceId = list[1];
  }
  if (message && needTraceId && traceId && typeof message === 'object') {
    let { detail } = message;
    if (detail && typeof detail === 'string') {
      detail = formatJson(detail) || detail;
    }
    return {
      ...message,
      trace_id: traceId,
      detail,
    };
  }
  return message;
};
