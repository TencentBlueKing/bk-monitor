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

export type ResourceStatus = 'running' | 'stopped' | 'failed' | 'ready';
export type ResourceUiState = 'idle' | 'filtered' | 'error';

export interface ResourceItem {
  id: string;
  name: string;
  status: ResourceStatus;
  keyword?: string;
  extra?: Record<string, string | number>;
}

export interface ResourceSnapshot {
  uiState: ResourceUiState;
  filterQuery: string;
  status: ResourceStatus | 'all';
  error: string;
  items: ResourceItem[];
}

export interface SaveResourceInput {
  id?: string;
  name: string;
  status?: ResourceStatus;
  keyword?: string;
  extra?: Record<string, string | number>;
}

export class ResourceListController {
  private snapshot: ResourceSnapshot;

  constructor(items: ResourceItem[] = []) {
    this.snapshot = {
      uiState: 'idle',
      filterQuery: '',
      status: 'all',
      error: '',
      items: items.map(item => ({ ...item, extra: item.extra ? { ...item.extra } : undefined })),
    };
  }

  getState(): ResourceSnapshot {
    return {
      ...this.snapshot,
      items: this.snapshot.items.map(item => ({ ...item, extra: item.extra ? { ...item.extra } : undefined })),
    };
  }

  getVisibleItems(): ResourceItem[] {
    const query = this.snapshot.filterQuery;
    return this.snapshot.items.filter(item => {
      if (this.snapshot.status !== 'all' && item.status !== this.snapshot.status) {
        return false;
      }
      if (!query) {
        return true;
      }
      return item.name.includes(query) || String(item.keyword ?? '').includes(query);
    });
  }

  setFilterQuery(value: string): ResourceSnapshot {
    this.snapshot = {
      ...this.snapshot,
      filterQuery: String(value ?? '').trim(),
      uiState: 'filtered',
      error: '',
    };
    return this.getState();
  }

  setStatus(status: ResourceStatus | 'all'): ResourceSnapshot {
    this.snapshot = { ...this.snapshot, status, error: '' };
    return this.getState();
  }

  save(input: SaveResourceInput): ResourceSnapshot {
    const name = String(input.name ?? '').trim();
    if (!name) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error: 'name is required' };
      return this.getState();
    }
    const duplicated = this.snapshot.items.some(item => item.name === name && item.id !== input.id);
    if (duplicated) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error: 'name already exists' };
      return this.getState();
    }
    if (input.id) {
      this.snapshot = {
        ...this.snapshot,
        uiState: 'idle',
        error: '',
        items: this.snapshot.items.map(item => (
          item.id === input.id
            ? { ...item, name, status: input.status ?? item.status, keyword: input.keyword ?? item.keyword, extra: input.extra ?? item.extra }
            : item
        )),
      };
      return this.getState();
    }
    this.snapshot = {
      ...this.snapshot,
      uiState: 'idle',
      error: '',
      items: [
        ...this.snapshot.items,
        {
          id: `res-${Date.now()}`,
          name,
          status: input.status ?? 'ready',
          keyword: input.keyword,
          extra: input.extra,
        },
      ],
    };
    return this.getState();
  }

  remove(id: string): ResourceSnapshot {
    this.snapshot = {
      ...this.snapshot,
      error: '',
      items: this.snapshot.items.filter(item => item.id !== id),
    };
    return this.getState();
  }
}
