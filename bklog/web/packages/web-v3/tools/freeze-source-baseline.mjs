/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {readFileSync,readdirSync,writeFileSync,existsSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {resolve,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const digest=value=>createHash('sha256').update(value).digest('hex');
const mapping=JSON.parse(readFileSync(resolve(root,'ai-native/source-map.json'),'utf8'));
for(const item of [...mapping.files,...mapping.consolidated||[]]){
 const file=resolve(root,'src-native',item.source);
 if(digest(readFileSync(file))!==item.sourceSha256)throw new Error(`Baseline was modified: ${item.source}`);
}
const roots=['src-native','tests-native','migration-runtime','vite.native.config.ts','vite.migration.config.mjs','vite.base.config.ts','package.json','pnpm-lock.yaml'].filter(file=>existsSync(resolve(root,file)));
function walk(file){const absolute=resolve(root,file);return readdirSafe(absolute)?readdirSync(absolute,{withFileTypes:true}).flatMap(entry=>walk(relative(root,resolve(absolute,entry.name)))):[{path:file,sha256:digest(readFileSync(absolute))}];}
function readdirSafe(file){try{readdirSync(file);return true;}catch{return false;}}
const files=roots.flatMap(walk).sort((a,b)=>a.path.localeCompare(b.path));
const folder=resolve(root,'architecture-archive');mkdirSync(folder,{recursive:true});
const archive=resolve(folder,'src-native-20261028.tar.gz');
if(existsSync(archive))throw new Error('The frozen baseline archive already exists; verify it instead of overwriting it');
execFileSync('tar',['-czf',archive,'-C',root,...roots],{env:{...process.env,COPYFILE_DISABLE:'1'}});
const manifest={schemaVersion:1,archive:relative(root,archive),archiveSha256:digest(readFileSync(archive)),sourceRoot:'src-native',files,reason:'Immutable behavioral and route baseline; the application source is src.'};
writeFileSync(resolve(folder,'src-native-20261028.manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({archive:manifest.archive,files:files.length,sha256:manifest.archiveSha256},null,2));
