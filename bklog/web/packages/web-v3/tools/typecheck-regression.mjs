/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, relative } from 'node:path';
import { spawnSync } from 'node:child_process';
const root = fileURLToPath(new URL('../', import.meta.url));
const status = JSON.parse(readFileSync(resolve(root, 'ai-native/typecheck-status.json'), 'utf8'));
function run(config) {
  const result = spawnSync(process.execPath, [resolve(root, 'node_modules/vue-tsc/bin/vue-tsc.js'), '--noEmit', '--pretty', 'false', '-p', config],
    { cwd: root, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  if (result.error) throw result.error;
  const byFile = new Map();
  const byCode = new Map();
  let total = 0;
  const output = `${result.stdout}\n${result.stderr}`;
  for (const match of output.matchAll(/^([^\n(]+)\(\d+,\d+\): error (TS\d+):/gm)) {
    const file = relative(root, resolve(root, match[1])).split('\\').join('/');
    if (!file.startsWith('src/')) continue;
    byFile.set(file, (byFile.get(file) || 0) + 1);
    byCode.set(match[2], (byCode.get(match[2]) || 0) + 1);
    total += 1;
  }
  if (result.status !== 0 && !total) throw new Error(`Typecheck did not produce comparable source diagnostics: ${output.slice(0, 800)}`);
  return { byFile, byCode, total };
}
const current = run('tsconfig.json');
const added = [];
const allowedFiles = status.countsByFile || {};
const allowedCodes = status.countsByCode || {};
if (current.total > (status.diagnostics || 0)) added.push({ kind: 'total', count: current.total - status.diagnostics });
for (const [file, count] of current.byFile) {
  const allowed = allowedFiles[file] || 0;
  if (count > allowed) added.push({ file, count: count - allowed });
}
for (const [code, count] of current.byCode) {
  const allowed = allowedCodes[code] || 0;
  if (count > allowed) added.push({ code, count: count - allowed });
}
console.log(JSON.stringify({ status: added.length ? 'FAILED_REGRESSION' : 'PASSED_NO_ADDITIONAL_DIAGNOSTICS',
  baselineErrors: status.diagnostics, targetErrors: current.total, added,
  limitation: 'Comparison against ai-native/typecheck-status.json by file and diagnostic code. Existing strict typecheck debt remains failing. Historical source archive is retired.' }, null, 2));
process.exitCode = added.length ? 1 : 0;
