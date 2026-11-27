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

import { querySpaceDirectory, SpaceDirectoryPager, supportsSpaceDirectoryPages } from './space-directory';

import type { ISpaceItem } from '../typings';

/** Adds the form's failure state and its established select-all limit to a directory pager. */
export class FormSpacePages {
  private limit: number;
  private pager = new SpaceDirectoryPager();
  private partial = false;
  private query = '';
  private revision = 0;
  failed = false;

  constructor(limit = Number.POSITIVE_INFINITY) {
    this.limit = limit;
  }

  get hasMore() {
    return this.items.length < this.limit && this.pager.hasMore;
  }
  get items() {
    return this.pager.items;
  }
  get loading() {
    return this.pager.isLoading;
  }

  /** Select-all enumerates the remaining matches only after the user explicitly chooses it. */
  async allMatching() {
    const revision = this.revision;
    if (!this.items.length && !(await this.fetchPage())) return;
    if (this.partial) {
      this.failed = true;
      return;
    }
    const ids = new Set(this.items.map(row => row.bk_biz_id));
    let cursor = this.pager.nextCursor;
    try {
      while (cursor && ids.size < this.limit) {
        const page = await querySpaceDirectory({
          query: this.query,
          cursor,
          pageSize: Math.min(100, this.limit - ids.size),
        });
        if (revision !== this.revision) return;
        if (page.partial) {
          this.partial = true;
          this.failed = true;
          return;
        }
        for (const row of page.items) ids.add(row.bk_biz_id);
        cursor = page.nextCursor;
      }
      if (revision === this.revision) return Array.from(ids).slice(0, this.limit);
    } catch {
      if (revision === this.revision) this.failed = true;
    }
  }

  async fetchPage() {
    if (this.loading || (this.items.length && !this.hasMore)) return false;
    const revision = this.revision;
    this.failed = false;
    try {
      const accepted = await (this.pager.hasMore
        ? this.pager.next()
        : this.pager.reset({ query: this.query, pageSize: 100 }));
      if (accepted && revision === this.revision) {
        this.partial ||= this.pager.partial;
        this.failed = this.partial;
      }
      return accepted;
    } catch {
      if (revision === this.revision) this.failed = true;
      return false;
    }
  }

  reset() {
    this.revision++;
    this.partial = false;
    this.failed = false;
    this.pager.close();
  }

  retryOrNext() {
    return this.partial ? this.search(this.query) : this.fetchPage();
  }

  search(query = '') {
    this.reset();
    this.query = query;
    return this.fetchPage();
  }
}

export function demoSpaceUrl(href: string, id: number) {
  const url = new URL(href);
  url.searchParams.delete('space_uid');
  url.searchParams.set('bizId', String(id));
  return url.href;
}

/** Application APIs need a currently authorized, non-demo business as their request context. */
export async function getAuthorizedSpaceContext(known: ISpaceItem[]) {
  const local = known.find(item => !item.is_demo);
  if (local) return local.bk_biz_id;
  const pager = new SpaceDirectoryPager();
  try {
    await pager.reset({ pageSize: 20 });
    while (true) {
      const authorized = pager.items.find(item => !item.is_demo);
      if (authorized || !pager.hasMore) return authorized?.bk_biz_id;
      await pager.next();
    }
  } catch {
    return undefined;
  }
}

/** Only request the demo referenced by this introduction. */
export async function guideDemoSpace(buttons: undefined | { name: string }[]) {
  if (!buttons?.some(button => button.name === 'DEMO') || !supportsSpaceDirectoryPages()) return;
  const { items } = await querySpaceDirectory({ includeDemo: true, pageSize: 1 });
  return items.find(space => space.is_demo);
}

/** Resolve saved or selected IDs without using the current directory page as an authorization list. */
export async function resolveSelectedSpaces(
  ids: (number | string)[],
  known: ISpaceItem[] = [],
  requireComplete = false
): Promise<ISpaceItem[]> {
  const requested = [
    ...new Set(
      ids
        .filter(id => id !== '' && id != null)
        .map(Number)
        .filter(Number.isFinite)
    ),
  ];
  const byId = new Map(known.map(item => [Number(item.bk_biz_id), item]));
  let partial = false;
  const missing = requested.filter(id => !byId.has(id));
  for (let start = 0; start < missing.length; start += 100) {
    const group = missing.slice(start, start + 100);
    let cursor: string | undefined;
    do {
      const page = await querySpaceDirectory({ bkBizIds: group, pageSize: group.length, cursor });
      partial ||= page.partial === true;
      for (const item of page.items) byId.set(Number(item.bk_biz_id), item);
      cursor = page.nextCursor || undefined;
    } while (cursor);
  }
  if (requireComplete && partial && requested.some(id => !byId.has(id))) throw new Error('Incomplete space directory');
  return requested.map(id => byId.get(id)).filter((item): item is ISpaceItem => item != null);
}
