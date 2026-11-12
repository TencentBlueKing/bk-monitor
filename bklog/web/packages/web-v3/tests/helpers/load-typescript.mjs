/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { nativeFixtureDependencies } from './native-state-fixture.mjs';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';
/** Execute the real TS module under the same Node version used by pnpm/CI. */
export function loadTypeScript(file, dependencies = {}, compilerOptions = {}) {
  dependencies = nativeFixtureDependencies(dependencies);
  const require = createRequire(file);
  // JSX emitted by this Vue3 test compiler must use its own runtime, including when reading V2 source.
  const compilerRequire = createRequire(new URL('../../package.json', import.meta.url));
  const source = readFileSync(file, 'utf8');
  const { outputText, diagnostics } = ts.transpileModule(source, { reportDiagnostics: true, compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, ...compilerOptions,
  } });
  const errors = diagnostics?.filter(item => item.category === ts.DiagnosticCategory.Error) ?? [];
  if (errors.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(errors, { getCanonicalFileName: name => name, getCurrentDirectory: () => process.cwd(), getNewLine: () => '\n' }));
  const exports = {};
  new Function('exports', 'require', outputText)(exports, id => id in dependencies ? dependencies[id] : id === 'vue/jsx-runtime' ? compilerRequire(id) : require(id));
  return exports;
}
