/** Static-only inline migration, backed up outside the repository. */
import {readFileSync,writeFileSync,readdirSync,mkdirSync,existsSync} from 'node:fs';
import {resolve,relative,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {normalizeInlineControls} from './inline-control-styles.mjs';
const project=fileURLToPath(new URL('../',import.meta.url)),source=resolve(project,'src');
const write=process.argv.includes('--write'),archive=process.argv.find(arg=>arg.startsWith('--archive='))?.slice(10);
if(write&&(!archive||!resolve(archive).startsWith('/private/tmp/')))throw new Error('External local archive required');
const walk=dir=>readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(resolve(dir,e.name)):e.isFile()?[resolve(dir,e.name)]:[]);
const records=[];
for(const path of walk(source).filter(path=>/\.(vue|[jt]sx?)$/.test(path))){
 const original=readFileSync(path,'utf8'),result=normalizeInlineControls(path,original);
 if(!result.count)continue;const file=relative(source,path);
 records.push({file,staticValues:result.count});
 if(write){const target=resolve(archive,file);if(!existsSync(target)){mkdirSync(dirname(target),{recursive:true});writeFileSync(target,original);}writeFileSync(path,result.output);}
}
console.log(JSON.stringify({mode:write?'written':'preview',files:records.length,staticValues:records.reduce((s,r)=>s+r.staticValues,0),records},null,2));
