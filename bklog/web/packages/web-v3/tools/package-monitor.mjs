/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {cpSync,existsSync,mkdtempSync,readFileSync,readdirSync,renameSync,rmSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {verifyMonitorBuild} from './verify-monitor-build.mjs';
const packageRoot=fileURLToPath(new URL('../',import.meta.url));
const hash=value=>createHash('sha256').update(value).digest('hex');
function inventory(root){return readdirSync(root,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?inventory(resolve(root,entry.name)):[{path:resolve(root,entry.name),sha256:hash(readFileSync(resolve(root,entry.name)))}]).sort((a,b)=>a.path.localeCompare(b.path));}
export function packageMonitor(kind,{webRoot=resolve(packageRoot,'../..'),output=resolve(packageRoot,'dist-monitor',kind)}={}) {
  const manifest=verifyMonitorBuild(kind,output);
  const folder=`monitor-${kind}-retrieve`,destination=resolve(webRoot,folder);
  const metadata=JSON.parse(readFileSync(existsSync(resolve(destination,'package.json'))?resolve(destination,'package.json'):resolve(packageRoot,'monitor-packages',`${kind}.package.json`),'utf8'));
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
    return{kind,destination,version:metadata.version,sourceDigest:manifest.sourceDigest};
  }finally{if(existsSync(stage))rmSync(stage,{recursive:true});}
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(packageMonitor(process.argv[2]),null,2));
