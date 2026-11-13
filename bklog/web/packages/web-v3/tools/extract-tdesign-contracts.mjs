/** Extract only reviewed, identical declaration contracts. Not a style redesign. */
import { readFileSync, writeFileSync, readdirSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { styleDeclarations } from './tdesign-style-source.mjs';
const project = fileURLToPath(new URL('../', import.meta.url)), source = resolve(project,'src');
const signatures = new Map([
  ['height:100%;width:100%','control-fill'],
  ['border-radius:0;border:1px solid transparent;transition:border-color 0.3s ease-in-out','cell-editor'],
  ['border-bottom-right-radius:0;border-top-right-radius:0','join-next'],
  ['border-bottom-left-radius:0;border-top-left-radius:0','join-previous'],
  ['height:26px;line-height:26px','compact-control'],
  ['height:24px;line-height:22px;min-width:54px','compact-action'],
  ['border-radius:0;width:140px','filter-operator'],
]);
const walk = dir => readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?walk(resolve(dir,entry.name)):entry.isFile()?[resolve(dir,entry.name)]:[]);
const write=process.argv.includes('--write'), archive=process.argv.find(arg=>arg.startsWith('--archive='))?.slice(10);
if(write&&(!archive||!resolve(archive).startsWith('/private/tmp/')))throw new Error('External source archive required');
const records=[];
for(const path of walk(resolve(source,'features')).filter(path=>path.endsWith('.scss'))){
 const original=readFileSync(path,'utf8'), declarations=styleDeclarations(original), changes=[], contracts=[];
 for(const id of new Set(declarations.map(decl=>decl.block))){
  const group=declarations.filter(decl=>decl.block===id);
  const name=signatures.get(group.map(decl=>decl.property+':'+decl.value.trim()).sort().join(';'));
  if(!name)continue;
  contracts.push(name);
  group.forEach((decl,index)=>changes.push({start:decl.start,end:decl.end,value:index===0?((original.slice(decl.start,decl.end).match(/^\s*/)||[''])[0]+`@include bklogControls.${name};`):''}));
 }
 if(!changes.length)continue;
 let output=original;
 for(const change of changes.sort((a,b)=>b.start-a.start)) output=output.slice(0,change.start)+change.value+output.slice(change.end);
 let module=relative(dirname(path),resolve(source,'shared/styles/theme/components/contracts')).replaceAll('\\','/');
 if(!module.startsWith('.'))module='./'+module;
 output=`@use '${module}' as bklogControls;\n`+output;
 const file=relative(source,path);
 records.push({file,contracts});
 if(write){const target=resolve(archive,file);if(!existsSync(target)){mkdirSync(dirname(target),{recursive:true});writeFileSync(target,original);}writeFileSync(path,output);}
}
console.log(JSON.stringify({files:records.length,contracts:records.reduce((sum,row)=>sum+row.contracts.length,0),records},null,2));
