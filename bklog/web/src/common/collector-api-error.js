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

import Vue from 'vue';

import { messageError } from '@/common/bkmagic';
import { makeMessage } from '@/common/util';
import i18n from '@/language/i18n';

import ApiErrorToast from './api-error-toast.vue';
import parser from './collector-api-error.parser';

const { extractRequestId, isInternalApiDump, parseCollectorApiError } = parser;

export { extractRequestId, isInternalApiDump, parseCollectorApiError };

const COPY_MAP = {
  kafka_tail: {
    title: '无法获取采集预览数据，Kafka 分区信息读取失败。',
    suggestion:
      '你可以继续选择存储集群，预览数据可能暂不可用。请稍后重试，或检查采集配置是否已下发。如问题持续，请联系管理员。',
  },
  storage_cluster: {
    title: '获取存储集群列表失败，暂时无法展示可选集群。',
    suggestion: '请稍后重试，或检查采集配置。如问题持续，请联系管理员。',
  },
  internal_dump: {
    title: '操作失败，系统返回了内部异常。',
    suggestion: '请稍后重试，或检查采集配置。如问题持续，请联系管理员。',
  },
};

function toRawMessage(error) {
  if (typeof error === 'string') {
    return error;
  }
  return error?.message || error?.response?.data?.message || '';
}

export function getCollectorApiErrorCopy(kind, t = i18n.t.bind(i18n)) {
  const copy = COPY_MAP[kind] || COPY_MAP.internal_dump;
  return {
    title: t(copy.title),
    suggestion: t(copy.suggestion),
  };
}

let activeToast = null;

function destroyToast(vm) {
  if (!vm) {
    return;
  }
  vm.$destroy();
  if (vm.$el?.parentNode) {
    vm.$el.parentNode.removeChild(vm.$el);
  }
  if (activeToast === vm) {
    activeToast = null;
  }
}

export function showFriendlyApiError({ kind, requestId, original }) {
  if (original) {
    console.error(original);
  }
  const copy = getCollectorApiErrorCopy(kind);
  if (activeToast) {
    destroyToast(activeToast);
  }
  const Ctor = Vue.extend(ApiErrorToast);
  const vm = new Ctor({
    i18n,
    propsData: {
      title: copy.title,
      suggestion: copy.suggestion,
      requestId: requestId || '',
      original: original || '',
    },
  });
  vm.$on('closed', () => destroyToast(vm));
  vm.$mount();
  document.body.appendChild(vm.$el);
  activeToast = vm;
  return vm;
}

export function showCaughtApiError(error, traceparent, { catchIsShowMessage = true, fallbackKind = null } = {}) {
  const original = toRawMessage(error);
  const parsed = parseCollectorApiError(original, traceparent);
  const kind = parsed.kind || fallbackKind;
  if (kind) {
    if (catchIsShowMessage) {
      showFriendlyApiError({ ...parsed, kind });
    } else if (original) {
      console.error(original);
    }
    return { ...parsed, kind };
  }
  if (catchIsShowMessage && original) {
    messageError(makeMessage(original, traceparent));
    console.error(original);
  } else if (original) {
    console.error(original);
  }
  return parsed;
}

export function showClusterSelectError(error, traceparent) {
  const original = toRawMessage(error);
  const parsed = parseCollectorApiError(original, traceparent);
  return showCaughtApiError(error, traceparent, {
    catchIsShowMessage: true,
    fallbackKind: parsed.kind || 'storage_cluster',
  });
}
