/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import {
  buildClusterView,
  runClusterTablePipeline,
  type ClusterPipelineInput,
  type ClusterPatternRow,
  type ITableItem,
  type WalkVisibleWindowOptions,
} from './cluster-table-pipeline';

type WorkerRequest = {
  id: string;
  payload?: ClusterPipelineInput;
  type: 'clear' | 'ping' | 'pipeline' | 'walk';
  window?: WalkVisibleWindowOptions;
};

let rawCache: ClusterPatternRow[] = [];
let snapshotList: ITableItem[] = [];
let lastCounts = { childCount: 0, groupCount: 0, visibleCount: 0 };

const post = (payload: Record<string, any>) => {
  self.postMessage(payload);
};

self.onmessage = (event: MessageEvent<WorkerRequest>) => {
  const message = event.data;
  if (!message?.id) return;

  if (message.type === 'ping') {
    post({ id: message.id, ok: true, type: 'pong' });
    return;
  }

  if (message.type === 'clear') {
    rawCache = [];
    snapshotList = [];
    lastCounts = { childCount: 0, groupCount: 0, visibleCount: 0 };
    post({ id: message.id, ok: true, type: 'cleared' });
    return;
  }

  try {
    if (message.type === 'pipeline') {
      if (message.payload?.raw) {
        rawCache = message.payload.raw;
      }
      const result = runClusterTablePipeline({
        ...(message.payload as ClusterPipelineInput),
        raw: rawCache,
      });
      snapshotList = result.list;
      lastCounts = {
        childCount: result.childCount,
        groupCount: result.groupCount,
        visibleCount: result.visibleCount,
      };
    }

    const view = buildClusterView(snapshotList, lastCounts, message.window as WalkVisibleWindowOptions);
    post({ id: message.id, ok: true, type: `${message.type}-result`, result: view });
  } catch (error) {
    const errMessage = error instanceof Error ? error.message : String(error);
    post({ id: message.id, ok: false, type: `${message.type}-result`, error: errMessage });
  }
};
