import { getBaselineRoot } from './source-baseline.mjs';
/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, relative } from 'node:path';
import { spawnSync } from 'node:child_process';
const root = fileURLToPath(new URL('../', import.meta.url));
const temporaryConfig = resolve(root, '.typecheck-baseline.generated.json');
const mapping = new Map(JSON.parse(readFileSync(resolve(root, 'ai-native/source-map.json'))).files.map(file => [file.target, file.source]));
function run(config, target) {
  const result = spawnSync(process.execPath, [resolve(root, 'node_modules/vue-tsc/bin/vue-tsc.js'), '--noEmit', '-p', config],
    { cwd: root, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  if (result.error) throw result.error;
  const counts = new Map();
  const output = `${result.stdout}\n${result.stderr}`;
  for (const match of output.matchAll(/^([^\n(]+)\(\d+,\d+\): error (TS\d+):/gm)) {
    const file = relative(target ? resolve(root, 'src') : getBaselineRoot(), resolve(root, match[1]));
    if (file.startsWith('..')) continue;
    const key = `${target ? mapping.get(file) || file : file}:${match[2]}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  if (result.status !== 0 && !counts.size) throw new Error(`Typecheck did not produce comparable source diagnostics: ${output.slice(0, 800)}`);
  return counts;
}
try {
  writeFileSync(temporaryConfig, JSON.stringify({ extends: './tsconfig.json', compilerOptions: { paths: { '@/*': [getBaselineRoot() + '/*'] } },
    include: ['**/*.ts', '**/*.tsx', '**/*.vue'].map(pattern => resolve(getBaselineRoot(), pattern)), exclude: [] }));
  const baseline = run(temporaryConfig, false), current = run('tsconfig.json', true);
  const added = [...current].filter(([key, count]) => count > (baseline.get(key) || 0)).map(([key, count]) => ({ key, count: count - (baseline.get(key) || 0) }));
  const total = counts => [...counts.values()].reduce((sum, count) => sum + count, 0);
  console.log(JSON.stringify({ status: added.length ? 'FAILED_REGRESSION' : 'PASSED_NO_ADDITIONAL_DIAGNOSTICS',
    baselineErrors: total(baseline), targetErrors: total(current), added,
    limitation: 'Comparison by source-origin file and diagnostic code; existing strict typecheck debt remains failing.' }, null, 2));
  process.exitCode = added.length ? 1 : 0;
} finally { unlinkSync(temporaryConfig); }
