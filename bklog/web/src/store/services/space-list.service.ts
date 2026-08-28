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
import { markRaw } from 'vue';
import * as pinyin from 'tiny-pinyin';
import * as patcher56L from 'tiny-pinyin/dist/patchers/56l.js';

if (pinyin.isSupported() && patcher56L.shouldPatch(pinyin.genToken)) {
  pinyin.patchDict(patcher56L);
}

export type SpaceListItem = {
  bk_biz_id: string;
  external_permission: string[];
  id: number | string;
  is_use: boolean;
  name: string;
  permission?: Record<string, boolean>;
  py_text: string;
  space_code: string;
  space_full_code_name: string;
  space_id: string;
  space_name: string;
  space_type_id?: string;
  space_type_name?: string;
  space_uid: string;
  tags: Array<{ id?: string; name?: string; type?: string }>;
};

const translate = (message: string) => {
  const t = (window as any).mainComponent?.$t;
  return typeof t === 'function' ? t.call((window as any).mainComponent, message) : message;
};

const toPinyin = (spaceName: string) => {
  if (!spaceName || !pinyin.isSupported()) return '';
  return pinyin.convertToPinyin(spaceName, true).replace(/true/g, '');
};

export const normalizeSpaceListItem = (item: Record<string, any> = {}): SpaceListItem => {
  const spaceName = item.space_name ?? '';
  const spaceTypeId = item.space_type_id;
  const defaultTag = {
    id: spaceTypeId,
    name: item.space_type_name,
    type: spaceTypeId,
  };
  const isBkciContainer = spaceTypeId === 'bkci' && item.space_code;
  const tags = isBkciContainer
    ? [
        defaultTag,
        {
          id: 'bcs',
          name: translate('容器项目'),
          type: 'bcs',
        },
      ]
    : [defaultTag];

  return markRaw({
    id: item.id ?? item.bk_biz_id,
    bk_biz_id: `${item.bk_biz_id ?? ''}`,
    space_uid: `${item.space_uid ?? ''}`,
    space_id: item.space_id != null ? `${item.space_id}` : '',
    space_code: item.space_code ?? '',
    space_name: spaceName,
    space_type_id: spaceTypeId,
    space_type_name: item.space_type_name,
    permission: item.permission && typeof item.permission === 'object' ? { ...item.permission } : item.permission,
    external_permission: Array.isArray(item.external_permission) ? [...item.external_permission] : [],
    is_use: !!item.is_use,
    space_full_code_name: `${spaceName}(#${item.space_id ?? ''})`,
    name: spaceName.replace(/\[.*?\]/, ''),
    py_text: toPinyin(spaceName),
    tags,
  });
};

export const normalizeSpaceList = (spaceList: Record<string, any>[] = []): SpaceListItem[] => {
  return (Array.isArray(spaceList) ? spaceList : []).map(item => normalizeSpaceListItem(item));
};

export const patchNormalizedSpaceItem = (
  list: SpaceListItem[] = [],
  matcher: (_item: SpaceListItem) => boolean,
  patch: Partial<SpaceListItem>,
): SpaceListItem[] => {
  const index = list.findIndex(matcher);
  if (index < 0) return list;
  const next = list.slice();
  next[index] = markRaw({
    ...list[index],
    ...patch,
  });
  return next;
};
