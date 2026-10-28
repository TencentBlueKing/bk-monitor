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

export type FavoriteVisibleType = 'private' | 'public';
export type FavoriteUiState = 'idle' | 'selected' | 'error';

export interface FavoriteItem {
  id: string;
  name: string;
  keyword: string;
  groupId: string;
  groupName: string;
  visibleType: FavoriteVisibleType;
  indexSetId: string;
}

export interface FavoriteGroup {
  groupId: string;
  groupName: string;
  visibleType: FavoriteVisibleType;
  favorites: FavoriteItem[];
}

export interface FavoriteSnapshot {
  uiState: FavoriteUiState;
  filterQuery: string;
  currentOnly: boolean;
  currentIndexSetId: string;
  activeId: string | null;
  error: string;
  groups: FavoriteGroup[];
}

export interface SaveFavoriteInput {
  name: string;
  keyword: string;
  groupId: string;
  indexSetId: string;
}

const DEFAULT_GROUPS: FavoriteGroup[] = [
  {
    groupId: 'private',
    groupName: '个人收藏',
    visibleType: 'private',
    favorites: [
      {
        id: 'fav-error',
        name: '错误日志',
        keyword: 'error',
        groupId: 'private',
        groupName: '个人收藏',
        visibleType: 'private',
        indexSetId: 'index-a',
      },
      {
        id: 'fav-login',
        name: '登录日志',
        keyword: 'login',
        groupId: 'private',
        groupName: '个人收藏',
        visibleType: 'private',
        indexSetId: 'index-b',
      },
    ],
  },
  {
    groupId: 'public',
    groupName: '公共收藏',
    visibleType: 'public',
    favorites: [
      {
        id: 'fav-timeout',
        name: '超时',
        keyword: 'timeout',
        groupId: 'public',
        groupName: '公共收藏',
        visibleType: 'public',
        indexSetId: 'index-a',
      },
    ],
  },
];

function cloneGroups(groups: FavoriteGroup[]): FavoriteGroup[] {
  return groups.map(group => ({
    ...group,
    favorites: group.favorites.map(item => ({ ...item })),
  }));
}

export class FavoriteController {
  private snapshot: FavoriteSnapshot;

  constructor(groups: FavoriteGroup[] = DEFAULT_GROUPS, currentIndexSetId = 'index-a') {
    this.snapshot = {
      uiState: 'idle',
      filterQuery: '',
      currentOnly: false,
      currentIndexSetId,
      activeId: null,
      error: '',
      groups: cloneGroups(groups),
    };
  }

  getState(): FavoriteSnapshot {
    return {
      ...this.snapshot,
      groups: cloneGroups(this.snapshot.groups),
    };
  }

  getVisibleGroups(): FavoriteGroup[] {
    const query = this.snapshot.filterQuery;
    return this.snapshot.groups
      .map(group => ({
        ...group,
        favorites: group.favorites.filter(item => {
          if (this.snapshot.currentOnly && item.indexSetId !== this.snapshot.currentIndexSetId) {
            return false;
          }
          if (!query) {
            return true;
          }
          return item.name.includes(query) || item.keyword.includes(query);
        }),
      }))
      .filter(group => group.favorites.length > 0);
  }

  replaceGroups(groups: FavoriteGroup[], currentIndexSetId = this.snapshot.currentIndexSetId): FavoriteSnapshot {
    this.snapshot = {
      ...this.snapshot,
      currentIndexSetId,
      groups: groups.length ? cloneGroups(groups) : this.snapshot.groups,
      activeId: null,
      uiState: 'idle',
      error: '',
    };
    return this.getState();
  }

  setFilterQuery(value: string): FavoriteSnapshot {
    this.snapshot = {
      ...this.snapshot,
      filterQuery: String(value ?? '').trim(),
      error: '',
    };
    return this.getState();
  }

  setCurrentOnly(value: boolean): FavoriteSnapshot {
    this.snapshot = {
      ...this.snapshot,
      currentOnly: Boolean(value),
    };
    return this.getState();
  }

  apply(id: string): { state: FavoriteSnapshot; keyword: string | null } {
    const item = this.findById(id);
    if (!item) {
      return { state: this.getState(), keyword: null };
    }
    this.snapshot = {
      ...this.snapshot,
      uiState: 'selected',
      activeId: item.id,
      error: '',
    };
    return { state: this.getState(), keyword: item.keyword };
  }

  save(input: SaveFavoriteInput): FavoriteSnapshot {
    const name = String(input.name ?? '').trim();
    const keyword = String(input.keyword ?? '').trim();
    const group = this.snapshot.groups.find(item => item.groupId === input.groupId);
    if (!name || !keyword || !group) {
      this.snapshot = {
        ...this.snapshot,
        uiState: 'error',
        error: 'name and keyword are required',
      };
      return this.getState();
    }
    if (group.favorites.some(item => item.name === name)) {
      this.snapshot = {
        ...this.snapshot,
        uiState: 'error',
        error: 'favorite name already exists in group',
      };
      return this.getState();
    }
    const next: FavoriteItem = {
      id: `fav-${Date.now()}`,
      name,
      keyword,
      groupId: group.groupId,
      groupName: group.groupName,
      visibleType: group.visibleType,
      indexSetId: input.indexSetId,
    };
    this.snapshot = {
      ...this.snapshot,
      uiState: this.snapshot.activeId ? 'selected' : 'idle',
      error: '',
      groups: this.snapshot.groups.map(item => (
        item.groupId === group.groupId
          ? { ...item, favorites: [...item.favorites, next] }
          : item
      )),
    };
    return this.getState();
  }

  remove(id: string): FavoriteSnapshot {
    const existed = Boolean(this.findById(id));
    if (!existed) {
      return this.getState();
    }
    const clearingActive = this.snapshot.activeId === id;
    this.snapshot = {
      ...this.snapshot,
      uiState: clearingActive ? 'idle' : this.snapshot.uiState,
      activeId: clearingActive ? null : this.snapshot.activeId,
      error: '',
      groups: this.snapshot.groups.map(group => ({
        ...group,
        favorites: group.favorites.filter(item => item.id !== id),
      })),
    };
    return this.getState();
  }

  private findById(id: string): FavoriteItem | null {
    for (const group of this.snapshot.groups) {
      const item = group.favorites.find(favorite => favorite.id === id);
      if (item) {
        return item;
      }
    }
    return null;
  }
}
