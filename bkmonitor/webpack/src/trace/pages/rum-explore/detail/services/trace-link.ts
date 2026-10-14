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

/** 关联 Trace 的检索结果，跳转 Trace 检索页需要其所属的 APM 应用 */
export interface IRumTraceInfo {
  app_name: string;
  trace_id: string;
}

/**
 * @description 按 trace_id 全局检索 Trace 所属的 APM 应用
 * @param traceId 关联的 trace_id
 * @param bizId 业务 ID
 * @returns 未检索到时返回 null
 */
export async function searchTraceInfo(traceId: string, bizId: number | string): Promise<IRumTraceInfo | null> {
  if (!traceId) return null;
  const url = `${location.origin}${window.site_url}rest/v2/overview/search/?query=${encodeURIComponent(traceId)}&bk_biz_id=${encodeURIComponent(String(bizId))}`;
  const res = await fetchEventStream(url);
  return res[0]?.items?.[0] ?? null;
}
