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
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { comparePng, writeVisualReport } from './visual-diff.mjs';

const require = createRequire(resolve(dirname(fileURLToPath(import.meta.url)), '../../packages/web-v3/package.json'));
const { PNG } = require('pngjs');

function writeSolid(filePath, rgba) {
  const png = new PNG({ width: 2, height: 2 });
  for (let index = 0; index < png.data.length; index += 4) {
    png.data[index] = rgba[0];
    png.data[index + 1] = rgba[1];
    png.data[index + 2] = rgba[2];
    png.data[index + 3] = rgba[3];
  }
  writeFileSync(filePath, PNG.sync.write(png));
}

test('visual diff writes an identical and a different report', () => {
  const dir = mkdtempSync(join(tmpdir(), 'bklog-visual-'));
  try {
    const left = join(dir, 'left.png');
    const right = join(dir, 'right.png');
    const changed = join(dir, 'changed.png');
    writeSolid(left, [58, 132, 255, 255]);
    writeSolid(right, [58, 132, 255, 255]);
    writeSolid(changed, [255, 255, 255, 255]);
    const same = comparePng(left, right);
    const diff = comparePng(left, changed);
    assert.equal(same.status, 'identical');
    assert.equal(same.differentPixels, 0);
    assert.equal(diff.status, 'different');
    assert.equal(diff.differentPixels, 4);
    const reportPath = join(dir, 'report.json');
    writeVisualReport({ same, diff }, reportPath);
    const saved = JSON.parse(readFileSync(reportPath, 'utf8'));
    assert.equal(saved.same.status, 'identical');
    assert.equal(saved.diff.differentPixels, 4);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
