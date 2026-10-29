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

import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
export function retirementFailures(status, frozen, evidenceExists) {
  const failures = [];
  for (let index = 0; index < 8; index++) {
    const id = `M${index}`;
    const milestone = status.milestones?.find(item => item.id === id);
    if (!milestone || !(index === 7 ? ['VERIFYING', 'ACCEPTED'].includes(milestone.status) : milestone.status === 'ACCEPTED') || !milestone.businessAccepted || !milestone.visualAccepted) failures.push(`${id}: not accepted`);
    if (!milestone?.evidence?.length || !milestone.evidence.every(evidenceExists)) failures.push(`${id}: missing evidence`);
  }
  if (!frozen.hostReady) failures.push('Frozen V1 host is not accepted');
  if (!frozen.files?.length) failures.push('Frozen V1 file manifest is missing');
  return failures;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const status = JSON.parse(readFileSync(resolve(root, 'migration-project/artifacts/tasks/execution-status.json'), 'utf8'));
  const frozen = JSON.parse(readFileSync(resolve(root, 'packages/web-v3/public/legacy-v1/sealed-manifest.json'), 'utf8'));
  const failures = retirementFailures(status, frozen, file => {
    const path = resolve(root, file);
    return path.startsWith(root + '/') && existsSync(path);
  });
  failures.forEach(failure => console.error(failure));
  process.exitCode = failures.length ? 1 : 0;
}
