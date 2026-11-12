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
import {createRequire}from'node:module';
import{readFileSync,readdirSync,existsSync,statSync,writeFileSync}from'node:fs';
import{resolve,relative,dirname,extname}from'node:path';
import{fileURLToPath}from'node:url';
import{createHash}from'node:crypto';
const require=createRequire(new URL('../../packages/web-v3/package.json',import.meta.url));
const ts=require('typescript'),{parse}=require('@vue/compiler-sfc');
const sha=x=>createHash('sha256').update(x).digest('hex');
const walk=root=>readdirSync(root,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(resolve(root,e.name)):[resolve(root,e.name)]).sort();
const literal=n=>n&&(ts.isStringLiteral(n)||ts.isNoSubstitutionTemplateLiteral(n))?n.text:null;
const fn=n=>ts.isArrowFunction(n)||ts.isFunctionExpression(n)||ts.isFunctionDeclaration(n)||ts.isMethodDeclaration(n)||ts.isGetAccessor(n)||ts.isSetAccessor(n);
const key=n=>n&&(ts.isIdentifier(n)||ts.isStringLiteral(n))?n.text:null;
const name=n=>n.name?.getText()??((ts.isVariableDeclaration(n.parent)||ts.isPropertyAssignment(n.parent))?n.parent.name.getText():'<callback>');
export function inspectSources(sourceRoot,{routePrefixes=['router/']}={}){
 const graph={schemaVersion:1,scope:'SOURCE_CANDIDATES_NOT_RUNTIME_COVERAGE',files:[],dependencies:[],routes:[],functions:[],eventBindings:[],effects:[],branches:[],templates:[],endpoints:[],unresolved:[],diagnostics:[]};
 function resolveDependency(specifier,filename){
  if(!specifier.startsWith('.')&&!specifier.startsWith('@/'))return{kind:'external',specifier};
  const base=specifier.startsWith('@/')?resolve(sourceRoot,specifier.slice(2)):resolve(dirname(filename),specifier);
  const choices=[base,...['.ts','.tsx','.js','.jsx','.vue','.mjs','.json','.scss','.css'].map(x=>base+x),...['index.ts','index.tsx','index.js','index.vue'].map(x=>resolve(base,x))];
  for(const p of choices)if(existsSync(p)&&statSync(p).isFile())return{kind:'local',target:relative(sourceRoot,p)};
  return{kind:'unresolved-local',specifier};
 }
 for(const filename of walk(sourceRoot).filter(p=>/\.(?:vue|[cm]?[jt]sx?)$/.test(p)&&!p.endsWith('.d.ts'))){
  const file=relative(sourceRoot,filename),text=readFileSync(filename,'utf8'),hash=sha(text);
  graph.files.push({file,sha256:hash,bytes:Buffer.byteLength(text)});
  const position=(start,end,expression)=>({file,sha256:hash,start,end,line:text.slice(0,start).split('\n').length,expression});
  const sections=[];
  if(filename.endsWith('.vue')){
   const{descriptor,errors}=parse(text,{filename});
   for(const error of errors){
    const message=typeof error==='string'?error:error.message;
    const legacyFunctional=message.startsWith('<template functional> is no longer supported');
    graph.diagnostics.push({file,phase:'sfc',message,classification:legacyFunctional?'SUPPORTED_VUE2_FUNCTIONAL_SYNTAX':'PARSE_ERROR',templateAstAvailable:Boolean(descriptor.template?.ast)});
   }
   for(const script of[descriptor.script,descriptor.scriptSetup].filter(Boolean))sections.push({content:script.content,offset:script.loc.start.offset,lang:script.lang??'js'});
   const template=descriptor.template;
   function templateVisit(node,guards=[]){
    let local=guards;
    if(node.type===1){
     for(const p of node.props??[])if(p.type===7&&['if','else-if','else','show'].includes(p.name)){
      const id=`${file}:template:${p.loc.start.offset}`;graph.branches.push({id,kind:`v-${p.name}`,predicate:p.exp?.content??'',...position(p.loc.start.offset,p.loc.end.offset,p.loc.source),state:'UNREVIEWED'});local=[...local,id];
     }
     for(const p of node.props??[])if(p.type===7){
      const expr=p.exp?.content??'',arg=p.arg?.content??'',loc=position(p.loc.start.offset,p.loc.end.offset,p.loc.source);
      if(p.name==='on'||p.name==='model')graph.eventBindings.push({id:`${file}:event:${p.loc.start.offset}`,owner:node.tag,event:p.name==='model'?`model:${arg||'default'}`:arg,handler:expr,guards:local,syntax:'template',...loc,state:'UNREVIEWED'});
      if(p.name==='bind'&&arg==='is')graph.unresolved.push({kind:'dynamic-component',...loc,state:'UNREVIEWED'});
     }
     graph.templates.push({tag:node.tag,guards:local,...position(node.loc.start.offset,node.loc.end.offset,node.loc.source)});
    }
    for(const child of node.children??[])templateVisit(child,local);
   }
   if(template?.ast)templateVisit(template.ast);else if(template)graph.unresolved.push({file,kind:'template-ast-unavailable',state:'UNREVIEWED'});
  }else sections.push({content:text,offset:0,lang:extname(filename).slice(1)});
  for(const section of sections){
   const sf=ts.createSourceFile(filename,section.content,ts.ScriptTarget.Latest,true,['ts','mts'].includes(section.lang)?ts.ScriptKind.TS:ts.ScriptKind.TSX);
   const loc=n=>position(section.offset+n.getStart(sf),section.offset+n.end,n.getText(sf));
   const functions=new Map(),routeObjects=new Map(),imports=new Map();
   const props=n=>new Map(n.properties.filter(ts.isPropertyAssignment).map(p=>[key(p.name),p.initializer]));
   function collect(n){
    if(fn(n)){const id=`${file}:fn:${section.offset+n.getStart(sf)}`;functions.set(n,id);graph.functions.push({id,name:name(n),...loc(n),expression:n.getText(sf).slice(0,280),state:'UNREVIEWED'});}
    if(ts.isImportDeclaration(n)&&literal(n.moduleSpecifier)){
     const specifier=literal(n.moduleSpecifier),resolved=resolveDependency(specifier,filename),bindings=[n.importClause?.name?.text,...(n.importClause?.namedBindings&&ts.isNamedImports(n.importClause.namedBindings)?n.importClause.namedBindings.elements.map(e=>e.name.text):[])].filter(Boolean);
     bindings.forEach(b=>imports.set(b,resolved));graph.dependencies.push({syntax:'import',specifier,bindings,typeOnly:n.importClause?.isTypeOnly??false,...resolved,...loc(n)});
    }
    if(ts.isObjectLiteralExpression(n)){
     const p=props(n);
     if(routePrefixes.some(prefix=>file.startsWith(prefix))&&p.has('path')&&['component','components','redirect','children','name'].some(k=>p.has(k))){const id=`${file}:route:${section.offset+n.getStart(sf)}`;routeObjects.set(n,id);graph.routes.push({id,localPath:literal(p.get('path')),pathExpression:p.get('path').getText(sf),name:literal(p.get('name')),component:p.get('component')?.getText(sf)??null,redirect:p.get('redirect')?.getText(sf)??null,meta:p.get('meta')?.getText(sf)??null,...loc(n),expression:undefined,state:'UNREVIEWED'});}
     if(file.startsWith('services/')&&p.has('url'))graph.endpoints.push({id:`${file}:endpoint:${section.offset+n.getStart(sf)}`,name:n.parent?.name?.getText(sf)??null,url:literal(p.get('url')),method:literal(p.get('method'))??'GET_DEFAULT_REQUIRES_REVIEW',...loc(n),expression:undefined,semantics:'UNCLASSIFIED'});
    }
    ts.forEachChild(n,collect);
   }
   collect(sf);
   const owner=n=>{for(let p=n.parent;p;p=p.parent)if(functions.has(p))return functions.get(p);return null;};
   const guards=n=>{const out=[];for(let p=n.parent;p;p=p.parent)if(ts.isIfStatement(p)||ts.isConditionalExpression(p)||ts.isSwitchStatement(p))out.push(`${file}:branch:${section.offset+p.getStart(sf)}`);return out;};
   for(const[n,id]of routeObjects){let p=n.parent;while(p&&!routeObjects.has(p))p=p.parent;graph.routes.find(r=>r.id===id).parentId=p?routeObjects.get(p):null;}
   function visit(n){
    if(ts.isIfStatement(n)||ts.isConditionalExpression(n)||ts.isSwitchStatement(n)||ts.isCaseClause(n)||ts.isDefaultClause(n)||ts.isBinaryExpression(n)&&[ts.SyntaxKind.AmpersandAmpersandToken,ts.SyntaxKind.BarBarToken,ts.SyntaxKind.QuestionQuestionToken].includes(n.operatorToken.kind))graph.branches.push({id:`${file}:branch:${section.offset+n.getStart(sf)}`,kind:ts.SyntaxKind[n.kind],predicate:(n.expression??(ts.isBinaryExpression(n)?n.left:n)).getText(sf).slice(0,600),owner:owner(n),...loc(n),expression:undefined,state:'UNREVIEWED'});
    if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n)){
     const tag=n.tagName.getText(sf);for(const a of n.attributes.properties)if(ts.isJsxAttribute(a)&&/^on(?:[A-Z-]|:)/.test(a.name.getText(sf)))graph.eventBindings.push({id:`${file}:event:${section.offset+a.getStart(sf)}`,owner:tag,event:a.name.getText(sf),handler:a.initializer?.getText(sf)??'',functionId:owner(n),guards:guards(n),syntax:'jsx',...loc(a),state:'UNREVIEWED'});
     if(imports.has(tag))graph.dependencies.push({syntax:'jsx-component',owner:tag,...loc(n),...imports.get(tag)});
    }
    if(ts.isCallExpression(n)){
     const callee=n.expression.getText(sf),specifier=literal(n.arguments[0]);
     if(n.expression.kind===ts.SyntaxKind.ImportKeyword||callee==='require'){if(specifier)graph.dependencies.push({syntax:'dynamic-import',specifier,...loc(n),...resolveDependency(specifier,filename)});else graph.unresolved.push({kind:'dynamic-import',...loc(n),state:'UNREVIEWED'});}
     if(/(?:require\.context|import\.meta\.glob|resolveComponent|\.component)$/.test(callee))graph.unresolved.push({kind:'dynamic-registration',...loc(n),state:'UNREVIEWED'});
     if(/(?:\.(?:request|dispatch|commit|fire|emit|push|replace|setItem|removeItem|addEventListener|removeEventListener)|^(?:fetch|fetchEventSource))$/.test(callee))graph.effects.push({id:`${file}:effect:${section.offset+n.getStart(sf)}`,callee,argument:specifier,argsPreview:n.arguments.map(a=>a.getText(sf).slice(0,1200)),functionId:owner(n),guards:guards(n),...loc(n),expression:undefined,state:'UNREVIEWED'});
    }
    ts.forEachChild(n,visit);
   }
   visit(sf);for(const d of sf.parseDiagnostics)graph.diagnostics.push({file,phase:'typescript',offset:section.offset+(d.start??0),message:ts.flattenDiagnosticMessageText(d.messageText,' ')});
  }
  for(const m of text.matchAll(/^\s*\/\/\s*#(if|else|endif|code)\b(.*)$/gm))graph.unresolved.push({kind:'build-directive',directive:m[1],condition:m[2].trim(),...position(m.index,m.index+m[0].length,m[0]),state:'UNREVIEWED'});
 }
 const routes=new Map(graph.routes.map(r=>[r.id,r]));function full(r,seen=new Set()){if(seen.has(r.id)||r.localPath===null)return null;seen.add(r.id);if(r.localPath.startsWith('/'))return r.localPath;const parent=routes.get(r.parentId);if(!parent)return r.localPath;const base=full(parent,seen);return base===null?null:`${base.replace(/\/$/,'')}/${r.localPath}`;}
 graph.routes.forEach(r=>{r.path=full(r);});graph.sourceDigest=sha(JSON.stringify(graph.files));graph.summary=Object.fromEntries(['files','routes','functions','eventBindings','effects','branches','endpoints','unresolved','diagnostics'].map(k=>[k,graph[k].length]));return graph;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const graph=inspectSources(fileURLToPath(new URL('../../packages/web-v2/src',import.meta.url))),out=fileURLToPath(new URL('../source/',import.meta.url));
 const{routes,eventBindings,branches,unresolved,endpoints,...rest}=graph;for(const[name,data]of Object.entries({'entry-graph':rest,routes,'capability-candidates':eventBindings,'branch-obligations':branches,unresolved,'endpoint-candidates':endpoints}))writeFileSync(resolve(out,name+'.json'),JSON.stringify(data,null,2)+'\n');console.log(JSON.stringify(graph.summary));
}
