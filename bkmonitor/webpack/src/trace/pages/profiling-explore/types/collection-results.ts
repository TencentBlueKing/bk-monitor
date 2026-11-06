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

import type { CollectionMethod, CollectionType } from './collection';
import type { CollectionExecutionHost, CollectionExecutionKey, CollectionHistoryFilters } from './collection-history';
import type { ProfileViewState } from './index';

export interface CollectionDataType {
  key: string;
  name: string;
}

/** hosts/query：一台主机的一次采集。 */
export interface CollectionHostResult extends Omit<CollectionExecutionHost, 'message'> {
  collection_method: CollectionMethod;
  collection_type: CollectionType;
  scheduled_at: number;
  task: { name: string; schedule_type: CollectionExecutionKey['schedule_type']; task_id?: number };
}

export interface CollectionResultParams {
  bk_biz_id: number;
  bk_host_id: number;
  finished_at: number;
  scheduled_at: number;
  started_at: number;
  task_id?: number;
}

export interface CollectionResultsState {
  dataType: string;
  execution: CollectionExecutionKey | null;
  filters: CollectionHistoryFilters;
  view: ProfileViewState;
}
