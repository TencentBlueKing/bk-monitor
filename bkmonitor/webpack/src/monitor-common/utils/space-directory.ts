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
import { listSpaces } from 'monitor-api/modules/commons';
import { bizWithAlertStatistics } from 'monitor-api/modules/home';

import type { ISpaceItem } from '../typings';
import type Pinyin from 'bk-magic-vue/lib/utils/pinyin';

export interface AlertSpaceDirectoryRecord extends ISpaceItem {
  hasData: boolean;
  noAuth: true;
}

export interface SpaceDirectoryPage<T extends ISpaceItem = ISpaceItem> {
  items: T[];
  nextCursor: null | string;
  partial?: boolean;
}

export interface SpaceDirectoryQuery {
  bkBizIds?: number[];
  cursor?: string;
  includeDemo?: boolean;
  pageSize?: number;
  query?: string;
  spaceUids?: string[];
  type?: string;
}

export const DIRECTORY_SPACE_TYPES = ['bkcc', 'default', 'bkci', 'bcs', 'bksaas'];

const owner = () => window.rawWindow || window;
const directoryScope = () => JSON.stringify([owner().uin, owner().bk_tenant_id]);

export function supportsSpaceDirectoryPages() {
  return owner().space_list_page_supported === true;
}

async function legacyPage<T extends ISpaceItem>(
  list: T[],
  options: SpaceDirectoryQuery
): Promise<SpaceDirectoryPage<T>> {
  const key = options.query?.trim().toLowerCase() || '';
  const pinyin = key ? (await import('bk-magic-vue/lib/utils/pinyin')).default : undefined;
  const ids = options.bkBizIds && new Set(options.bkBizIds);
  const uids = options.spaceUids && new Set(options.spaceUids);
  const size = options.pageSize ?? 20;
  const items: T[] = [];
  let i = options.cursor?.startsWith('local:') ? Number(options.cursor.slice(6)) : 0;
  for (; i < list.length; i++) {
    const row = list[i];
    if ((ids || options.includeDemo) && !(ids?.has(row.bk_biz_id) || (options.includeDemo && row.is_demo))) continue;
    if (uids && !uids.has(row.space_uid)) continue;
    if (
      options.type === 'bcs'
        ? row.space_type_id !== 'bkci' || !row.space_code
        : options.type && row.space_type_id !== options.type
    )
      continue;
    if (!matchesLegacyQuery(row, key, pinyin)) continue;
    if (items.length === size) break;
    items.push(normalizeRow(row));
  }
  return { items, nextCursor: i < list.length ? 'local:' + i : null };
}

function matchesLegacyQuery(row: ISpaceItem, query: string, pinyin?: typeof Pinyin) {
  if (!query) return true;
  const fields = [row.space_name, row.space_id, row.space_uid, row.bk_biz_id, row.type_name];
  if (
    fields.some(field =>
      String(field ?? '')
        .toLowerCase()
        .includes(query)
    )
  )
    return true;
  if (row.py_text || row.pyf_text) return row.py_text?.includes(query) || row.pyf_text?.includes(query);
  if (!pinyin?.isSupported()) return false;
  const syllables = pinyin.convertToPinyin(row.space_name, true, ',').toLowerCase().split(',');
  return (
    syllables.join('').includes(query) ||
    syllables
      .map(part => part[0])
      .join('')
      .includes(query)
  );
}

function normalizeRow<T extends ISpaceItem>(row: T): T {
  return { ...row, id: row.bk_biz_id, name: row.space_name, text: row.space_name };
}

const pending = new Map<string, Promise<SpaceDirectoryPage>>();
let legacyReply: undefined | { rows: ISpaceItem[]; scope: string };
interface LegacyAlertRow {
  bk_biz_id: number;
  bk_biz_name: string;
}
let legacyAlerts:
  | undefined
  | {
      byId: Map<number, LegacyAlertRow>;
      granted: Set<number>;
      received: Set<number>;
      scope: string;
    };

/** One open selector owns its search, cursor and accumulated rows. */
export class SpaceDirectoryPager {
  private cursor: null | string = null;
  private generation = 0;
  private options: SpaceDirectoryQuery = {};
  private pending = false;
  private async fetch(references: SpaceDirectoryQuery[] = []) {
    const generation = this.generation;
    this.pending = true;
    try {
      let page = await this.queryPage({ ...this.options, cursor: this.cursor ?? undefined });
      if (generation !== this.generation) return false;
      const saved = await Promise.all(
        references.map(query => this.queryPage(query).catch(() => ({ items: [], nextCursor: null, partial: true })))
      );
      if (generation !== this.generation) return false;
      const ids = new Set(this.items.map(row => row.bk_biz_id));
      // A legacy replica ignores a server cursor. Resume in its already-returned array past known records.
      while (page.nextCursor?.startsWith('local:') && page.items.every(row => ids.has(row.bk_biz_id))) {
        page = await this.queryPage({ ...this.options, cursor: page.nextCursor });
        if (generation !== this.generation) return false;
      }
      const additions = [];
      for (const batch of [...saved, page]) {
        for (const row of batch.items) {
          if (!ids.has(row.bk_biz_id)) {
            ids.add(row.bk_biz_id);
            additions.push(row);
          }
        }
      }
      this.items = this.items.concat(additions);
      this.cursor = page.nextCursor;
      this.partial = page.partial === true || saved.some(result => result.partial);
      this.failed = false;
      return true;
    } catch (error) {
      if (generation === this.generation) this.failed = true;
      throw error;
    } finally {
      if (generation === this.generation) this.pending = false;
    }
  }
  failed = false;
  items: ISpaceItem[] = [];

  partial = false;

