/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import type { LogRecord } from './retrieve-search-controller';

export type ContextUiState = 'idle' | 'waiting' | 'success' | 'empty';

export interface ContextSnapshot {
  uiState: ContextUiState;
  anchorId: string | null;
  before: LogRecord[];
  after: LogRecord[];
}

export class ContextController {
  private snapshot: ContextSnapshot = {
    uiState: 'idle',
    anchorId: null,
    before: [],
    after: [],
  };

  getState(): ContextSnapshot {
    return {
      ...this.snapshot,
      before: [...this.snapshot.before],
      after: [...this.snapshot.after],
    };
  }

  open(records: LogRecord[], anchorId: string, isSearching = false, windowSize = 1): ContextSnapshot {
    if (isSearching) {
      this.snapshot = { ...this.snapshot, uiState: 'waiting', anchorId, before: [], after: [] };
      return this.getState();
    }
    const index = records.findIndex(item => item.id === anchorId);
    if (index < 0) {
      this.snapshot = { uiState: 'empty', anchorId, before: [], after: [] };
      return this.getState();
    }
    this.snapshot = {
      uiState: 'success',
      anchorId,
      before: records.slice(Math.max(0, index - windowSize), index),
      after: records.slice(index + 1, index + 1 + windowSize),
    };
    return this.getState();
  }
}
