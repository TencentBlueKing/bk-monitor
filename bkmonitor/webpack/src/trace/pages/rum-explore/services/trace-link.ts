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
import { fetchEventStream } from '@/utils';

import type { IRumSearchEvent, IRumTraceInfo } from '../typings';

/** 单次批量检索的 trace_id 数量上限，避免 query 过长 */
export const TRACE_SEARCH_BATCH_SIZE = 20;

/**
 * @description 按 trace_id 全局检索 Trace 所属的 APM 应用，单条与批量共用同一实现
 * @param {string[]} traceIds 关联的 Trace ID 列表，内部去重后按批检索
 * @param {number | string} bizId 发起检索的业务 ID
 * @param {(infos: IRumTraceInfo[]) => void} [onData] 每帧的新增命中项，供调用方逐步渲染
 * @param {AbortSignal} [signal] 上下文切换时中断在途请求的信号
 * @returns {Promise<Map<string, IRumTraceInfo>>} Trace ID 到命中结果的映射
 */
export async function searchTraceInfoMap(
  traceIds: string[],
  bizId: number | string,
  onData?: (infos: IRumTraceInfo[]) => void,
  signal?: AbortSignal
): Promise<Map<string, IRumTraceInfo>> {
  const ids = [...new Set(traceIds.filter(Boolean))];
  const idSet = new Set(ids);
  const result = new Map<string, IRumTraceInfo>();
  const batches: string[][] = [];
  for (let index = 0; index < ids.length; index += TRACE_SEARCH_BATCH_SIZE) {
    batches.push(ids.slice(index, index + TRACE_SEARCH_BATCH_SIZE));
  }
  await Promise.all(
    batches.map(async batch => {
      await fetchEventStream<IRumSearchEvent>(
        buildSearchUrl(batch.join(','), bizId),
        event => {
          if (event?.type !== 'trace') return;
          const hits: IRumTraceInfo[] = [];
          for (const item of event.items ?? []) {
            // 累计快照里同一 trace_id 只保留最早命中的应用
            if (item?.trace_id && idSet.has(item.trace_id) && !result.has(item.trace_id)) {
              result.set(item.trace_id, item);
              hits.push(item);
            }
          }
          if (hits.length) onData?.(hits);
        },
        signal
      );
    })
  );
  return result;
}

/**
 * @description 构造全局 Trace ID 检索的流式接口地址。
 * @param {string} query 以英文逗号连接的 Trace ID
 * @param {number | string} bizId 发起检索的业务 ID
 * @returns {string} 含查询条件和业务参数的完整接口地址
 */
function buildSearchUrl(query: string, bizId: number | string) {
  return `${location.origin}${window.site_url}rest/v2/overview/search/?query=${encodeURIComponent(query)}&bk_biz_id=${encodeURIComponent(String(bizId))}`;
}
