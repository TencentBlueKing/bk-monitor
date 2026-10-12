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
import { issueLogContent } from 'monitor-api/modules/issue';

import type { RequestOptions } from '../../services/base';
import type { IssueLogContentParams, IssueLogContentResponse } from '../typing';

/** 匹配开头的日期时间（如 2026-07-24 21:08:17.684），展示时去掉以腾出空间 */
const DATETIME_PREFIX_REGEX = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{4})?\s*/;

/** log_content 单次请求的最大条数，与列表增强层保持一致 */
export const ISSUE_LOG_CONTENT_BATCH_SIZE = 10;

export interface IssueLogContentTarget {
  bk_biz_id: number;
  id: string;
}

/**
 * 列表与合并明细共用的异常文案：优先去掉时间前缀的 log_content，否则 anomaly_message，再否则 --
 */
export const getIssueExceptionText = (source: { anomaly_message?: string; log_content?: string }) =>
  source.log_content?.replace(DATETIME_PREFIX_REGEX, '') || source.anomaly_message || '--';

/** 取出 log_content 开头的时间前缀，供日志浮层头部展示 */
export const getIssueLogDatetimePrefix = (logContent?: string) =>
  logContent?.match(DATETIME_PREFIX_REGEX)?.[0]?.trimEnd();

/** 单批请求关联日志；失败返回空对象，由调用方按 anomaly_message 兜底 */
export const requestIssueLogContent = async (
  issues: IssueLogContentTarget[],
  options?: RequestOptions
): Promise<IssueLogContentResponse> => {
  if (!issues.length) return {};
  const params: IssueLogContentParams = {
    bk_biz_ids: [...new Set(issues.map(issue => issue.bk_biz_id))],
    issue_ids: issues.map(issue => issue.id),
  };
  return issueLogContent<IssueLogContentParams, IssueLogContentResponse>(params, options).catch(() => ({}));
};

/**
 * 按批串行拉取关联日志。每批最多 10 条；中止后不再合并尚未应用的批次。
 */
export const fetchIssueLogContentInBatches = async (
  issues: IssueLogContentTarget[],
  options?: RequestOptions & {
    onBatch?: (batch: IssueLogContentTarget[], dataMap: IssueLogContentResponse) => void;
  }
) => {
  const { onBatch, ...requestOptions } = options ?? {};
  for (let index = 0; index < issues.length; index += ISSUE_LOG_CONTENT_BATCH_SIZE) {
    if (requestOptions.signal?.aborted) return;
    const batch = issues.slice(index, index + ISSUE_LOG_CONTENT_BATCH_SIZE);
    const dataMap = await requestIssueLogContent(batch, requestOptions);
    if (requestOptions.signal?.aborted) return;
    onBatch?.(batch, dataMap);
  }
};
