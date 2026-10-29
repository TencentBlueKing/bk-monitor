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

import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve, relative } from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const web=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const root=resolve(web,'packages/web-v3/src-native');
const require=createRequire(resolve(web,'package.json'));
const {parse}=require('@babel/parser');const {parse:parseVue}=require('@vue/compiler-sfc');
function files(dir){return readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(resolve(dir,e.name)):[resolve(dir,e.name)]);}
function walk(node,callback){if(!node||typeof node!=='object')return;if(node.type)callback(node);for(const[key,value]of Object.entries(node)){if(['loc','comments','tokens'].includes(key))continue;if(Array.isArray(value))value.forEach(v=>walk(v,callback));else if(value&&typeof value==='object')walk(value,callback);}}
const issues=[];
for(const file of files(root).filter(f=>/\.(?:[jt]sx?|mjs|vue)$/.test(f))){
 const source=readFileSync(file,'utf8'),path=relative(web,file);
 const add=(type,line,detail)=>issues.push({file:path,type,line,detail});
 let scripts=[{content:source,loc:{start:{line:1}}}];
 if(file.endsWith('.vue')){
  const {descriptor}=parseVue(source,{filename:file});scripts=[descriptor.script,descriptor.scriptSetup].filter(Boolean);
  const template=descriptor.template;
  if(template){for(const match of template.content.matchAll(/\.sync\b|slot-scope\s*=|\.native\b|<template\s+functional/g))add('vue2-template',template.loc.start.line+template.content.slice(0,match.index).split('\n').length-1,match[0]);}
 }
 for(const script of scripts){try{
  const ast=parse(script.content,{sourceType:'unambiguous',plugins:[['typescript',{dts:file.endsWith('.d.ts')}],'jsx','decorators-legacy']});
  walk(ast,node=>{
   const line=script.loc.start.line+node.loc.start.line-1;
   if(node.type==='ImportDeclaration'){
    const name=node.source.value;
    if(name==='vue'&&node.specifiers.some(s=>s.type==='ImportDefaultSpecifier'))add('vue2-default-import',line,name);
    if(/vue-property-decorator|vue-tsx-support|vue-class-component|vue-router\/(?:composables|types)|vue\/types|(?:\/|-)vue2(?:\/|$)|^bk-magic-vue/.test(name))add('dependency-needs-migration',line,name);
   }
   if(node.type==='ObjectMethod'&&['beforeDestroy','destroyed'].includes(node.key.name))add('vue2-lifecycle',line,node.key.name);
   if(path !== 'packages/web-v3/src-native/common/bus.js' && node.type==='CallExpression'&&node.callee.type==='MemberExpression'&&['$on','$off','$once','$set','$delete','$destroy','$mount'].includes(node.callee.property.name))add('removed-instance-api',line,node.callee.property.name);
  });
 }catch(error){add('parse-error',script.loc.start.line,error.message);}}
}
const report={schemaVersion:1,sourceRoot:'packages/web-v3/src-native',accepted:false,uiVerificationStarted:false,issues,
 limitations:['Static compatibility scan only; absence of these markers does not prove a module is migrated','Runtime component events, plugins, Vuex actions, JSX, directives, styles and external integrations still require build and behavioral validation']};
writeFileSync(resolve(web,'migration-project/artifacts/inventory/native-blockers.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({issues:issues.length,files:new Set(issues.map(i=>i.file)).size,parseErrors:issues.filter(i=>i.type==='parse-error').length}));
process.exitCode=issues.length?1:0;
