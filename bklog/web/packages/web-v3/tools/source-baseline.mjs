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

import {readFileSync, realpathSync} from 'node:fs';
import {resolve, sep, relative} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

// Analysis-phase reference only. V2 retirement remains gated on full acceptance.
const root = realpathSync(fileURLToPath(new URL('../../web-v2/src/', import.meta.url)));
const inventory = JSON.parse(readFileSync(new URL('../../../analyze-info/source/entry-graph.json', import.meta.url), 'utf8'));
const references = new Map(inventory.files.map(file => [file.file, file.sha256]));
const hash = body => createHash('sha256').update(body).digest('hex');

export function baselineUrl(sourcePath) {
  const file = realpathSync(resolve(root, sourcePath));
  if (!file.startsWith(root + sep)) throw new Error('BASELINE_PATH_OUTSIDE_V2');
  const key = relative(root, file);
  const expected = references.get(key);
  if (!expected || hash(readFileSync(file)) !== expected) throw new Error('BASELINE_SOURCE_NOT_PINNED:' + key);
  return pathToFileURL(file);
}

export function getBaselineRoot() {
  for (const file of inventory.files) baselineUrl(file.file);
  return root;
}
