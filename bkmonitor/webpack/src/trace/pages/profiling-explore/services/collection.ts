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
  createTask,
  deleteTask,
  editTask,
  listTasks,
  metaConfig,
  previewProcesses,
  switchTask,
} from 'monitor-api/modules/apm_profile_active_collection';

import type {
  CollectionMeta,
  CollectionPayload,
  CollectionTarget,
  CollectionTask,
  PreviewSelector,
  ProcessPreview,
} from '../types/collection';

const options = (signal: AbortSignal) => ({ signal, needMessage: false });
const mockParams = process.env.NODE_ENV === 'development' ? { is_mock: true } : {};

export function getCollectionMeta(bizId: number, signal: AbortSignal): Promise<CollectionMeta> {
  return metaConfig({ bk_biz_id: bizId, ...mockParams }, options(signal));
}

export function getCollectionTasks(
  bizId: number,
  signal: AbortSignal
): Promise<{ data: CollectionTask[]; total: number }> {
  return listTasks({ bk_biz_id: bizId, page: 1, page_size: 10000, ...mockParams }, options(signal));
}

export function getProcessPreview(
  bizId: number,
  target: CollectionTarget,
  selector: PreviewSelector,
  signal: AbortSignal
): Promise<ProcessPreview> {
  return previewProcesses(
    { bk_biz_id: bizId, target_config: target, process_selector: selector, ...mockParams },
    options(signal)
  );
}

export function removeCollectionTask(bizId: number, taskId: number, signal: AbortSignal): Promise<void> {
  return deleteTask({ bk_biz_id: bizId, task_id: taskId, ...mockParams }, options(signal));
}

export function saveCollectionTask(
  payload: CollectionPayload,
  taskId: number | undefined,
  signal: AbortSignal
): Promise<void> {
  return taskId
    ? editTask({ ...payload, task_id: taskId, ...mockParams }, options(signal))
    : createTask({ ...payload, ...mockParams }, options(signal));
}

export function toggleCollectionTask(
  bizId: number,
  taskId: number,
  enabled: boolean,
  signal: AbortSignal
): Promise<void> {
  return switchTask({ bk_biz_id: bizId, task_id: taskId, enabled, ...mockParams }, options(signal));
}
