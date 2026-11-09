/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import fs from 'node:fs';
import {resolve, relative, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
import {parse} from '@vue/compiler-sfc';
const root=fileURLToPath(new URL('../',import.meta.url));
const controls={'bk-alert':['Alert','bkAlert'],'bk-tag':['Tag','bkTag'],'bk-progress':['Progress','bkProgress'],'bk-badge':['Badge','bkBadge']};
export function migrateDisplayControls(source,filename){
 const descriptor=filename.endsWith('.vue')?parse(source).descriptor:null;
 const edits=[],counts={}; const put=(start,end,text)=>edits.push({start,end,text});
 const blocks=descriptor?[descriptor.script,descriptor.scriptSetup].filter(Boolean).map(s=>({text:s.content,offset:s.loc.start.offset})):[{text:source,offset:0}];
 const literal=value=>/^(['\"])(.*)\1$/.exec(value)?.[2];
 const theme=value=>literal(value)!==undefined?JSON.stringify(literal(value)==='info'?'primary':literal(value)||'default'):`(${value}) === 'info' ? 'primary' : ((${value}) || 'default')`;
 const variant=value=>literal(value)!==undefined?JSON.stringify(({stroke:'outline',filled:'dark'})[literal(value)]||'light'):`(${value}) === 'stroke' ? 'outline' : ((${value}) === 'filled' ? 'dark' : 'light')`;
 const color=value=>literal(value)!==undefined?JSON.stringify(({primary:'#3a84ff',success:'#2dcb56',warning:'#ff9c01',danger:'#ea3636'})[literal(value)]):`({'primary':'#3a84ff','success':'#2dcb56','warning':'#ff9c01','danger':'#ea3636'}[(${value}) || 'primary'])`;
 for(const block of blocks){
  const ast=ts.createSourceFile(filename,block.text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),imports=new Map(),native=new Set();
  const start=n=>block.offset+n.getStart(ast),end=n=>block.offset+n.end;
  for(const node of ast.statements)if(ts.isImportDeclaration(node)&&/compat\/tdesign\/magic-controls/.test(node.moduleSpecifier.text)){
   const all=[...(node.importClause?.namedBindings?.elements||[])],keep=[];
   for(const e of all){const old=(e.propertyName||e.name).text,found=Object.entries(controls).find(([,spec])=>spec[1]===old);if(found){imports.set(e.name.text,found[0]);native.add(`${found[1][0]} as ${e.name.text.startsWith('bk')?'T'+found[1][0]:e.name.text}`);}else keep.push(e);}
   if(keep.length!==all.length)put(start(node),end(node),keep.length?`import { ${keep.map(e=>e.getText(ast)).join(', ')} } from ${node.moduleSpecifier.getText(ast)};`:'');
  }
  const val=p=>!p.initializer?'true':ts.isJsxExpression(p.initializer)?p.initializer.expression?.getText(ast)||'true':p.initializer.getText(ast);
  const visit=n=>{
   if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n)){
    const tag=n.tagName.getText(ast),key=controls[tag]?tag:imports.get(tag),spec=controls[key];
    if(spec){
     const name=controls[tag]||tag.startsWith('bk')?'T'+spec[0]:tag;
     if(name!==tag)put(start(n.tagName),end(n.tagName),name);
     if(controls[tag])native.add(`${spec[0]} as T${spec[0]}`);
     counts[key]=(counts[key]||0)+1;
     const props=n.attributes.properties.filter(ts.isJsxAttribute),get=name=>props.find(p=>p.name.getText(ast)===name);
     if(key==='bk-tag'&&!get('type'))put(end(n.attributes),end(n.attributes)," variant='light'");
     if(['bk-tag','bk-alert'].includes(key))put(end(n.attributes),end(n.attributes),` data-v2-display='${key.slice(3)}'`);
     const rewrite=(p,name,v=val(p))=>put(start(p),end(p),`${name}={${v}}`);
     for(const p of props){const name=p.name.getText(ast),v=val(p);
      if(key==='bk-alert'){
       if(name==='type')rewrite(p,'theme');if(name==='title')rewrite(p,'message');if(name==='closable')rewrite(p,'closeBtn');
       if(name==='show-icon'||name==='showIcon')rewrite(p,'icon',`(${v}) ? undefined : () => null`);
       if(name==='v-slots'&&p.initializer&&ts.isJsxExpression(p.initializer)&&ts.isObjectLiteralExpression(p.initializer.expression))for(const slot of p.initializer.expression.properties)if(slot.name?.getText(ast)==='title')put(start(slot.name),end(slot.name),'message');
      }
      if(key==='bk-tag'){
       if(name==='theme')rewrite(p,'theme',theme(v));
       if(name==='type')rewrite(p,'variant',variant(v));
       if(name==='radius'){if(get('style'))throw Error(`Merge radius/style manually: ${filename}`);rewrite(p,'style',`{borderRadius: ${v}}`);}
       if(name==='onClose'&&!/^\(\)\s*=>/.test(v)&&!new RegExp('(?:const|let)\\s+'+v+'\\s*=\\s*\\(\\)\\s*=>').test(block.text))rewrite(p,'onClose',`({e}) => (${v})(e)`);
       if(name==='icon')rewrite(p,'icon',`() => <i class={${v}} />`);
       if(name==='onClick')rewrite(p,'onClick',`() => (${v})()`);
      }
      if(key==='bk-progress'){
       if(name==='percent')rewrite(p,'percentage',`Number(((${v}) * 100).toFixed(0))`);
       if(name==='theme')rewrite(p,'color',color(v));
       if(['show-text','showText'].includes(name))rewrite(p,'label');
      }
      if(name==='ext-cls'||name==='extCls'){
       const cls=get('class');if(cls){rewrite(cls,'class',`[${val(cls)}, ${v}]`);put(start(p),end(p),'');}else rewrite(p,'class');
      }
     }
    }
   }
   if(ts.isJsxClosingElement(n)){const tag=n.tagName.getText(ast),key=controls[tag]?tag:imports.get(tag);if(key&&(controls[tag]||tag.startsWith('bk')))put(start(n.tagName),end(n.tagName),'T'+controls[key][0]);}
   ts.forEachChild(n,visit);
  };visit(ast);
  // Registry shorthand identifiers must use the native import as well.
  for(const [local,key]of imports)if(local.startsWith('bk')){
   const walk=n=>{if(ts.isIdentifier(n)&&n.text===local&&!ts.isImportSpecifier(n.parent)&&!ts.isJsxOpeningElement(n.parent)&&!ts.isJsxClosingElement(n.parent)&&!ts.isJsxSelfClosingElement(n.parent))put(start(n),end(n),'T'+controls[key][0]);ts.forEachChild(n,walk);};walk(ast);
  }
  if(native.size)put(block.offset,block.offset,`\nimport { ${[...native].join(', ')} } from 'tdesign-vue-next';\n`);
 }
 if(descriptor?.template?.ast){
  const visit=n=>{
   if(n.type===1&&controls[n.tag]){
    const key=n.tag,spec=controls[key],tag='t-'+spec[0].toLowerCase(),start=n.loc.start.offset,close=n.loc.source.lastIndexOf('</'+key);
    put(start+1,start+1+key.length,tag);if(close>=0)put(start+close+2,start+close+2+key.length,tag);counts[key]=(counts[key]||0)+1;
    const name=p=>p.type===6?p.name:p.arg?.content,value=p=>p.type===6?p.value?JSON.stringify(p.value.content):'true':p.exp?.content||'true',get=k=>n.props.find(p=>name(p)===k);
    const rewrite=(p,k,v=value(p))=>put(p.loc.start.offset,p.loc.end.offset,`:${k}="${v.replaceAll('"',"'")}"`);
    for(const p of n.props){const k=name(p),v=value(p);
     if(key==='bk-alert'){
      if(k==='type')rewrite(p,'theme');if(k==='title')rewrite(p,'message');if(k==='closable')rewrite(p,'close-btn');if(k==='show-icon')rewrite(p,'icon',`(${v}) ? undefined : () => null`);
     }
     if(key==='bk-tag'){
      if(k==='theme')rewrite(p,'theme',theme(v));
      if(k==='type')rewrite(p,'variant',variant(v));
      if(p.type===7&&p.name==='on'&&k==='close'){
       const expression=p.exp.content;
       put(p.loc.start.offset,p.loc.end.offset,`@close="({e}) => ${/^[\w.$]+$/.test(expression)?expression+'(e)':expression.replaceAll('$event','e')}"`);
      }
     }
     if(key==='bk-progress'){if(k==='percent')rewrite(p,'percentage',`Number(((${v}) * 100).toFixed(0))`);if(k==='theme')rewrite(p,'color',color(v));if(k==='show-text')rewrite(p,'label');}
     if(key==='bk-badge'){
      if(k==='val')rewrite(p,'count',get('visible')?`(${value(get('visible'))}) ? (${v}) : 0`:v);
      if(k==='visible')rewrite(p,'show-zero');
      if(k==='theme')rewrite(p,'color',`'#ea3636'`);
      if(k==='position')put(p.loc.start.offset,p.loc.end.offset,'');
     }
     if(k==='ext-cls'){const cls=get('class');if(cls){rewrite(cls,'class',`[${value(cls)}, ${v}]`);put(p.loc.start.offset,p.loc.end.offset,'');}else rewrite(p,'class');}
    }
    if(key==='bk-tag'&&!get('type'))put(start+1+key.length,start+1+key.length,' variant="light"');
    if(['bk-tag','bk-alert'].includes(key))put(start+1+key.length,start+1+key.length,` data-v2-display="${key.slice(3)}"`);
    if(key==='bk-badge')put(start+1+key.length,start+1+key.length,` :max-count="Infinity"${get('visible')?'':' show-zero'}`);
    if(key==='bk-alert')for(const child of n.children||[])for(const p of child.props||[])if(p.type===7&&p.name==='slot'&&p.arg?.content==='title')put(p.arg.loc.start.offset,p.arg.loc.end.offset,'message');
   }
   for(const child of n.children||[])visit(child);
  };visit(descriptor.template.ast);
 }
 let output=source;for(const e of edits.sort((a,b)=>b.start-a.start||b.end-a.end))output=output.slice(0,e.start)+e.text+output.slice(e.end);
 return {output,counts};
}
const walk=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(resolve(d,e.name)):[resolve(d,e.name)]);
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const report={files:[],counts:{}};
 for(const file of walk(resolve(root,'src')).filter(f=>/\.(vue|[jt]sx?)$/.test(f)&&!f.includes('/platform/compat/')&&!f.endsWith('.d.ts'))){
  const source=fs.readFileSync(file,'utf8'),result=migrateDisplayControls(source,file);
  for(const[k,n]of Object.entries(result.counts))report.counts[k]=(report.counts[k]||0)+n;
  if(result.output!==source){report.files.push(relative(root,file));if(process.argv.includes('--write')){const backup=resolve('/tmp/bklog-native-display-before',relative(root,file));fs.mkdirSync(dirname(backup),{recursive:true});if(!fs.existsSync(backup))fs.writeFileSync(backup,source);fs.writeFileSync(file,result.output);}}
 }
 fs.writeFileSync(resolve(root,'ai-native/display-controls-migration.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
