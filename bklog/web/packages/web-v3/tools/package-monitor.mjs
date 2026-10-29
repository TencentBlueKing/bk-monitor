/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {cpSync,existsSync,mkdirSync,mkdtempSync,readFileSync,readdirSync,renameSync,rmSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {resolve,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {verifyMonitorBuild} from './verify-monitor-build.mjs';
const packageRoot=fileURLToPath(new URL('../',import.meta.url));
const hash=value=>createHash('sha256').update(value).digest('hex');
function inventory(root){return readdirSync(root,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?inventory(resolve(root,entry.name)):[{path:resolve(root,entry.name),sha256:hash(readFileSync(resolve(root,entry.name)))}]).sort((a,b)=>a.path.localeCompare(b.path));}
export function packageMonitor(kind,{webRoot=resolve(packageRoot,'../..'),output=resolve(packageRoot,'dist-monitor',kind),archiveRoot=resolve(packageRoot,'architecture-archive')}={}) {
  const manifest=verifyMonitorBuild(kind,output);
  const folder=`monitor-${kind}-retrieve`,destination=resolve(webRoot,folder);
  const previous=existsSync(destination)?inventory(destination):[];
  const metadata=JSON.parse(readFileSync(existsSync(resolve(destination,'package.json'))?resolve(destination,'package.json'):resolve(packageRoot,'monitor-packages',`${kind}.package.json`),'utf8'));
  let archive;
  if(previous.length) {
    mkdirSync(archiveRoot,{recursive:true});
    const snapshot=hash(JSON.stringify(previous.map(item=>({path:relative(destination,item.path),sha256:item.sha256}))));
    archive=resolve(archiveRoot,`${folder}-before-${snapshot.slice(0,12)}.tar.gz`);
    if(!existsSync(archive))execFileSync('tar',['-czf',archive,'-C',webRoot,folder],{env:{...process.env,COPYFILE_DISABLE:'1'}});
    const record={schemaVersion:1,directory:folder,archive:relative(packageRoot,archive),archiveSha256:hash(readFileSync(archive)),files:previous.map(item=>({path:relative(destination,item.path),sha256:item.sha256}))};
    writeFileSync(archive+'.json',JSON.stringify(record,null,2)+'\n');
  }
  const stage=mkdtempSync(resolve(webRoot,`.monitor-${kind}-next-`));
  const backup=stage+'.previous';
  try {
    cpSync(output,stage,{recursive:true});
    writeFileSync(resolve(stage,'package.json'),JSON.stringify({...metadata,type:'commonjs',main:'main.js'},null,2)+'\n');
    const delivered={...manifest,files:inventory(stage).filter(item=>!item.path.endsWith('/migration-build.json')).map(item=>({path:relative(stage,item.path),sha256:item.sha256}))};
    writeFileSync(resolve(stage,'migration-build.json'),JSON.stringify(delivered,null,2)+'\n');
    if(existsSync(destination))renameSync(destination,backup);
    try {renameSync(stage,destination);}catch(error){if(existsSync(backup))renameSync(backup,destination);throw error;}
    if(existsSync(backup))rmSync(backup,{recursive:true});
    return{kind,destination,archive,version:metadata.version,sourceDigest:manifest.sourceDigest};
  }finally{if(existsSync(stage))rmSync(stage,{recursive:true});}
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(packageMonitor(process.argv[2]),null,2));
