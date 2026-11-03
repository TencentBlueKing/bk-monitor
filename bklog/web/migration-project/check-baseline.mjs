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

import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(readFileSync(resolve(here, 'migration.config.json'), 'utf8'));
const sourceRoot = resolve(here, config.sourceProject);
const targetRoot = resolve(here, config.targetProject);
const packagePath = resolve(sourceRoot, 'package.json');
const required = (config.requiredPaths || []).map(item => resolve(sourceRoot, item));
const missing = required.filter(item => !existsSync(item));

if (!existsSync(targetRoot)) {
  missing.push(targetRoot);
}

const packageJson = existsSync(packagePath) ? JSON.parse(readFileSync(packagePath, 'utf8')) : {};
const dependencies = {
  ...(packageJson.dependencies || {}),
  ...(packageJson.devDependencies || {}),
};
const expectedNode = config.runtime?.sourceNode || '';
const targetPackagePath = resolve(targetRoot, 'package.json');
const workspaceManifest = resolve(sourceRoot, 'pnpm-workspace.yaml');
const targetPackage = existsSync(targetPackagePath) ? JSON.parse(readFileSync(targetPackagePath, 'utf8')) : {};
const targetVue = targetPackage.dependencies?.vue || '';
const workspaceText = existsSync(workspaceManifest) ? readFileSync(workspaceManifest, 'utf8') : '';
if (!workspaceText.includes('packages/web-v3')) missing.push(workspaceManifest);
if (!targetVue.startsWith('3.') && !targetVue.startsWith('^3.') && !targetVue.startsWith('~3.')) {
  missing.push(`${targetPackagePath}#vue`);
}

const report = {
  phase: config.task?.phase || 'P0',
  tapdId: config.task?.tapdId || '',
  node: process.version,
  expectedNode: expectedNode ? `v${expectedNode}` : '',
  nodeMatches: process.version === `v${expectedNode}`,
  sourceRoot,
  targetRoot,
  targetHasPackageJson: existsSync(targetPackagePath),
  targetVue,
  targetVueMajor: targetVue.split('.').find(part => part === '3' || part.endsWith('3')) ? 3 : null,
  workspaceIncludesWebV3: workspaceText.includes('packages/web-v3'),
  targetIsDirectory: existsSync(targetRoot) && statSync(targetRoot).isDirectory(),
  declared: {
    vue: dependencies.vue || null,
    vueRouter: dependencies['vue-router'] || null,
    vuex: dependencies.vuex || null,
    sourceComponentLibrary: dependencies[config.componentLibrary?.source] || null,
    buildCli: dependencies['@blueking/bkmonitor-cli'] || null,
  },
  missing,
};

process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
process.exit(missing.length > 0 ? 1 : 0);
