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
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { extractContract } from './extract-contract.mjs';
import { comparePng, writeVisualReport } from './visual-diff.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(here, '..');
const webRoot = resolve(projectRoot, '..');
const webV3 = resolve(webRoot, 'packages/web-v3');
const require = createRequire(resolve(webV3, 'package.json'));
const { PNG } = require('pngjs');

function writeJson(filePath, value) {
  mkdirSync(dirname(filePath), { recursive: true });
  writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

function solidPng(rgba) {
  const png = new PNG({ width: 2, height: 2 });
  for (let index = 0; index < png.data.length; index += 4) {
    png.data[index] = rgba[0];
    png.data[index + 1] = rgba[1];
    png.data[index + 2] = rgba[2];
    png.data[index + 3] = 255;
  }
  return PNG.sync.write(png);
}

const labelSource = resolve(webRoot, 'src/components/collection-access/components/step-add/label-target-dialog.vue');
const selectSource = resolve(webRoot, 'src/components/collection-access/components/step-add/container-target-item.vue');
const labelContract = extractContract(labelSource, 'label-target-dialog');
labelContract.source = relative(webRoot, labelSource);
labelContract.invariants = [
  'isHaveSelectItem 为 false 时确定按钮 disabled',
  '搜索框 @change 调用 search，search 再调用 labelTreeRef.filter(filterStr)',
  'right-icon 保持未映射，不写成 suffixIcon',
];
const selectContract = extractContract(selectSource, 'container-target-item');
selectContract.source = relative(webRoot, selectSource);
selectContract.invariants = [
  'searchable 映射为 filterable，allow-create 映射为 creatable',
  'bk-option 的 :id/:name 映射为 value/label',
  '@toggle 只转发 boolean，不转发 TDesign context',
];
writeJson(resolve(projectRoot, 'artifacts/contracts/label-target-dialog.json'), labelContract);
writeJson(resolve(projectRoot, 'artifacts/contracts/container-target-item.json'), selectContract);

const visualDir = resolve(projectRoot, 'artifacts/visual/p3');
mkdirSync(visualDir, { recursive: true });
writeFileSync(resolve(visualDir, 'primary.png'), solidPng([58, 132, 255]));
writeFileSync(resolve(visualDir, 'primary-copy.png'), solidPng([58, 132, 255]));
writeFileSync(resolve(visualDir, 'blank.png'), solidPng([255, 255, 255]));
const visualReport = {
  note: 'P3 只验证比较器能保存报告。登录后页面截图仍受 R-001 阻塞，这两张纯色图不是 UI 基线。',
  same: comparePng(resolve(visualDir, 'primary.png'), resolve(visualDir, 'primary-copy.png')),
  diff: comparePng(resolve(visualDir, 'primary.png'), resolve(visualDir, 'blank.png')),
};
writeVisualReport(visualReport, resolve(visualDir, 'report.json'));

const adapter = spawnSync(process.execPath, [
  '--test',
  'src/vue-runtime.test.mjs',
  'src/adapters/bk-magic/adapter-contract.test.mjs',
], { cwd: webV3, stdio: 'inherit' });
const visual = spawnSync(process.execPath, ['--test', 'migration-engine/visual-diff.test.mjs'], {
  cwd: projectRoot,
  stdio: 'inherit',
});
const legacy = spawnSync(process.execPath, ['migration-project/analyze-legacy.mjs'], {
  cwd: webRoot,
  stdio: 'inherit',
});

const tdesignVersion = JSON.parse(readFileSync(require.resolve('tdesign-vue-next/package.json'), 'utf8')).version;
const task = {
  tapdId: '1010158081139460519',
  phase: 'P3',
  source: [
    'src/components/collection-access/components/step-add/label-target-dialog.vue',
    'src/components/collection-access/components/step-add/container-target-item.vue',
  ],
  contracts: [
    'migration-project/artifacts/contracts/label-target-dialog.json',
    'migration-project/artifacts/contracts/container-target-item.json',
  ],
  visualReport: 'migration-project/artifacts/visual/p3/report.json',
  tdesignVersion,
  commands: {
    adapter: adapter.status,
    visual: visual.status,
    legacy: legacy.status,
  },
  gaps: ['right-icon', 'bk-select @toggle context', 'bk-dialog', 'bk-big-tree', 'bk-checkbox'],
};
writeJson(resolve(projectRoot, 'artifacts/tasks/p3.json'), task);
if (adapter.status !== 0 || visual.status !== 0 || legacy.status !== 0 || visualReport.same.status !== 'identical') {
  process.exitCode = 1;
}
