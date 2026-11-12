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

import fs from'node:fs';import {fileURLToPath} from 'node:url';import{createRequire}from'node:module';const root=fileURLToPath(new URL('../../../packages/web-v3/',import.meta.url));const{parse}=createRequire(root+'package.json')('@babel/parser');const ast=p=>parse(fs.readFileSync(p,'utf8'),{sourceType:'module'});const before=ast(new URL('./application-state-operations.before.txt',import.meta.url)).program.body.find(n=>n.type==='ExportDefaultDeclaration')?.declaration;const prev=ast(new URL('./application-state-operations.before.txt',import.meta.url)).program.body;const dict=before?.type==='ObjectExpression'?before:prev.find(n=>n.type==='VariableDeclaration'&&n.declarations[0].id.name==='mutations')?.declarations[0].init;
if(!dict)throw Error('Missing original mutations');const current=ast(root+'src/app/state/mutations/index.js').program.body.filter(n=>n.type==='ExportNamedDeclaration'&&n.declaration?.type==='FunctionDeclaration').map(n=>n.declaration);const clean=value=>Array.isArray(value)?value.map(clean):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).filter(([key])=>!['start','end','loc','extra','leadingComments','trailingComments','innerComments'].includes(key)).map(([key,v])=>[key,clean(v)])):value;const rows=dict.properties.map(method=>{const name=method.computed?'applyApplicationState':method.key.name;const next=current.find(n=>n.id.name===name);return{name,bodyUnchanged:JSON.stringify(clean(method.body))===JSON.stringify(clean(next?.body)),parametersUnchanged:JSON.stringify(clean(method.params))===JSON.stringify(clean(next?.params))};});console.log(JSON.stringify({compared:rows.length,unchanged:rows.filter(r=>r.bodyUnchanged&&r.parametersUnchanged).length,methods:rows},null,2));if(rows.some(r=>!r.bodyUnchanged||!r.parametersUnchanged))process.exitCode=1;
