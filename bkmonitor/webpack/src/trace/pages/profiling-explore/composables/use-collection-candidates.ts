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
import { type Ref, onScopeDispose, shallowRef, watch } from 'vue';

import {
  COLLECTION_CANDIDATE_MAX_LIMIT,
  COLLECTION_CANDIDATE_PAGE_SIZE,
  getCollectionCandidates,
} from '../services/collection-history';

import type { SelectionRange } from '../types';
import type { CollectionCandidate, CollectionCandidateField } from '../types/collection-history';

/**
 * 筛选下拉的候选值：首屏取前 20 个，输入关键字时按 keyword 远程搜索，滚动到底部递增 limit 重查。
 * 后端 topk 只按事件数返回前 N 个，不支持 offset，因此每次都用更大的 limit 全量替换。
 */
export function useCollectionCandidates(
  bizId: Ref<number>,
  range: Ref<null | SelectionRange>,
  fields: CollectionCandidateField[]
) {
  const candidates = shallowRef<Partial<Record<CollectionCandidateField, CollectionCandidate[]>>>({});
  const loading = shallowRef(false);
  // 关键字搜索进行中，此时下拉整列表替换为骨架；滚动加载不参与，只追加数据
  const searching = shallowRef(false);
  // 返回数量达到请求的 limit 时说明可能还有更多候选
  const hasMore = shallowRef(false);
  const error = shallowRef(false);
  // 当前关键字，用于区分「搜索结果为空」与「暂无数据」两种空态
  const keyword = shallowRef('');
  let limit = COLLECTION_CANDIDATE_PAGE_SIZE;
  let controller: AbortController;

  // 按当前关键字与 limit 重查一次；并发请求以最新的为准，旧请求直接中止
  async function fetchCandidates() {
    controller?.abort();
    const currentRange = range.value;
    if (!currentRange) {
      candidates.value = {};
      hasMore.value = false;
      // 时间范围失效时清掉进行中的请求状态，避免下拉一直停在加载中
      loading.value = false;
      error.value = false;
      searching.value = false;
      return;
    }
    const current = new AbortController();
    controller = current;
    loading.value = true;
    error.value = false;
    const results = await Promise.allSettled(
      fields.map(field =>
        getCollectionCandidates(bizId.value, currentRange, field, { keyword: keyword.value, limit }, current.signal)
      )
    );
    if (current.signal.aborted) return;
    candidates.value = Object.fromEntries(
      fields.map((field, index) => [field, results[index].status === 'fulfilled' ? results[index].value : []])
    );
    error.value = results.some(result => result.status === 'rejected');
    hasMore.value =
      limit < COLLECTION_CANDIDATE_MAX_LIMIT &&
      results.some(result => result.status === 'fulfilled' && result.value.length >= limit);
    loading.value = false;
    searching.value = false;
  }

  // 关键字变化时回到第一页，期间下拉展示骨架；
  // 关键字从有到无（手动清空或收起下拉）时保留已加载深度，重开下拉不丢滚动加载的候选
  function search(value: string) {
    const next = value || '';
    if (next || !keyword.value) limit = COLLECTION_CANDIDATE_PAGE_SIZE;
    keyword.value = next;
    searching.value = true;
    return fetchCandidates();
  }

  // 滚动到底部时扩大 limit 重查，没有更多候选或达到上限就不再请求
  function loadMore() {
    if (loading.value || !hasMore.value) return;
    limit = Math.min(limit + COLLECTION_CANDIDATE_PAGE_SIZE, COLLECTION_CANDIDATE_MAX_LIMIT);
    return fetchCandidates();
  }

  // 失败重试沿用当前关键字与 limit，不重置已加载的候选范围
  function reload() {
    return fetchCandidates();
  }

  // 业务或时间范围变化时清空关键字并完整回到首屏（先清 keyword 让 search 重置已加载深度）
  watch(
    [bizId, range],
    () => {
      keyword.value = '';
      search('');
    },
    { immediate: true }
  );
  onScopeDispose(() => controller?.abort());
  return { candidates, loading, searching, hasMore, error, keyword, search, loadMore, reload };
}
