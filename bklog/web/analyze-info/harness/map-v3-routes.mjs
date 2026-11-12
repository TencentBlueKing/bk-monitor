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

import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {inspectSources} from './source-inventory.mjs';
import {routeEntries} from './route-entries.mjs';
const source = fileURLToPath(new URL('../source/',import.meta.url));
const v2root = fileURLToPath(new URL('../../packages/web-v2/src/',import.meta.url));
const v3root = fileURLToPath(new URL('../../packages/web-v3/src/',import.meta.url));
const v2graph = JSON.parse(readFileSync(resolve(source,'entry-graph.json')));
const v2 = JSON.parse(readFileSync(resolve(source,'route-entries.json')));
for(const ref of v2graph.files)if(createHash('sha256').update(readFileSync(resolve(v2root,ref.file))).digest('hex')!==ref.sha256)throw Error('V2_SOURCE_CHANGED');
const graph = inspectSources(v3root,{routePrefixes:['app/router/']});
const v3 = routeEntries(graph,graph.routes,file=>readFileSync(resolve(v3root,file),'utf8'),{componentPrefixes:['features/','app/shell/','shared/ui/']});
const paired = new Set();
const matches = v2.map(entry=>{
  const candidates = entry.name ? v3.filter(target=>target.name===entry.name) : entry.path ? v3.filter(target=>target.path===entry.path) : [];
  for(const target of candidates)paired.add(target.id);
  return {v2:entry,candidates:candidates.map(target=>({id:target.id,name:target.name,path:target.path,file:target.file,line:target.line,sha256:target.sha256,entryKind:target.entryKind,componentSources:target.componentSources,unresolvedFactories:target.unresolvedFactories})),discoveryStatus:candidates.length===1?'SINGLE_STATIC_CANDIDATE':candidates.length?'AMBIGUOUS_STATIC_CANDIDATES':'NO_STATIC_CANDIDATE',samePath:candidates.length===1?entry.path===candidates[0].path:null,businessAccepted:false,uiAccepted:false};
});
const report={schemaVersion:1,scope:'STATIC_ROUTE_MAPPING_NOT_MIGRATION_ACCEPTANCE',v2SourceDigest:v2graph.sourceDigest,v3SourceDigest:graph.sourceDigest,v2Routes:v2.length,v3Routes:v3.length,summary:{single:matches.filter(x=>x.candidates.length===1).length,ambiguous:matches.filter(x=>x.candidates.length>1).length,missing:matches.filter(x=>!x.candidates.length).length,pathDifferences:matches.filter(x=>x.samePath===false).length},matches,extraV3Entries:v3.filter(entry=>!paired.has(entry.id)),diagnostics:graph.diagnostics,limitations:['Route names/paths are discovery keys, never business or UI equivalence.','Conditional factories include all discovered branches; runtime selection remains unverified.','Styles/config/build artifacts and dynamically assembled entries require separate analysis.']};
for(const[name,value]of Object.entries({'v3-entry-graph':graph,'v3-route-entries':v3,'route-migration-map':report}))writeFileSync(resolve(source,name+'.json'),JSON.stringify(value,null,2)+'\n');
console.log(JSON.stringify({scope:report.scope,v2:report.v2Routes,v3:report.v3Routes,...report.summary,v3ScriptFiles:graph.files.length,diagnostics:graph.diagnostics.length}));
