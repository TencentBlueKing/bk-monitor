import { localArtifactUrl, localArtifactPath } from './local-artifacts.mjs';
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import{spawnSync}from'node:child_process';
import{readFileSync,writeFileSync,mkdirSync}from'node:fs';
import{fileURLToPath}from'node:url';
import{resolve}from'node:path';
import{digest}from'./protocol.mjs';
export function verifyCalibration({files,requiredIds}){
 const proc=spawnSync(process.execPath,['--test','--test-reporter=tap',...files],{encoding:'utf8',maxBuffer:16*1024*1024});
 const passed=[...(proc.stdout??'').matchAll(/^ok \d+ - (.+)$/gm)].map(m=>m[1]);
 const missing=requiredIds.filter(id=>passed.filter(p=>p===id).length!==1);
 return{schemaVersion:1,status:proc.status===0&&!missing.length&&requiredIds.length>0?'UNIT_CALIBRATION_PASSED':'INVALID_CALIBRATION',processExit:proc.status,required:requiredIds.length,passed:passed.length,missing,testFileDigests:files.map(file=>({file,sha256:digest(readFileSync(file,'utf8'))})),stdout:proc.stdout,stderr:proc.stderr};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const spec=JSON.parse(readFileSync(new URL('../spec/calibration-required.json',import.meta.url),'utf8'));
 const result=verifyCalibration({files:spec.unit.files.map(f=>fileURLToPath(new URL(f,import.meta.url))),requiredIds:spec.unit.ids});
 const dir=fileURLToPath(localArtifactUrl('runs/calibration/'));mkdirSync(dir,{recursive:true});writeFileSync(resolve(dir,'unit-result.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({...result,stdout:undefined,stderr:undefined}));if(result.status!=='UNIT_CALIBRATION_PASSED')process.exitCode=1;
}
