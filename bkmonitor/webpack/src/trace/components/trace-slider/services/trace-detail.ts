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
import { CancelToken } from 'monitor-api/cancel';
import { traceDetail } from 'monitor-api/modules/apm_trace';

export interface FetchTraceSliderDetailParams {
  app_name: string;
  bk_biz_id: number;
  displays?: string[];
  query_trace_relation_app?: boolean;
  trace_id: string;
}

export interface FetchTraceSliderDetailResult {
  data: Record<string, unknown> | null;
  isAborted: boolean;
}

const isRequestAborted = (err: unknown): boolean => {
  const message = (err as Error)?.message;
  return message === 'canceled' || message === 'aborted' || (err as Error)?.name === 'AbortError';
};

/**
 * 拉取 Trace 详情。取消与失败在这里拆开，调用方取消时不要关 loading。
 */
export const fetchTraceSliderDetail = (
  params: FetchTraceSliderDetailParams,
  onCancel: (cancel: () => void) => void
): Promise<FetchTraceSliderDetailResult> => {
  return traceDetail(params, {
    cancelToken: new CancelToken(onCancel),
  })
    .then((data: Record<string, unknown>) => ({ data, isAborted: false }))
    .catch((err: unknown) => ({ data: null, isAborted: isRequestAborted(err) }));
};
