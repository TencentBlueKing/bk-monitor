/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import fs from 'node:fs';
import {resolve,relative,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {parse} from '@vue/compiler-sfc';
import ts from 'typescript';
const root=fileURLToPath(new URL('../',import.meta.url));
const allowed=new Set(['value','modelValue','disabled','readonly','size','placeholder','maxlength','name','type','class','style','ext-cls','extCls','ref','key','clearable','left-icon','leftIcon','right-icon','rightIcon','show-word-limit','showWordLimit','data-test-id']);
// Numeric/textarea/emoji filtering, clear button visibility and grouped slots
// have separate V2 contracts. Never silently discard unsupported behavior.
export function migrateTextInputs(source,filename){
 const descriptor=filename.endsWith('.vue')?parse(source).descriptor:null;
 const edits=[],skipped=[],handlerArities=new Map();let count=0;const put=(start,end,text)=>edits.push({start,end,text});
 const blocks=descriptor?[descriptor.script,descriptor.scriptSetup].filter(Boolean).map(s=>({text:s.content,offset:s.loc.start.offset})):[{text:source,offset:0}];
 for(const block of blocks){const ast=ts.createSourceFile(filename,block.text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);const collect=n=>{if((ts.isMethodDeclaration(n)||ts.isFunctionDeclaration(n))&&n.name)handlerArities.set(n.name.getText(ast),n.parameters.length);if(ts.isVariableDeclaration(n)&&n.initializer&&ts.isArrowFunction(n.initializer))handlerArities.set(n.name.getText(ast),n.initializer.parameters.length);ts.forEachChild(n,collect);};collect(ast);}
 for(const block of blocks){
  const ast=ts.createSourceFile(filename,block.text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),aliases=new Set(),native=new Set();
  for(const n of ast.statements)if(ts.isImportDeclaration(n)&&/compat\/tdesign\/magic-controls/.test(n.moduleSpecifier.text))for(const e of n.importClause?.namedBindings?.elements||[])if((e.propertyName||e.name).text==='bkInput')aliases.add(e.name.text);
  const start=n=>block.offset+n.getStart(ast),end=n=>block.offset+n.end;
  const val=p=>!p.initializer?'true':ts.isJsxExpression(p.initializer)?p.initializer.expression?.getText(ast)||'true':p.initializer.getText(ast);
  const visit=n=>{
   if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n)){
    const tag=n.tagName.getText(ast);
    if(tag==='bk-input'||aliases.has(tag)){
     const props=n.attributes.properties,attrs=props.filter(ts.isJsxAttribute),get=k=>attrs.find(p=>p.name.getText(ast)===k);
     const reasons=[];
     if(props.some(ts.isJsxSpreadAttribute))reasons.push('spread attributes');
     for(const p of attrs){const k=p.name.getText(ast);if(!allowed.has(k)&&!['v-model','onChange','onEnter','onBlur','onFocus'].includes(k)&&!k.startsWith('v-bk')&&!k.startsWith('data-'))reasons.push(k);}
     const type=get('type');if(type&&!/^['"](?:text|password|url|search)['"]$/.test(val(type)))reasons.push('non-text type');
     if(get('clearable')&&val(get('clearable'))!=='false')reasons.push('V2 always-visible clear action');
     if(ts.isJsxElement(n.parent)&&n.parent.children.some(c=>!ts.isJsxText(c)||c.text.trim()))reasons.push('grouped slots');
     if(reasons.length)skipped.push({line:source.slice(0,start(n)).split('\n').length,reasons});
     else{
      count++;native.add('Input as TInput');put(start(n.tagName),end(n.tagName),'TInput');
      if(ts.isJsxElement(n.parent))put(start(n.parent.closingElement.tagName),end(n.parent.closingElement.tagName),'TInput');
      for(const p of attrs){const k=p.name.getText(ast),v=val(p),rewrite=(name,value=v)=>put(start(p),end(p),`${name}={${value}}`);
       if(['onChange','onBlur','onFocus','onEnter'].includes(k)){const fn=p.initializer&&ts.isJsxExpression(p.initializer)?p.initializer.expression:null;if(fn&&ts.isArrowFunction(fn)&&fn.parameters.length===1&&fn.parameters[0].type?.kind===ts.SyntaxKind.StringKeyword)rewrite(k,`value => (${v})(String(value))`);}
       if(['left-icon','leftIcon'].includes(k))rewrite('prefixIcon',`() => <i class={${v}} />`);
       if(['right-icon','rightIcon'].includes(k))rewrite('suffix',`() => <i class={${v}} />`);
       if(['show-word-limit','showWordLimit'].includes(k))rewrite('showLimitNumber');
       if(['ext-cls','extCls'].includes(k)){const cls=get('class');if(cls){put(start(cls.initializer),end(cls.initializer),`{[${val(cls)}, ${v}]}`);put(start(p),end(p),'');}else rewrite('class');}
      }
     }
    }
   }
   ts.forEachChild(n,visit);
  };visit(ast);
  if(native.size)put(block.offset,block.offset,`\nimport { ${[...native].join(', ')} } from 'tdesign-vue-next';\n`);
 }
 if(descriptor?.template?.ast){
  const visit=n=>{
   if(n.type===1&&n.tag==='bk-input'){
    const name=p=>p.type===6?p.name:p.arg?.content,value=p=>p.type===6?p.value?JSON.stringify(p.value.content):'true':p.exp?.content||'true',get=k=>n.props.find(p=>name(p)===k),reasons=[];
    for(const p of n.props){const k=name(p);if(p.type===7&&['model','if','else','else-if','for','show'].includes(p.name))continue;if(p.type===7&&p.name.startsWith('bk'))continue;if(p.type===7&&p.name==='on'){if(!['change','enter','blur','focus','input'].includes(k))reasons.push('event:'+k);continue;}if(!allowed.has(k)&&!k?.startsWith('data-'))reasons.push(k||'spread attributes');}
    if(get('type')&&!/^['"](?:text|password|url|search)['"]$/.test(value(get('type'))))reasons.push('non-text type');
    if(get('clearable')&&value(get('clearable'))!=='false')reasons.push('V2 always-visible clear action');
    if(n.children.some(c=>c.type!==3&&(c.type!==2||c.content.trim())))reasons.push('grouped slots');
    if(n.props.filter(p=>p.type===7&&p.name==='on'&&['input','change'].includes(name(p))).length>1)reasons.push('paired input/change');
    if(reasons.length)skipped.push({line:n.loc.start.line,reasons});
    else{
     count++;const start=n.loc.start.offset,close=n.loc.source.lastIndexOf('</bk-input'),slots=[];
     put(start+1,start+9,'t-input');if(close>=0)put(start+close+2,start+close+10,'t-input');
     for(const p of n.props){const k=name(p),v=value(p),rewrite=(key,exp=v)=>put(p.loc.start.offset,p.loc.end.offset,`:${key}="${exp.replaceAll('"',"'")}"`);
      if(['left-icon','right-icon'].includes(k)){slots.push(`<template #${k==='left-icon'?'prefixIcon':'suffix'}><i :class="${v.replaceAll('"',"'")}" /></template>`);put(p.loc.start.offset,p.loc.end.offset,'');}
      if(k==='show-word-limit')rewrite('show-limit-number');
      if(p.type===7&&p.name==='on'&&handlerArities.get(p.exp?.content)>1)put(p.loc.start.offset,p.loc.end.offset,`@${k==='input'?'change':k}="(value, {e}) => ${p.exp.content}(value, e)"`);
      else if(p.type===7&&p.name==='on'&&k==='input')put(p.arg.loc.start.offset,p.arg.loc.end.offset,'change');
      if(k==='ext-cls'){const cls=get('class');if(cls){rewrite('class',`[${value(cls)}, ${v}]`);put(p.loc.start.offset,p.loc.end.offset,'');}else rewrite('class');}
     }
     if(slots.length){if(n.isSelfClosing)put(n.loc.end.offset-2,n.loc.end.offset,`>${slots.join('')}</t-input>`);else put(start+close,start+close,slots.join(''));}
    }
   }
   for(const c of n.children||[])visit(c);
  };visit(descriptor.template.ast);
 }
 let output=source;for(const e of edits.sort((a,b)=>b.start-a.start||b.end-a.end))output=output.slice(0,e.start)+e.text+output.slice(e.end);
 // Remove an old named import only when there are no remaining references.
 const currentDescriptor=descriptor?parse(output).descriptor:null;
 const currentBlocks=currentDescriptor?[currentDescriptor.script,currentDescriptor.scriptSetup].filter(Boolean).map(s=>({text:s.content,offset:s.loc.start.offset})):[{text:output,offset:0}];
 const clean=[];
 for(const block of currentBlocks){const ast=ts.createSourceFile(filename,block.text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
  for(const n of ast.statements)if(ts.isImportDeclaration(n)&&/compat\/tdesign\/magic-controls/.test(n.moduleSpecifier.text)){
   const all=[...(n.importClause?.namedBindings?.elements||[])];const keep=all.filter(e=>{if((e.propertyName||e.name).text!=='bkInput')return true;let used=false;const visit=x=>{if(x===n)return;if(ts.isIdentifier(x)&&x.text===e.name.text)used=true;ts.forEachChild(x,visit);};visit(ast);return used;});
   if(keep.length!==all.length)clean.push({start:block.offset+n.getStart(ast),end:block.offset+n.end,text:keep.length?`import { ${keep.map(e=>e.getText(ast)).join(', ')} } from ${n.moduleSpecifier.getText(ast)};`:''});
  }
 }
 for(const e of clean.sort((a,b)=>b.start-a.start))output=output.slice(0,e.start)+e.text+output.slice(e.end);
 return {output,count,skipped};
}
const walk=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(resolve(d,e.name)):[resolve(d,e.name)]);
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const report={files:[],count:0,skipped:[]};
 for(const file of walk(resolve(root,'src')).filter(f=>/\.(vue|[jt]sx?)$/.test(f)&&!f.includes('/platform/compat/')&&!f.endsWith('.d.ts'))){const source=fs.readFileSync(file,'utf8'),result=migrateTextInputs(source,file);report.count+=result.count;report.skipped.push(...result.skipped.map(s=>({file:relative(root,file),...s})));if(source!==result.output){report.files.push(relative(root,file));if(process.argv.includes('--write')){const backup=resolve('/tmp/bklog-native-text-input-before',relative(root,file));fs.mkdirSync(dirname(backup),{recursive:true});if(!fs.existsSync(backup))fs.writeFileSync(backup,source);fs.writeFileSync(file,result.output);}}}
 fs.writeFileSync(resolve(root,'ai-native/text-inputs-migration.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({files:report.files.length,count:report.count,skipped:report.skipped.length}));
}
