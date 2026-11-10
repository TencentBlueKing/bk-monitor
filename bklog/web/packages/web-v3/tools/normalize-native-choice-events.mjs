/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import fs from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
const root=fileURLToPath(new URL('../',import.meta.url));
const walk=p=>fs.readdirSync(p,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(p+'/'+e.name):[p+'/'+e.name]);
let count=0;
for(const f of walk(resolve(root,'src')).filter(f=>f.endsWith('.tsx')&&!f.includes('/platform/compat/'))){
 let source=fs.readFileSync(f,'utf8');
 const ast=ts.createSourceFile(f,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),native=new Set(),functions=new Map(),edits=[];
 for(const n of ast.statements)if(ts.isImportDeclaration(n)&&n.moduleSpecifier.text==='tdesign-vue-next')for(const e of n.importClause?.namedBindings?.elements||[])if(['Switch','RadioGroup','CheckboxGroup'].includes((e.propertyName||e.name).text))native.add(e.name.text);
 const find=n=>{if(ts.isFunctionDeclaration(n)&&n.name)functions.set(n.name.text,n);if(ts.isMethodDeclaration(n)&&n.name)functions.set('this.'+n.name.getText(ast),n);if(ts.isVariableDeclaration(n)&&n.initializer&&(ts.isArrowFunction(n.initializer)||ts.isFunctionExpression(n.initializer)))functions.set(n.name.getText(ast),n.initializer);ts.forEachChild(n,find);};find(ast);
 const visit=n=>{
  if((ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n))&&native.has(n.tagName.getText(ast)))for(const p of n.attributes.properties){
   if(!ts.isJsxAttribute(p)||!p.initializer||!ts.isJsxExpression(p.initializer)||!p.initializer.expression)continue;
   const expr=p.initializer.expression;
   if(p.name.text==='beforeChange'&&expr.getText(ast).includes('(() => false)')){edits.push({start:expr.getStart(ast),end:expr.end,text:'() => false'});continue;}
   if(p.name.text!=='onChange')continue;
   const fn=ts.isArrowFunction(expr)||ts.isFunctionExpression(expr)?expr:functions.get(expr.getText(ast));
   const type=fn?.parameters[0]?.type?.getText(ast).replace(/\s/g,'');let guard;
   if(type==='boolean'||type==='boolean|undefined')guard="typeof value === 'boolean'";
   else if(type==='string')guard="typeof value === 'string'";
   else if(type==='number')guard="typeof value === 'number'";
   else if(type==='string[]')guard="value.every(item => typeof item === 'string')";
   if(guard)edits.push({start:expr.getStart(ast),end:expr.end,text:`(value) => { if (${guard}) (${expr.getText(ast)})(value); }`});
  }
  ts.forEachChild(n,visit);
 };visit(ast);
 for(const e of edits.sort((a,b)=>b.start-a.start))source=source.slice(0,e.start)+e.text+source.slice(e.end);
 if(edits.length){fs.writeFileSync(f,source);count+=edits.length;}
}
console.log({nativeEventsNarrowed:count});
