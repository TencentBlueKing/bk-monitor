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

/** 关联 Trace 的检索结果，打开 Trace 详情需要其所属的 APM 应用与业务 */
export interface IRumTraceInfo {
  app_name: string;
  /** Trace 所属业务，跨业务检索时与当前 RUM 记录的业务不同 */
  bk_biz_id?: number | string;
  trace_id: string;
}

/** 全局检索接口的 data 帧，只关心包含 Trace 命中项的事件 */
interface IRumSearchEvent {
  items?: IRumTraceInfo[];
  type?: string;
}

/** 单次批量检索的 trace_id 数量上限，避免 query 过长 */
export const TRACE_SEARCH_BATCH_SIZE = 20;

/**
 * @description 按 trace_id 全局检索 Trace 所属的 APM 应用，单条与批量共用同一实现
 * @param traceIds 关联的 trace_id 列表，内部去重后按批检索
 * @param bizId 业务 ID
 * @param onData 每解析完一帧就回调该帧的命中项，调用方可边收边渲染
 * @param signal 中断信号，调用方切换上下文时终止在途请求
 * @returns trace_id 到检索结果的映射，只包含实际检索到 Trace 的项
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

/** 全局检索接口地址，多个 trace_id 用英文逗号拼接 */
function buildSearchUrl(query: string, bizId: number | string) {
  return `${location.origin}${window.site_url}rest/v2/overview/search/?query=${encodeURIComponent(query)}&bk_biz_id=${encodeURIComponent(String(bizId))}`;
}