  constructor(private readonly queryPage = querySpaceDirectory) {}
  get hasMore() {
    return this.cursor !== null;
  }
  get isLoading() {
    return this.pending;
  }

  get nextCursor() {
    return this.cursor;
  }

  close() {
    this.generation++;
    this.pending = false;
    this.cursor = null;
    this.items = [];
    this.partial = false;
    this.failed = false;
  }

  next() {
    if (!this.hasMore || this.pending) return Promise.resolve(false);
    return this.fetch();
  }

  reset(
    options: SpaceDirectoryQuery = {},
    saved?: { bkBizIds?: number[]; includeDemo?: boolean; spaceUids?: string[] }
  ) {
    this.close();
    this.options = options;
    const references = [];
    if (!options.query && !options.type) {
      if (saved?.bkBizIds?.length || saved?.includeDemo) {
        references.push({ bkBizIds: saved.bkBizIds?.slice(0, 100), pageSize: 100, includeDemo: saved.includeDemo });
      }
      if (saved?.spaceUids?.length) references.push({ spaceUids: saved.spaceUids.slice(0, 100), pageSize: 100 });
    }
    return this.fetch(references);
  }
}

/** Received alerts permit filtering those alerts; they do not grant access to the business. */
export async function queryAlertSpaceDirectory(
  options: SpaceDirectoryQuery = {}
): Promise<SpaceDirectoryPage<AlertSpaceDirectoryRecord>> {
  const scope = directoryScope();
  if (legacyAlerts?.scope === scope) return legacyAlertPage(options);
  const data = await bizWithAlertStatistics(
    {
      mode: 'page',
      page_size: options.pageSize ?? 20,
      query: options.query || undefined,
      type: options.type || undefined,
      cursor: options.cursor || undefined,
      bk_biz_ids: options.bkBizIds?.join(','),
    },
    { needBiz: false }
  );
  if (scope !== directoryScope()) throw new Error('Space directory identity changed');
  if (!Array.isArray(data?.items)) {
    if (![data?.business_list, data?.business_with_permission, data?.business_with_alert].every(Array.isArray)) {
      throw new Error('Invalid alert space directory response');
    }
    legacyAlerts = {
      scope,
      byId: new Map(data.business_list.map((row: LegacyAlertRow) => [row.bk_biz_id, row])),
      granted: new Set(data.business_with_permission.map((row: LegacyAlertRow) => row.bk_biz_id)),
      received: new Set(data.business_with_alert.map((row: LegacyAlertRow) => row.bk_biz_id)),
    };
    return legacyAlertPage(options);
  }
  return {
    items: data.items.map(row => alertRow(row, row.has_data)),
    nextCursor: data.next_cursor,
    partial: data.partial,
  };
}

/** Store only concurrent requests; permission changes take effect on the next open/search. */
export function querySpaceDirectory(options: SpaceDirectoryQuery = {}): Promise<SpaceDirectoryPage> {
  const host = owner();
  if (host !== window && host.querySpaceDirectory) return host.querySpaceDirectory(options);
  if ((options.bkBizIds?.length === 0 && !options.includeDemo) || options.spaceUids?.length === 0)
    return Promise.resolve({ items: [], nextCursor: null });
  const scope = directoryScope();
  if (legacyReply?.scope === scope) return legacyPage(legacyReply.rows, options);
  if (!supportsSpaceDirectoryPages()) {
    const directory = host.loadSpaceDirectory?.() ?? Promise.resolve(host.space_list || []);
    return directory.then(rows => legacyPage(rows, options));
  }
  const params = {
    mode: 'page',
    page_size: options.pageSize ?? 20,
    query: options.query || undefined,
    type: options.type || undefined,
    cursor: options.cursor || undefined,
    bk_biz_ids: options.bkBizIds?.length ? options.bkBizIds.join(',') : undefined,
    space_uids: options.spaceUids?.length ? options.spaceUids.join(',') : undefined,
    include_demo: options.includeDemo ? 1 : undefined,
  };
  const key = JSON.stringify([scope, params]);
  if (pending.has(key)) return pending.get(key);
  const job = listSpaces(params, { needBiz: false })
    .then(data => {
      if (scope !== directoryScope()) throw new Error('Space directory identity changed');
      // During a rolling downgrade an older replica ignores mode and replies with the authorized array.
      if (Array.isArray(data)) {
        legacyReply = { scope, rows: data };
        return legacyPage(data, { ...options, cursor: undefined });
      }
      if (!Array.isArray(data?.items) || !(data.next_cursor === null || typeof data.next_cursor === 'string')) {
        throw new Error('Invalid space directory page');
      }
      return { items: data.items.map(normalizeRow), nextCursor: data.next_cursor, partial: data.partial === true };
    })
    .finally(() => pending.delete(key));
  pending.set(key, job);
  return job;
}

function alertRow(row: LegacyAlertRow, hasData: boolean): AlertSpaceDirectoryRecord {
  return {
    id: row.bk_biz_id,
    bk_biz_id: row.bk_biz_id,
    text: row.bk_biz_name,
    name: row.bk_biz_name,
    space_name: row.bk_biz_name,
    space_id: String(row.bk_biz_id),
    space_code: '',
    space_uid: '',
    space_type_id: row.bk_biz_id > 0 ? 'bkcc' : '',
    type_name: '',
    status: '',
    is_demo: false,
    hasData,
    noAuth: true,
  };
}

function legacyAlertPage(options: SpaceDirectoryQuery) {
  const { byId, received, granted } = legacyAlerts;
  const rows = [];
  for (const id of options.bkBizIds || received) {
    const row = byId.get(id);
    if (row && !granted.has(id)) rows.push(alertRow(row, received.has(id)));
  }
  return legacyPage<AlertSpaceDirectoryRecord>(rows, options);
}
