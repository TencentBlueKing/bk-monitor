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

import { getCollectionCandidates } from '../services/collection-history';

import type { SelectionRange } from '../types';
import type { CollectionCandidate, CollectionCandidateField } from '../types/collection-history';

export function useCollectionCandidates(bizId: Ref<number>, range: Ref<SelectionRange>) {
  const candidates = shallowRef<Partial<Record<CollectionCandidateField, CollectionCandidate[]>>>({});
  const candidateLoading = shallowRef(false);
  // 任一候选接口失败即置位，具体提示与重试入口由使用方渲染
  const candidateError = shallowRef(false);
  let controller: AbortController;

  async function loadCandidates() {
    controller?.abort();
    const current = new AbortController();
    controller = current;
    candidates.value = {};
    candidateError.value = false;
    candidateLoading.value = false;
    if (!range.value) return;
    candidateLoading.value = true;
    const fields: CollectionCandidateField[] = ['target', 'task_name', 'process_names', 'process_pids'];
    const results = await Promise.allSettled(
      fields.map(field => getCollectionCandidates(bizId.value, range.value, field, current.signal))
    );
    if (current.signal.aborted) return;
    candidates.value = Object.fromEntries(
      results.map((result, index) => [fields[index], result.status === 'fulfilled' ? result.value : []])
    );
    candidateError.value = results.some(result => result.status === 'rejected');
    candidateLoading.value = false;
  }

  watch([bizId, range], loadCandidates, { immediate: true });
  onScopeDispose(() => controller?.abort());
  return { candidates, candidateLoading, candidateError, loadCandidates };
}
