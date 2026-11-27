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
  type SpaceDirectoryQuery,
  queryAlertSpaceDirectory,
  querySpaceDirectory,
  SpaceDirectoryPager,
} from 'monitor-common/utils/space-directory';

import type { ISpaceItem } from 'monitor-common/typings';

export interface DirectoryOption extends ISpaceItem {
  hasData?: boolean;
  noAuth?: boolean;
}

/** Ordinary view permission and alarm visibility have independent result sets and cursors. */
export class PagedSpaceOptions {
  private lookupGeneration = 0;
  private order = new Map<number, DirectoryOption>();
  private references = new Map<number, DirectoryOption>();
  readonly alerts = new SpaceDirectoryPager(queryAlertSpaceDirectory);
  readonly allowed = new SpaceDirectoryPager();

  get rows(): DirectoryOption[] {
    return [...this.order.values()];
  }

  clearPages() {
    this.order.clear();
    this.allowed.close();
    this.alerts.close();
  }

  close() {
    this.lookupGeneration++;
    this.clearPages();
  }

  forgetReferences() {
    ++this.lookupGeneration;
    this.references.clear();
  }

  next(includeAlerts: boolean) {
    return Promise.allSettled([this.allowed.next(), ...(includeAlerts ? [this.alerts.next()] : [])]);
  }

  reset(query: SpaceDirectoryQuery, includeAlerts: boolean) {
    this.order.clear();
    return Promise.allSettled([this.allowed.reset(query), ...(includeAlerts ? [this.alerts.reset(query)] : [])]);
  }

  async resolveSelected(ids: number[], includeAlerts: boolean) {
    const generation = ++this.lookupGeneration;
    this.retain(ids);
    const missing = [...new Set(ids.filter(id => !this.references.has(id)))];
    try {
      for (let i = 0; i < missing.length; i += 100) {
        const batch = missing.slice(i, i + 100);
        const page = await querySpaceDirectory({ bkBizIds: batch, pageSize: batch.length });
        if (generation !== this.lookupGeneration) return false;
        for (const item of page.items) this.references.set(item.bk_biz_id, item);
        const unseen = batch.filter(id => !this.references.has(id));
        if (page.partial && unseen.length) throw new Error('Incomplete authorized space lookup');
        if (includeAlerts && unseen.length) {
          const alerts = await queryAlertSpaceDirectory({ bkBizIds: unseen, pageSize: unseen.length });
          if (generation !== this.lookupGeneration) return false;
          for (const item of alerts.items) this.references.set(item.bk_biz_id, item);
          if (alerts.partial && unseen.some(id => !this.references.has(id)))
            throw new Error('Incomplete alert space lookup');
        }
      }
    } catch (error) {
      if (generation !== this.lookupGeneration) return false;
      throw error;
    }
    return generation === this.lookupGeneration;
  }

  /** Keep only explicitly selected/current IDs when the search or page changes. */
  retain(ids: number[]) {
    const references = new Map<number, DirectoryOption>();
    for (const id of ids) {
      const item = this.selected(id);
      if (item) references.set(id, item);
    }
    this.references = references;
  }

  selected(id: number): DirectoryOption | undefined {
    return this.order.get(id) ?? this.references.get(id);
  }

  updateRows() {
    for (const item of this.allowed.items) this.order.set(item.bk_biz_id, item);
    for (const item of this.alerts.items) {
      if (!this.order.has(item.bk_biz_id)) this.order.set(item.bk_biz_id, item);
    }
  }
}
