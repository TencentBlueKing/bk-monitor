/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
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

import { buildDialogPayload, buildSearchPayload, parseRetrieveRoute } from './retrieve-data-adapter.ts';
import { RetrieveWorkbenchController } from './retrieve-workbench-controller.ts';

describe('retrieve-data-adapter', () => {
  it('AC-001 parses the V2 hash route contract', () => {
    const route = parseRetrieveRoute('http://127.0.0.1:41001/#/retrieve/38077?spaceUid=bkcc__5000140&bizId=5000140&tab=origin');
    assert.deepEqual(route, {
      indexSetId: '38077',
      spaceUid: 'bkcc__5000140',
      bizId: '5000140',
      tab: 'origin',
    });
  });

  it('AC-002 builds a search payload from the workbench snapshot', () => {
    const controller = new RetrieveWorkbenchController(parseRetrieveRoute('http://x/#/retrieve/38077?spaceUid=s&bizId=b&tab=origin'), 2_000);
    controller.dispatch({
      type: 'query/change',
      keyword: 'error',
      mode: 'ai',
      conditions: [{ field: 'log', operator: 'contains', value: 'timeout', logic: 'AND' }],
    });
    const payload = buildSearchPayload(controller.getState(), { size: 20 });
    assert.equal(payload.keyword, 'error');
    assert.equal(payload.search_mode, 'ai');
    assert.equal(payload.index_set_id, '38077');
    assert.equal(payload.space_uid, 's');
    assert.equal(payload.biz_id, 'b');
    assert.equal(payload.size, 20);
    assert.equal(payload.addition[0].field, 'log');
  });

  it('AC-003 makes dialog payloads carry fallback visibility', () => {
    const controller = new RetrieveWorkbenchController(parseRetrieveRoute('http://x/#/retrieve/38077?spaceUid=s&bizId=b&tab=origin'), 2_000);
    const payload = buildDialogPayload(controller.getState(), [
      { name: 'log', type: 'string', kind: 'text', alias: '日志', visible: true, analyzable: true },
      { name: 'path', type: 'string', kind: 'text', alias: '路径', visible: false, analyzable: false },
    ], true);
    assert.deepEqual(payload.fields, ['log']);
    assert.equal(payload.fallbackVisible, true);
  });
});
