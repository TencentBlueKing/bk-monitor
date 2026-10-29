/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {existsSync,mkdirSync,mkdtempSync,readFileSync,readdirSync,renameSync,rmSync,symlinkSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync,spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const packageRoot=fileURLToPath(new URL('../',import.meta.url));
const manifest=JSON.parse(readFileSync(resolve(packageRoot,'architecture-archive/src-native-20261028.manifest.json'),'utf8'));
const digest=value=>createHash('sha256').update(value).digest('hex');
let extracted;
export function getBaselineArchiveRoot() {
  if(extracted)return extracted;
  const archive=resolve(packageRoot,manifest.archive);
  if(digest(readFileSync(archive))!==manifest.archiveSha256)throw new Error('Frozen source archive checksum mismatch');
  const cache=resolve(tmpdir(),`bklog-baseline-${manifest.archiveSha256.slice(0,20)}-layout2`);
  const marker=resolve(cache,'.verified-baseline.json');
  if(!existsSync(marker)) {
    const stage=mkdtempSync(resolve(tmpdir(),'bklog-baseline-stage-'));
    try {
      const archiveRoot=resolve(stage,'web/packages/web-v3');
      mkdirSync(archiveRoot,{recursive:true});
      execFileSync('tar',['-xzf',archive,'-C',archiveRoot]);
      for(const item of manifest.files) {
        if(digest(readFileSync(resolve(archiveRoot,item.path)))!==item.sha256)throw new Error(`Frozen file checksum mismatch: ${item.path}`);
      }
      // Historical tests keep their original module resolution without creating
      // another source tree or dependency installation inside the application.
      symlinkSync(resolve(packageRoot,'node_modules'),resolve(archiveRoot,'node_modules'),'dir');
      const webRoot=resolve(packageRoot,'../..');
      for(const name of ['src','node_modules','package.json'])symlinkSync(resolve(webRoot,name),resolve(stage,'web',name));
      writeFileSync(resolve(stage,'.verified-baseline.json'),JSON.stringify({archiveSha256:manifest.archiveSha256}));
      try {renameSync(stage,cache);}catch(error){if(!existsSync(marker))throw error;}
    }finally{if(existsSync(stage))rmSync(stage,{recursive:true});}
  }
  if(JSON.parse(readFileSync(marker,'utf8')).archiveSha256!==manifest.archiveSha256)throw new Error('Frozen source cache identity mismatch');
  const migrationAssets=resolve(cache,'web/migration-project');
  if(!existsSync(migrationAssets))symlinkSync(resolve(packageRoot,'../../migration-project'),migrationAssets,'dir');
  extracted=resolve(cache,'web/packages/web-v3');
  return extracted;
}
export const getBaselineRoot=()=>resolve(getBaselineArchiveRoot(),manifest.sourceRoot);
export const baselineUrl=file=>pathToFileURL(resolve(getBaselineRoot(),file));
export function verifyBaseline() {
  const root=getBaselineArchiveRoot();
  for(const item of manifest.files)if(digest(readFileSync(resolve(root,item.path)))!==item.sha256)throw new Error(`Frozen file changed: ${item.path}`);
  return {archive:manifest.archive,archiveSha256:manifest.archiveSha256,files:manifest.files.length};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  if(process.argv[2]==='test'){
    const root=getBaselineArchiveRoot();
    const tests=readdirSync(resolve(root,'tests-native')).filter(name=>name.endsWith('.test.mjs')).map(name=>resolve(root,'tests-native',name));
    const result=spawnSync(process.execPath,['--test',...tests],{cwd:root,stdio:'inherit'});
    process.exitCode=result.status??1;
  }else console.log(JSON.stringify(verifyBaseline(),null,2));
}
