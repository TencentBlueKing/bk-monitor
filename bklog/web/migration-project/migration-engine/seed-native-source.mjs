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

import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, readdirSync, mkdirSync, existsSync, cpSync } from 'node:fs';
import { resolve, dirname, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
const web = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(resolve(web, 'packages/web-v2/package.json'));
const { parse } = require('@babel/parser');
const { parse: parseVue } = require('@vue/compiler-sfc');
const replacements = new Map([
 ['vue-router/composables', 'vue-router'],
 ['@blueking/date-picker/vue2', '@blueking/date-picker'],
 ['@blueking/date-picker/vue2/vue2.css', '@blueking/date-picker/vue3/vue3.css'],
]);
function visit(node, callback) {
 if (!node || typeof node !== 'object') return;
 if (node.type) callback(node);
 for (const [key, value] of Object.entries(node)) {
  if (['loc', 'comments', 'tokens'].includes(key)) continue;
  if (Array.isArray(value)) value.forEach(item => visit(item, callback));
  else if (value && typeof value === 'object') visit(value, callback);
 }
}
export function upgradeImports(source, filename) {
 const edits = [];
 const scripts = extname(filename) === '.vue' ? (() => {
  const { descriptor } = parseVue(source, { filename });
  return [descriptor.script, descriptor.scriptSetup].filter(Boolean).map(script => ({text:script.content, offset:script.loc.start.offset}));
 })() : [{text:source,offset:0}];
 for (const script of scripts) {
  const ast = parse(script.text, {sourceType:'unambiguous', plugins:[['typescript',{dts:filename.endsWith('.d.ts')}], 'jsx', 'decorators-legacy']});
  visit(ast, node => {
   const literal = ['ImportDeclaration','ExportNamedDeclaration','ExportAllDeclaration'].includes(node.type) ? node.source :
    node.type === 'CallExpression' && (node.callee.type === 'Import' || node.callee.name === 'require') ? node.arguments[0] : null;
   if (literal?.type === 'StringLiteral' && replacements.has(literal.value)) edits.push({start:script.offset+literal.start, end:script.offset+literal.end, value:JSON.stringify(replacements.get(literal.value)), from:literal.value, to:replacements.get(literal.value)});
  });
 }
 let output = source;
 for (const edit of edits.sort((a,b)=>b.start-a.start)) output = output.slice(0,edit.start)+edit.value+output.slice(edit.end);
 return {code:output, changes:edits.map(({from,to})=>({from,to}))};
}
function list(dir) {
 return readdirSync(dir,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name)).flatMap(entry=>{
  if (entry.isSymbolicLink()) throw new Error('Source symlinks require manual review');
  const path=resolve(dir,entry.name);return entry.isDirectory()?list(path):[path];
 });
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
 const sourceRoot=resolve(web,'src'), targetRoot=resolve(web,'packages/web-v3/src-native');
 if (existsSync(targetRoot)) throw new Error('Native source already exists; do not overwrite ongoing manual migration');
 const report=[];
 for(const source of list(sourceRoot)) {
  const path=relative(sourceRoot,source),target=resolve(targetRoot,path), bytes=readFileSync(source);
  mkdirSync(dirname(target),{recursive:true});
  let code=bytes, changes=[], error=null;
  if (/\.(?:[jt]sx?|mjs|vue)$/.test(source)) {
   try { const result=upgradeImports(bytes.toString('utf8'),source); code=Buffer.from(result.code);changes=result.changes; }
   catch(err) { error=err.message; }
  }
  writeFileSync(target,code);
  report.push({source:`src/${path}`,target:`packages/web-v3/src-native/${path}`,sourceSha256:createHash('sha256').update(bytes).digest('hex'),changes,error,status:changes.length?'IMPORTS_UPDATED_NOT_ACCEPTED':'SOURCE_COPIED_NOT_MIGRATED'});
 }
 const output=resolve(web,'migration-project/artifacts/inventory/native-source.json');
 mkdirSync(dirname(output),{recursive:true});
 writeFileSync(output,JSON.stringify({schemaVersion:1,strategy:'source-first-native-vue3',businessBaseline:'src',previousPrototypeUsed:false,uiVerificationStarted:false,files:report},null,2)+'\n');
 console.log(JSON.stringify({files:report.length,importsUpdated:report.filter(file=>file.changes.length).length,parseErrors:report.filter(file=>file.error).length}));
}
