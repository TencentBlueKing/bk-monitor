/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {existsSync,readdirSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
function walk(dir){return readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?walk(resolve(dir,entry.name)):[resolve(dir,entry.name)]);}
const javascript=walk(resolve(root,'src')).filter(file=>/\.[cm]?jsx?$/.test(file)).map(file=>relative(root,file));
const duplicateSources=['src-native','src-prototype'].filter(name=>existsSync(resolve(root,name)));
const result={status:javascript.length||duplicateSources.length?'INCOMPLETE':'PASSED',sourceRoot:'src',duplicateSources,remainingJavascript:javascript.length,javascript};
console.log(JSON.stringify(result,null,2));
process.exitCode=result.status==='PASSED'?0:1;
