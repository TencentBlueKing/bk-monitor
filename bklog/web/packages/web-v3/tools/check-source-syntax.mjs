/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {readFileSync,readdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
const root=fileURLToPath(new URL('../src',import.meta.url));
function walk(dir){return readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?walk(resolve(dir,entry.name)):[resolve(dir,entry.name)]);}
const diagnostics=[];
const files=walk(root).filter(file=>/\.[cm]?[jt]sx?$/.test(file));
for(const file of files){
 const kind=/\.tsx$/.test(file)?ts.ScriptKind.TSX:/\.(?:jsx|[cm]?js)$/.test(file)?ts.ScriptKind.JSX:ts.ScriptKind.TS;
 const source=ts.createSourceFile(file,readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,kind);
 diagnostics.push(...source.parseDiagnostics);
}
if(diagnostics.length){
 console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics,{getCanonicalFileName:name=>name,getCurrentDirectory:()=>process.cwd(),getNewLine:()=> '\n'}));process.exitCode=1;
}else console.log(`Source syntax passed (${files.length} modules).`);
