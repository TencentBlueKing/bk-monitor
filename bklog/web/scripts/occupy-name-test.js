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

/*
 * Occupied placeholder name validation regression test.
 *
 * Run:
 *   node scripts/occupy-name-test.js
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const occupyRulesPath = path.resolve(
  __dirname,
  '../src/views/retrieve-v3/search-result/log-clustering/log-table/content-table/cluster-popover/regex-match/occupy-rules.ts',
);
const source = fs.readFileSync(occupyRulesPath, 'utf8');

assert.match(
  source,
  /OCCUPY_NAME_REGEXP = \/\^\[A-Za-z0-9_-\]\+\$\//,
  'frontend occupy regex must stay aligned with backend PATTERN_PLACEHOLDER_REGEX',
);
assert.match(source, /class RegexTableValidateError extends Error/);

const OCCUPY_NAME_REGEXP = /^[A-Za-z0-9_-]+$/;
const isValidOccupyName = value => OCCUPY_NAME_REGEXP.test(value);

assert.equal(isValidOccupyName('jsonBodyInfo'), true);
assert.equal(isValidOccupyName('player_CHAR'), true);
assert.equal(isValidOccupyName('RAW_JSON'), true);
assert.equal(isValidOccupyName('MAP_INFO'), true);
assert.equal(isValidOccupyName('IP'), true);
assert.equal(isValidOccupyName('CHAR-1'), true);

assert.equal(isValidOccupyName('player CHAR'), false);
assert.equal(isValidOccupyName('json$body'), false);
assert.equal(isValidOccupyName('中文占位符'), false);
assert.equal(isValidOccupyName('JSON.BODY'), false);
assert.equal(isValidOccupyName(''), false);

console.log('occupy-name-test: ok');
