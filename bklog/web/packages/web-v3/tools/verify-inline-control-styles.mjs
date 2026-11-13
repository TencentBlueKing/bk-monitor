/** Prove the inline batch changed only the reviewed static visual literals. */
import {readFileSync,readdirSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
import {parse} from '@vue/compiler-sfc';
import {normalizeInlineControls} from './inline-control-styles.mjs';
const source=fileURLToPath(new URL('../src/',import.meta.url)),archive=process.argv[2];
if(!archive||!resolve(archive).startsWith('/private/tmp/'))throw new Error('Expected external local archive');
const walk=d=>readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(resolve(d,e.name)):e.isFile()?[resolve(d,e.name)]:[]);
const failures=[];let files=0;
for(const path of walk(archive)){
 const file=relative(resolve(archive),path),before=readFileSync(path,'utf8'),after=readFileSync(resolve(source,file),'utf8');files++;
 if(normalizeInlineControls(file,before).output!==after)failures.push({file,reason:'Changes outside reviewed static visual values'});
 if(file.endsWith('.vue')){
  if(parse(after).errors.length>parse(before).errors.length)failures.push({file,reason:'New SFC parse error'});
 }else{
  const diagnostics=text=>ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX).parseDiagnostics.length;
  if(diagnostics(after)>diagnostics(before))failures.push({file,reason:'New script parse error'});
 }
}
console.log(JSON.stringify({files,passed:files-failures.length,failures},null,2));if(failures.length)process.exitCode=1;
