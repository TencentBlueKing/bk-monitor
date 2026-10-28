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

export type GrepMountAction = 'reload' | 'idle' | 'wait';
export type GrepUiState = 'idle' | 'waiting' | 'loading' | 'success' | 'empty' | 'error';

export interface GrepSnapshot {
  uiState: GrepUiState;
  field: string;
  pattern: string;
  matches: LogRecord[];
  error: string;
  requestId: number;
}

export function resolveGrepMountAction(isSearching: boolean, field: string): GrepMountAction {
  if (isSearching) {
    return 'wait';
  }
  return field.trim() ? 'reload' : 'idle';
}

function readField(record: LogRecord, field: string): string {
  if (field === 'log' || !field) {
    return record.log;
  }
  const value = (record as Record<string, unknown>)[field];
  return value == null ? '' : String(value);
}

export class GrepController {
  private snapshot: GrepSnapshot = {
    uiState: 'idle',
    field: 'log',
    pattern: '',
    matches: [],
    error: '',
    requestId: 0,
  };

  getState(): GrepSnapshot {
    return { ...this.snapshot, matches: [...this.snapshot.matches] };
  }

  setField(field: string): GrepSnapshot {
    this.snapshot = { ...this.snapshot, field: String(field ?? '').trim(), error: '' };
    return this.getState();
  }

  setPattern(pattern: string): GrepSnapshot {
    this.snapshot = { ...this.snapshot, pattern: String(pattern ?? '').trim(), error: '' };
    return this.getState();
  }

  search(records: LogRecord[], isSearching = false): GrepSnapshot {
    const action = resolveGrepMountAction(isSearching, this.snapshot.field);
    if (action === 'wait') {
      this.snapshot = { ...this.snapshot, uiState: 'waiting', error: '' };
      return this.getState();
    }
    if (action === 'idle') {
      this.snapshot = { ...this.snapshot, uiState: 'idle', matches: [], error: '' };
      return this.getState();
    }

    const requestId = this.snapshot.requestId + 1;
    this.snapshot = { ...this.snapshot, uiState: 'loading', requestId, error: '' };

    try {
      const matcher = this.createMatcher(this.snapshot.pattern);
      const matches = records.filter(item => matcher(readField(item, this.snapshot.field)));
      if (requestId !== this.snapshot.requestId) {
        return this.getState();
      }
      this.snapshot = {
        ...this.snapshot,
        uiState: matches.length ? 'success' : 'empty',
        matches,
        error: '',
      };
    } catch (error) {
      if (requestId !== this.snapshot.requestId) {
        return this.getState();
      }
      this.snapshot = {
        ...this.snapshot,
        uiState: 'error',
        error: error instanceof Error ? error.message : String(error),
      };
    }
    return this.getState();
  }

  private createMatcher(pattern: string): (value: string) => boolean {
    if (!pattern) {
      return () => true;
    }
    try {
      const regex = new RegExp(pattern, 'i');
      return value => regex.test(value);
    } catch {
      throw new Error('invalid grep pattern');
    }
  }
}
