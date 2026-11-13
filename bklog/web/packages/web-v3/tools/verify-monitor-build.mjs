/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {readFileSync,readdirSync,writeFileSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,relative,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const packageRoot=fileURLToPath(new URL('../',import.meta.url));
const digest=content=>createHash('sha256').update(content).digest('hex');
function walk(dir){return readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?walk(resolve(dir,entry.name)):[resolve(dir,entry.name)]).sort();}
export function monitorBuildIdentity() {
  const sourceDigest=digest(walk(resolve(packageRoot,'src')).map(file=>relative(packageRoot,file)+'\0'+digest(readFileSync(file))).join('\n'));
  const configs=['vite.config.ts','vite.application.config.mjs','vite.application-source.config.ts','vite.base.config.ts','vite.monitor.config.ts','tools/monitor-style-scope.mjs','tools/native-sdk-vue.mjs','tools/legacy-static-entry.mjs','tools/verify-legacy-deployment.mjs','tools/verify-monitor-build.mjs','tools/compile-messages.mjs','project.inlang/settings.json','project.inlang/paraglide.config.mjs','package.json','pnpm-lock.yaml'];
  const inputs=[...configs.map(file=>resolve(packageRoot,file)).filter(existsSync),...walk(resolve(packageRoot,'migration-runtime'))];
  const buildConfigDigest=digest(inputs.sort().map(file=>relative(packageRoot,file)+'\0'+digest(readFileSync(file))).join('\n'));
  return {sourceDigest,buildConfigDigest};
}
export function verifyMonitorBuild(kind,output=resolve(packageRoot,'dist-monitor',kind)) {
  if(!['apm','trace'].includes(kind))throw new Error('Expected apm or trace');
  const entry=readFileSync(resolve(output,'main.js'),'utf8');
  const required=[kind==='apm'?'MonitorApmLog':'MonitorTraceLog','Vue2','configureMonitorApp','logStore','i18n','initMonitorState','initGlobalComponents','initWindowState'];
  // Rollup emits the public CommonJS assignments at the end of the entry chunk.
  const exported=[...entry.slice(-12000).matchAll(/exports\.([\w$]+)\s*=/g)].map(match=>match[1]);
  for(const name of required)if(!exported.includes(name))throw new Error(`Missing Monitor export: ${name}`);
  const cssFile=resolve(output,'css/main.css');
  const css=readFileSync(cssFile,'utf8');
  for(const match of css.matchAll(/url\(["']?([^)'"\s]+)["']?\)/g)) {
    const url=match[1];if(/^(?:data:|https?:|\/|#)/.test(url))continue;
    if(!existsSync(resolve(dirname(cssFile),decodeURIComponent(url.split(/[?#]/)[0]))))throw new Error(`Missing stylesheet asset: ${url}`);
  }
  const assets=walk(output).filter(file=>file.endsWith('.js')&&file!==resolve(output,'main.js'));
  for(const worker of ['retrieve-search.worker','cluster-table.worker'])if(!assets.some(file=>file.includes(worker)))throw new Error(`Missing compiled worker: ${worker}`);
  if(kind==='trace'&&!css.includes('.monitor-trace-log .t-'))throw new Error('Trace control CSS scope is absent');
  writeFileSync(resolve(output,'package.json'),JSON.stringify({name:`@blueking/monitor-${kind}-log`,private:true,type:'commonjs',main:'main.js'},null,2)+'\n');
  const identity=monitorBuildIdentity();
  const recordedIdentity=JSON.parse(readFileSync(resolve(output,'build-identity.json'),'utf8'));
  if(recordedIdentity.sourceDigest!==identity.sourceDigest||recordedIdentity.buildConfigDigest!==identity.buildConfigDigest)throw new Error('Monitor build snapshot differs from current sources; rebuild before packaging');
  const manifestFile=resolve(output,'migration-build.json');
  if(existsSync(manifestFile)){
    const prior=JSON.parse(readFileSync(manifestFile,'utf8'));
    if(prior.sourceDigest!==identity.sourceDigest||prior.buildConfigDigest!==identity.buildConfigDigest)throw new Error('Monitor artifacts are stale; rebuild before packaging');
    const currentFiles=walk(output).filter(file=>file!==manifestFile).map(file=>({path:relative(output,file),sha256:digest(readFileSync(file))}));
    if(JSON.stringify(prior.files)!==JSON.stringify(currentFiles))throw new Error('Monitor artifacts changed after verification; rebuild before packaging');
  }
  const files=walk(output).filter(file=>!file.endsWith('/migration-build.json')).map(file=>({path:relative(output,file),sha256:digest(readFileSync(file))}));
  const manifest={schemaVersion:1,kind,sourceRoot:'src',...identity,format:'commonjs',entry:'main.js',stylesheet:'css/main.css',exports:required,files};
  writeFileSync(resolve(output,'migration-build.json'),JSON.stringify(manifest,null,2)+'\n');
  return manifest;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const manifest=verifyMonitorBuild(process.argv[2]);console.log(JSON.stringify({kind:manifest.kind,files:manifest.files.length,exports:manifest.exports,sourceDigest:manifest.sourceDigest},null,2));
}
