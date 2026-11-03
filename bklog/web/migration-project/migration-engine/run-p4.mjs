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

import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(here, '..');
const webV3 = resolve(projectRoot, '../packages/web-v3');
const result = spawnSync(process.execPath, ['--test', 'src/pilot/pilot-behavior.test.mjs'], {
  cwd: webV3,
  stdio: 'inherit',
});
const task = {
  id: 'P4-MODULE-001',
  tapdId: '1010158081139460519',
  phase: 'P4',
  title: '迁移采集步骤中已核对的标签选择和应用类型状态',
  status: result.status === 0 ? 'NEEDS_REVIEW' : 'FAILED',
  source: [
    'src/components/collection-access/components/step-add/label-target-dialog.vue',
    'src/components/collection-access/components/step-add/container-target-item.vue',
  ],
  behaviorMatrix: 'migration-project/migration-plan/03-business-behavior-matrix.md',
  uiBaseline: 'migration-project/migration-plan/05-ui-baseline.md',
  command: 'node --test src/pilot/pilot-behavior.test.mjs',
  exitCode: result.status,
  blocked: ['R-001 登录后截图', 'E2E', '整页采集向导'],
};
mkdirSync(resolve(projectRoot, 'artifacts/tasks'), { recursive: true });
writeFileSync(resolve(projectRoot, 'artifacts/tasks/p4.json'), `${JSON.stringify(task, null, 2)}\n`);
if (result.status !== 0) process.exitCode = 1;
