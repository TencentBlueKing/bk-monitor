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

export type MemoryStatus = 'active' | 'stale' | 'replaced';

export interface MemoryItem {
  id: string;
  type: string;
  status: MemoryStatus;
  summary: string;
  hitCount: number;
  lastHitAt?: string;
}

export class MemoryStore {
  private items: MemoryItem[];

  constructor(items: MemoryItem[] = []) {
    this.items = items.map(item => ({ ...item }));
  }

  query(keyword: string): MemoryItem[] {
    const token = keyword.trim().toLowerCase();
    if (!token) {
      return [];
    }
    return this.items.filter(
      item => item.status === 'active' && `${item.id} ${item.summary}`.toLowerCase().includes(token),
    );
  }

  hit(id: string, at = new Date().toISOString()): MemoryItem | null {
    const item = this.items.find(entry => entry.id === id);
    if (!item) {
      return null;
    }
    item.hitCount += 1;
    item.lastHitAt = at;
    return { ...item };
  }

  markStale(id: string): void {
    const item = this.items.find(entry => entry.id === id);
    if (item) {
      item.status = 'stale';
    }
  }

  list(): MemoryItem[] {
    return this.items.map(item => ({ ...item }));
  }
}
