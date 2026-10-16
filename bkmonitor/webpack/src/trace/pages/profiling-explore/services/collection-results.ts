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
import {
  exportResult,
  queryHosts,
  queryResult,
  resultDataTypes,
} from 'monitor-api/modules/apm_profile_active_collection';

import type { ProfileResult, SelectionRange } from '../types';
import type { CollectionHistoryFilters } from '../types/collection-history';
import type { CollectionDataType, CollectionHostResult, CollectionResultParams } from '../types/collection-results';

const mockParams = process.env.NODE_ENV === 'development' ? { is_mock: true } : {};
const options = (signal: AbortSignal) => ({ signal, needMessage: false });

export async function downloadCollectionProfile(
  params: CollectionResultParams,
  dataType: string,
  signal: AbortSignal
): Promise<{ data: Blob; filename: string }> {
  const config = { ...options(signal), responseType: 'blob' as const };
  try {
    return await exportResult({ ...params, data_type: dataType, ...mockParams }, config);
  } catch (error) {
    if (error instanceof Blob && error.type.includes('json')) {
      const detail = JSON.parse(await error.text());
      throw new Error(detail.message || detail.error_details || '导出失败，请重试');
    }
    throw error;
  }
}

export function getCollectionDataTypes(
  params: CollectionResultParams,
  signal: AbortSignal
): Promise<{ data_types: CollectionDataType[] }> {
  return resultDataTypes({ ...params, ...mockParams }, options(signal));
}

export function getCollectionProfile(
  params: CollectionResultParams,
  dataType: string,
  signal: AbortSignal
): Promise<ProfileResult> {
  return queryResult(
    { ...params, data_type: dataType, diagram_types: ['flamegraph', 'table'], ...mockParams },
    options(signal)
  );
}

export function getCollectionResults(
  bizId: number,
  range: SelectionRange,
  filters: CollectionHistoryFilters,
  offset: number,
  signal: AbortSignal
): Promise<{ data: CollectionHostResult[] }> {
  return queryHosts(
    { bk_biz_id: bizId, start_time: range[0], end_time: range[1], filters, offset, limit: 20, ...mockParams },
    options(signal)
  );
}
