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
import { supportsSpaceDirectoryPages } from './space-directory';
import { resolveSelectedSpaces } from './space-selection';

import type { ISpaceItem } from '../typings';

export function eventSpaceId(id: number, resolved: Record<number, string>, legacy: ISpaceItem[]) {
  if (supportsSpaceDirectoryPages()) return resolved[id] || id;
  return legacy.find(space => +space.bk_biz_id === +id)?.space_id || id;
}

export async function resolveEventSpaceIds(events: { bk_biz_id?: number }[]): Promise<Record<number, string>> {
  if (!supportsSpaceDirectoryPages()) return {};
  // For CMDB businesses the event's business ID already is the public space ID.
  const ids = events.map(event => Number(event.bk_biz_id)).filter(id => id < 0);
  const spaces = await resolveSelectedSpaces(ids).catch(() => []);
  return Object.fromEntries(spaces.map(space => [space.bk_biz_id, space.space_id]));
}
