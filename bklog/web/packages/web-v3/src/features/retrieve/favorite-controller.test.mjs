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

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { FavoriteController } from './favorite-controller.ts';

describe('FavoriteController', () => {
  it('AC-001 trims filter and matches name or keyword', () => {
    const controller = new FavoriteController();
    controller.setFilterQuery('  error  ');
    const names = controller.getVisibleGroups().flatMap(group => group.favorites.map(item => item.name));
    assert.deepEqual(names, ['错误日志']);
    controller.setFilterQuery('timeout');
    const keywords = controller.getVisibleGroups().flatMap(group => group.favorites.map(item => item.keyword));
    assert.deepEqual(keywords, ['timeout']);
  });

  it('AC-002 current-only keeps the current index set', () => {
    const controller = new FavoriteController();
    controller.setCurrentOnly(true);
    const ids = controller.getVisibleGroups().flatMap(group => group.favorites.map(item => item.id));
    assert.deepEqual(ids, ['fav-error', 'fav-timeout']);
  });

  it('AC-003 rejects duplicate names in the same group', () => {
    const controller = new FavoriteController();
    const rejected = controller.save({
      name: '  错误日志  ',
      keyword: 'panic',
      groupId: 'private',
      indexSetId: 'index-a',
    });
    assert.equal(rejected.uiState, 'error');
    assert.equal(rejected.groups[0].favorites.length, 2);
  });

  it('AC-004 apply selects the favorite and returns keyword', () => {
    const controller = new FavoriteController();
    const result = controller.apply('fav-timeout');
    assert.equal(result.keyword, 'timeout');
    assert.equal(result.state.activeId, 'fav-timeout');
    assert.equal(result.state.uiState, 'selected');
  });

  it('AC-005 delete clears active selection', () => {
    const controller = new FavoriteController();
    controller.apply('fav-error');
    const next = controller.remove('fav-error');
    assert.equal(next.activeId, null);
    assert.equal(next.uiState, 'idle');
    assert.equal(next.groups[0].favorites.some(item => item.id === 'fav-error'), false);
  });
});
