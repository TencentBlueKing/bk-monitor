/** Validate a local source migration without persisting rendered or business data. */
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compileString } from 'sass';
import postcss from 'postcss';
import { resolveSemanticVariables } from './tdesign-style-source.mjs';
const project=fileURLToPath(new URL('../',import.meta.url)), source=resolve(project,'src');
const archive=process.argv[2];
if(!archive||!resolve(archive).startsWith('/private/tmp/'))throw new Error('Expected local external source archive');
const walk=dir=>readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?walk(resolve(dir,entry.name)):entry.isFile()?[resolve(dir,entry.name)]:[]);
const sections=(file,text)=>file.endsWith('.scss')?[text]:[...text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map(match=>match[1]);
const importer={findFileUrl(url){if(url.startsWith('@/'))return pathToFileURL(resolve(source,url.slice(2)));if(url.startsWith('~'))return pathToFileURL(resolve(project,'node_modules',url.slice(1)));return null;}};
const semanticDefaults=new Map();
postcss.parse(compileString(readFileSync(resolve(source,'shared/styles/theme/tokens.scss'),'utf8'),{url:pathToFileURL(resolve(source,'shared/styles/theme/tokens.scss'))}).css).walkDecls(decl=>semanticDefaults.set(decl.prop,decl.value));
const valueCache=new Map();
function canonicalValue(value){
 if(valueCache.has(value))return valueCache.get(value);
 const expanded=resolveSemanticVariables(value,(token,fallback)=>{
  if(semanticDefaults.has(token))return semanticDefaults.get(token);
  if(token.startsWith('--bklog-z-'))return fallback;
  throw new Error('Missing semantic token '+token);
 });
 // Sass serializes alpha hex colors as rgba outside var() fallbacks.
 const serialized=compileString('a { value: '+expanded+'; }',{logger:{warn(){},debug(){}}}).css;
 let result;
 postcss.parse(serialized).walkDecls(decl=>{result=decl.value.trim().replace(/\s+/g,' ').replace(/#[\da-f]+/gi,v=>v.length===4?'#'+[...v.slice(1)].map(c=>c+c).join('').toLowerCase():v.toLowerCase());});
 valueCache.set(value,result);return result;
}
function canonical(css){
 const root=postcss.parse(css);const result=[];
 root.walkRules(rule=>{
  const declarations=(rule.nodes||[]).filter(node=>node.type==='decl').map(decl=>{
   // Every changed visual has an explicit original fallback. Resolve only those
   // application semantic variables; leave existing dynamic CSS unchanged.
   const value=canonicalValue(decl.value);
   return [decl.prop,value,Boolean(decl.important)].join('|');
  }).sort();
  if(declarations.length) result.push(JSON.stringify([rule.selector.replace(/\s+/g,' ').trim(),declarations]));
 });
 return result;
}
const results=[];
for(const oldPath of walk(resolve(archive))){
 const file=relative(resolve(archive),oldPath),currentPath=resolve(source,file);
 if(!existsSync(currentPath))throw new Error('Missing migrated source: '+file);
 const beforeText=readFileSync(oldPath,'utf8'),afterText=readFileSync(currentPath,'utf8');
 const before=sections(file,beforeText),after=sections(file,afterText);
 let error;
 if(before.length!==after.length)error='style section count changed';
 if(file.endsWith('.vue')){const outside=text=>text.replace(/(<style\b[^>]*>)[\s\S]*?(<\/style>)/g,'$1$2');if(outside(beforeText)!==outside(afterText))error='non-style SFC content changed';}
 for(let i=0;!error&&i<before.length;i++){
  try{
   const opts={url:pathToFileURL(currentPath),importers:[importer],loadPaths:[resolve(project,'node_modules')],logger:{warn(){},debug(){}}};
   const left=canonical(compileString(before[i],opts).css),right=canonical(compileString(after[i],opts).css);
   if(JSON.stringify(left)!==JSON.stringify(right)){error='compiled selector/declaration contract differs';if(process.env.STYLE_DEBUG){const index=left.findIndex((value,index)=>value!==right[index]);console.error(file,left[index],right[index]);}}
  }catch(e){error='compile unavailable: '+String(e.message).split('\n')[0];}
 }
 results.push({file,status:error?'FAILED':'EQUIVALENT',...(error?{reason:error}:{})});
}
const failures=results.filter(result=>result.status!=='EQUIVALENT');
console.log(JSON.stringify({files:results.length,equivalent:results.length-failures.length,failures},null,2));
if(failures.length)process.exitCode=1;
