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
import { shallowRef, watch } from 'vue';
import type { Ref } from 'vue';

import { getSpanTypeDetailConfig } from '../registry/span-type-registry';
import { getRecordDetail } from '../services';
import { fetchEventStream } from '@/utils';

import type { IRumTimeRange, RumModeType } from '../../typings';
import type { IRumDetailContext, IRumRecordDetail, IRumRelatedData } from '../typings';

interface IUseSpanDetailOptions {
  /** 详情上下文，为 null 表示抽屉未打开 */
  context: Ref<IRumDetailContext | null>;
  mode: Ref<RumModeType>;
  /** 页面所选时间范围，Error 影响面统计沿用该范围 */
  timeRange: Ref<IRumTimeRange>;
}

/**
 * @description 详情数据取数：主详情与按 span 类型声明的关联数据分两条链路并行推进
 *
 * 关联数据依赖主详情的区块内容（如 Error 需要文件行列号），因此在主详情返回后才发起；
 * 两次请求各自维护 loading，关联数据失败不影响主详情展示。
 */
export function useSpanDetail({ context, mode, timeRange }: IUseSpanDetailOptions) {
  const detail = shallowRef<IRumRecordDetail | null>(null);
  const traceInfo = shallowRef(null);
  const related = shallowRef<IRumRelatedData>({});
  const loading = shallowRef(false);
  const relatedLoading = shallowRef(false);
  /** 请求序号，用于丢弃过期响应（快速切换记录时） */
  let requestId = 0;

  async function fetchDetail() {
    const current = context.value;
    if (!current?.record_id) {
      detail.value = null;
      related.value = {};
      return;
    }
    const seq = ++requestId;
    loading.value = true;
    related.value = {};
    const res = await getRecordDetail(current, mode.value);
    if (seq !== requestId) return;
    fetchTraceInfo(res);
    detail.value = res;
    loading.value = false;
    if (res) fetchRelated(res, current, seq);
  }

  async function fetchRelated(res: IRumRecordDetail, current: IRumDetailContext, seq: number) {
    const { loadRelated } = getSpanTypeDetailConfig(current.span_type);
    if (!loadRelated) return;
    relatedLoading.value = true;
    const data = await loadRelated(current, mode.value, res, timeRange.value).catch(() => null);
    if (seq !== requestId) return;
    related.value = data || {};
    relatedLoading.value = false;
  }

  async function fetchTraceInfo(detail: IRumRecordDetail) {
    if (!detail) {
      traceInfo.value = null;
    } else {
      const { links, bk_biz_id } = detail.origin_data;
      const url = `${location.origin}${window.site_url}rest/v2/overview/search/?query=${encodeURIComponent(links?.[0]?.trace_id)}&bk_biz_id=${encodeURIComponent(String(bk_biz_id))}`;
      fetchEventStream(url).then(res => {
        traceInfo.value = res[0]?.items?.[0];
      });
    }
  }

  watch(context, fetchDetail, { immediate: true });

  return { detail, traceInfo, related, loading, relatedLoading, refresh: fetchDetail };
}
