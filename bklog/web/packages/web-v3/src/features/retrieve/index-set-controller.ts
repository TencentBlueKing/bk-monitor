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

export interface IndexSetItem {
  id: string;
  name: string;
  scenario: string;
}

export interface IndexSetSnapshot {
  uiState: 'idle' | 'filtered' | 'error';
  activeId: string;
  filterQuery: string;
  error: string;
  items: IndexSetItem[];
}

export const DEFAULT_INDEX_SETS: IndexSetItem[] = [
  { id: 'index-a', name: 'nginx-access', scenario: 'linux' },
  { id: 'index-b', name: 'app-error', scenario: 'linux' },
];

export class IndexSetController {
  private snapshot: IndexSetSnapshot;

  constructor(items: IndexSetItem[] = DEFAULT_INDEX_SETS, activeId = items[0]?.id ?? '') {
    this.snapshot = {
      uiState: 'idle',
      activeId,
      filterQuery: '',
      error: '',
      items: items.map(item => ({ ...item })),
    };
  }

  getState(): IndexSetSnapshot {
    return { ...this.snapshot, items: this.snapshot.items.map(item => ({ ...item })) };
  }

  getVisibleItems(): IndexSetItem[] {
    const query = this.snapshot.filterQuery;
    if (!query) {
      return this.getState().items;
    }
    return this.snapshot.items.filter(item => item.name.includes(query) || item.id.includes(query));
  }

  setFilterQuery(value: string): IndexSetSnapshot {
    this.snapshot = { ...this.snapshot, filterQuery: String(value ?? '').trim(), uiState: 'filtered', error: '' };
    return this.getState();
  }

  select(id: string): IndexSetSnapshot {
    const found = this.snapshot.items.some(item => item.id === id);
    if (!found) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error: 'index set not found' };
      return this.getState();
    }
    this.snapshot = { ...this.snapshot, activeId: id, uiState: 'idle', error: '' };
    return this.getState();
  }
}
