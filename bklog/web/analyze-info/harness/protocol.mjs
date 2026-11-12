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
import { createHash } from 'node:crypto';
export const VERSION = 1;
export const OUTCOMES = ['UNEXECUTED','PASSED','FAILED','BLOCKED','INVALID_RUN','NEEDS_REVIEW'];
export function canonical(value) {
  if(value===undefined)return{$type:'undefined'};
  if(Array.isArray(value))return{$type:'array',values:value.map(canonical)};
  if(value&&typeof value==='object')return{$type:'object',entries:Object.keys(value).sort().map(k=>[k,canonical(value[k])])};
  return{$type:typeof value,value};
}
export const digest=value=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
export function requestSignature({url,method,body,context={}}){
  const u=new URL(url),query={};for(const key of [...new Set(u.searchParams.keys())].sort())query[key]=u.searchParams.getAll(key);
  let payload={encoding:'empty'};
  if(body!==undefined&&body!==null&&body!==''){try{payload={encoding:'json',value:JSON.parse(body)};}catch{payload={encoding:'text',value:body};}}
  return digest({method:method.toUpperCase(),path:u.pathname,query,payload,context});
}
export function requestPolicy(request,rules){
  const rulesForRequest=rules.filter(r=>r.method.toUpperCase()===request.method.toUpperCase()&&r.path===new URL(request.url).pathname);
  if(rulesForRequest.length>1)return{decision:'BLOCK',reason:'AMBIGUOUS_POLICY'};
  const rule=rulesForRequest[0];
  if(!rule||!rule.source?.sha256||!rule.rationale||rule.reviewed!==true)return{decision:'BLOCK',reason:'UNCLASSIFIED_ENDPOINT'};
  return ['READ','READ_STREAM'].includes(rule.semantics)?{decision:'ALLOW',ruleId:rule.id}:{decision:'BLOCK',reason:'WRITE_NOT_AUTHORIZED',ruleId:rule.id};
}
export class ReplayTape{
  constructor(entries){
    if(!entries.length||entries.some(e=>!e.complete||e.cancelled||!e.signature||!e.actionId||!e.response||!e.bodyDigest))throw Error('BASELINE_NOT_REPLAYABLE');
    for(const e of entries)if(digest(e.response)!==e.bodyDigest)throw Error('BASELINE_BODY_DIGEST_MISMATCH');
    this.entries=entries;this.used=new Set();
  }
  consume(request,actionId){const signature=requestSignature(request),index=this.entries.findIndex((e,i)=>!this.used.has(i)&&e.signature===signature&&e.actionId===actionId);if(index<0)throw Error('UNMATCHED_REPLAY_REQUEST');this.used.add(index);return this.entries[index].response;}
  assertConsumed(){if(this.used.size!==this.entries.length)throw Error('UNCONSUMED_REPLAY_REQUESTS');}
}
export function parseStream(text,{format='ndjson',transportFinished=false,cancelled=false,terminalRequired=false,terminal}={}){
  const chunks=[],errors=[];
  if(format==='ndjson'){
    for(const[index,line]of text.split(/\r?\n/).entries()){if(!line.trim())continue;try{chunks.push({index,value:JSON.parse(line)});}catch{errors.push({index,reason:'INVALID_JSON'});}}
  }else if(format==='sse'){
    const blocks=text.replace(/\r\n|\r/g,'\n').split('\n\n');
    for(const[index,block]of blocks.entries()){
      const event={data:[]};for(const line of block.split('\n')){if(!line||line.startsWith(':'))continue;const split=line.indexOf(':'),name=split<0?line:line.slice(0,split),value=split<0?'':line.slice(split+1).replace(/^ /,'');if(name==='data')event.data.push(value);else if(['event','id'].includes(name))event[name]=value;}
      if(event.data.length){if(index===blocks.length-1)errors.push({reason:'UNTERMINATED_SSE_EVENT'});else chunks.push({...event,data:event.data.join('\n')});}
    }
  }else errors.push({reason:'UNKNOWN_STREAM_FORMAT'});
  const terminalObserved=terminal?chunks.some(terminal):!terminalRequired;
  return{chunks,errors,transportFinished,cancelled,terminalObserved,complete:transportFinished&&!cancelled&&!errors.length&&terminalObserved};
}
export function validateScenario(s){
  const errors=[];if(s.schemaVersion!==VERSION)errors.push('SCHEMA_VERSION');for(const k of ['id','sourceDigest','contextDigest'])if(typeof s[k]!=='string'||!s[k])errors.push(k);
  if(!s.sourceRefs?.length||s.sourceRefs.some(r=>!r.file||!r.sha256||!r.symbol))errors.push('SOURCE_REFS');
  if(!Array.isArray(s.actions)||!s.actions.length)errors.push('ACTIONS');const ids=new Set();
  for(const a of s.actions??[]){if(!a.id||ids.has(a.id))errors.push('ACTION_IDS');ids.add(a.id);if(!a.target?.scope||!a.target?.semanticId)errors.push('SCOPED_TARGET');for(const k of ['ready','expected']){const items=a[k]??[];if(!items.length)errors.push('EMPTY_'+k.toUpperCase());if(items.some(x=>!x.id)||new Set(items.map(x=>x.id)).size!==items.length)errors.push('ORACLE_IDS');}}
  return errors;
}
export function evaluateRun({scenario,run,baseline}){
  const schema=validateScenario(scenario);if(schema.length)return{outcome:'INVALID_RUN',reasons:schema};
  if(!run?.actions?.length)return{outcome:'UNEXECUTED',reasons:[]};
  if(run.authenticationBlocked||run.policyBlocks?.length)return{outcome:'BLOCKED',reasons:['AUTH_OR_POLICY']};
  if(run.sourceDigest!==scenario.sourceDigest||run.contextDigest!==scenario.contextDigest)return{outcome:'INVALID_RUN',reasons:['CONTEXT_OR_SOURCE_CHANGED']};
  if(!baseline?.selfReplayPassed||!baseline.complete||baseline.fixtureDigest!==run.fixtureDigest)return{outcome:'INVALID_RUN',reasons:['BASELINE_NOT_PROVEN']};
  const reasons=[];if(run.actions.some(a=>!scenario.actions.some(s=>s.id===a.id)))reasons.push('UNKNOWN_ACTION');
  for(const action of scenario.actions){const actual=run.actions.filter(a=>a.id===action.id);if(actual.length!==1){reasons.push('ACTION_MISSING_OR_DUPLICATE:'+action.id);continue;}const a=actual[0];
    if(a.targetMatches!==1||a.routeMatched!==true||a.ready?.length!==action.ready.length||!a.ready.every(r=>r.passed===true)||action.ready.some(r=>a.ready?.filter(x=>x.id===r.id).length!==1))reasons.push('ACTION_NOT_READY:'+action.id);
    const expected=action.expected.map(e=>e.id);if(expected.some(id=>a.assertions?.filter(x=>x.id===id).length!==1)||a.assertions?.some(x=>!expected.includes(x.id)))reasons.push('ASSERTIONS_MISSING_OR_UNKNOWN:'+action.id);
  }
  if(reasons.length)return{outcome:'INVALID_RUN',reasons};const assertions=run.actions.flatMap(a=>a.assertions??[]);
  if(assertions.some(a=>a.passed!==true&&a.passed!==false))return{outcome:'NEEDS_REVIEW',reasons:['UNKNOWN_ASSERTION']};
  return{outcome:assertions.some(a=>!a.passed)?'FAILED':'PASSED',reasons:[],defectState:assertions.some(a=>!a.passed)?'CANDIDATE_NOT_CONFIRMED':null};
}
export function compareSemanticNodes(left,right,{geometryTolerance=0}={}){
  const diffs=[];function index(nodes,side){const m=new Map();for(const n of nodes.filter(n=>n.semanticId)){if(m.has(n.semanticId))diffs.push({kind:'AMBIGUOUS_KEY',side,id:n.semanticId});m.set(n.semanticId,n);}return m;}
  const a=index(left,'v2'),b=index(right,'v3');for(const[id,n]of a){const m=b.get(id);if(!m){diffs.push({kind:'MISSING',id});continue;}for(const field of ['role','name','value','checked','expanded','disabled','focused','occluded'])if(digest(field==='name'&&typeof n[field]==='string'?n[field].replace(/\s+/g,' ').trim():n[field])!==digest(field==='name'&&typeof m[field]==='string'?m[field].replace(/\s+/g,' ').trim():m[field]))diffs.push({kind:'SEMANTIC',id,field,expected:n[field],actual:m[field]});for(const field of ['x','y','width','height'])if(n.rect?.[field]!==undefined&&m.rect?.[field]!==undefined&&Math.abs(n.rect[field]-m.rect[field])>geometryTolerance)diffs.push({kind:'GEOMETRY',id,field,expected:n.rect[field],actual:m.rect[field]});}
  for(const id of b.keys())if(!a.has(id))diffs.push({kind:'EXTRA',id});return diffs;
}
export function confirmDefect(candidate,evidence){return candidate.defectState==='CANDIDATE_NOT_CONFIRMED'&&['sourceContractVerified','v2ExpectedPassed','comparableContext','readyPassed','policyValid','independentReproduction'].every(k=>evidence[k]===true)?'CONFIRMED':'NEEDS_REVIEW';}
