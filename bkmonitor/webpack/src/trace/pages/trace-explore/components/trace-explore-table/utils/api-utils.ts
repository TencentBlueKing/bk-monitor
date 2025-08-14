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
import { listFlattenSpan, listFlattenTrace } from 'monitor-api/modules/apm_trace';
import { bkMessage, makeMessage } from 'monitor-api/utils';

import { useQueryStringParseErrorState } from '../../../../../components/retrieval-filter/query-string-utils';

export function getTableList(
  params,
  isSpanVisual: boolean,
  requestConfig
): Promise<{ data: any[]; isAborted?: boolean; total: number }> {
  const apiFunc = isSpanVisual ? listFlattenSpan : listFlattenTrace;
  const config = { needMessage: false, ...requestConfig };
  return apiFunc(params, config).catch(err => {
    const isAborted = requestErrorMessage(err);
    return { data: [], total: 0, isAborted };
  });
}

/**
 * @description 请求错误时消息提示处理逻辑（ cancel 类型报错不进行提示）
 * @param err
 *
 */
export function requestErrorMessage(err) {
  const state = useQueryStringParseErrorState();
  state.setErrorData(err);
  const message = makeMessage(err.error_details || err.message);
  let isAborted = false;
  if (message && err?.message !== 'canceled' && err?.message !== 'aborted') {
    bkMessage(message);
  } else {
    isAborted = true;
  }
  return isAborted;
}
