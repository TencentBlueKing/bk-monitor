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

import { createServiceFixture } from './service-fixture.mjs';

import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import * as Vue from 'vue';
const require = createRequire(import.meta.url);
const { parse, compileScript } = require('@vue/compiler-sfc');
const parser = require('@babel/parser');
// Execute the actual script-setup business handlers without rendering controls
// or issuing HTTP requests. Component/render behavior is verified in browser.
export function loadScriptSetup(file, bindings) {
  const dependencies = { ...bindings };
  if (bindings.$http?.request) dependencies.ServicesInstance = createServiceFixture(bindings.$http.request);
  const { descriptor } = parse(readFileSync(file, 'utf8'), { filename: fileURLToPath(file) });
  let code = compileScript(descriptor, { id: 'source-contract' }).content;
  const ast = parser.parse(code, {
    sourceType: 'module',
    plugins: descriptor.scriptSetup?.lang === 'ts' ? ['typescript'] : [],
  });
  const imports = ast.program.body.filter(node => node.type === 'ImportDeclaration');
  for (const declaration of imports)
    for (const specifier of declaration.specifiers) {
      if (declaration.source.value === 'vue' && specifier.type === 'ImportSpecifier')
        dependencies[specifier.local.name] = Vue[specifier.imported.name];
      if (!(specifier.local.name in dependencies)) dependencies[specifier.local.name] = () => null;
    }
  for (const declaration of imports.reverse()) code = code.slice(0, declaration.start) + code.slice(declaration.end);
  code = code.replace('export default', 'return');
  if (descriptor.scriptSetup?.lang === 'ts') {
    const ts = require('typescript');
    code = ts.transpileModule(code, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    }).outputText;
  }
  return new Function(...Object.keys(dependencies), code)(...Object.values(dependencies));
}
