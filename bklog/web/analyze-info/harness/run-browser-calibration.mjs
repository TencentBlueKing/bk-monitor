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
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';
import { captureUi, waitForUiIdle } from './ui-snapshot.mjs';
import { compareSemanticNodes, requestPolicy, requestSignature, parseStream, evaluateRun } from './protocol.mjs';
const require=createRequire(new URL('../../packages/web-v3/package.json',import.meta.url));
const {chromium,expect}=require('@playwright/test');
const out=fileURLToPath(new URL('../runs/calibration/browser/',import.meta.url));mkdirSync(out,{recursive:true});
const html=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>
body{font:14px Arial;margin:20px}button,input{font:inherit}#nav{position:relative;z-index:1;width:100px;height:40px}#cover{position:absolute;z-index:100;left:20px;top:20px;width:100px;height:40px;background:#333;display:none}#low{position:absolute;left:20px;top:20px;z-index:0}#low div{position:absolute;width:100px;height:40px;z-index:99999;background:#bbb}section{margin-top:20px}label{display:block}#panel{width:180px}#duplicate button{margin:10px}
</style><body><button id="nav" aria-label="日志采集" aria-expanded="false">采</button><div id="cover"></div><div id="low" hidden><div></div></div>
<section><label>结果<input id="panel" readonly value="initial"></label><button id="update">更新现有面板</button><button id="slow">慢查询</button><button id="write">写入</button><button id="a">Read A</button><button id="b">Read B</button><button id="stream">流查询</button><button id="wrong">错误导航</button><button id="passive">探针</button><output id="probe"></output></section>
<section id="duplicate"><form data-scope="A"><button type="button">保存</button></form><form data-scope="B"><button type="button">保存</button></form><output id="saved"></output></section>
<script type="module">import{observeCall}from'/observer.mjs';
const panel=document.querySelector('#panel');const read=async(path,body={})=>{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();panel.value=d.value;return d;};
document.querySelector('#update').onclick=()=>read('/api/read/');document.querySelector('#slow').onclick=()=>read('/api/slow/');document.querySelector('#write').onclick=()=>read('/api/write/').catch(()=>{});
document.querySelector('#a').onclick=()=>read('/api/multiple/',{value:'A'});document.querySelector('#b').onclick=()=>read('/api/multiple/',{value:'B'});
document.querySelector('#stream').onclick=async()=>{const r=await fetch('/api/stream/');const t=await r.text();panel.value=String(t.trim().split('\\n').length);};
document.querySelector('#wrong').onclick=()=>location.hash='/unexpected';
document.querySelector('#passive').onclick=async()=>{const p=Promise.resolve(3),r=observeCall(()=>p,[],{enabled:true});document.querySelector('#probe').textContent=String(r===p)+'|'+await r;};
document.querySelectorAll('form button').forEach(b=>b.onclick=()=>document.querySelector('#saved').textContent=b.closest('form').dataset.scope);
</script></body></html>`;
let writes=0,requestCounter=0;
const server=createServer(async(req,res)=>{
 const path=new URL(req.url,'http://appdev.woa.com').pathname;
 if(path==='/observer.mjs'){res.writeHead(200,{'Content-Type':'text/javascript'});res.end(readFileSync(new URL('./observer.mjs',import.meta.url)));return;}
 if(!path.startsWith('/api/')){res.writeHead(200,{'Content-Type':'text/html'});res.end(html);return;}
 let raw='';for await(const chunk of req)raw+=chunk;
 if(path==='/api/write/')writes++;
 if(path==='/api/slow/')await new Promise(r=>setTimeout(r,2200));
 if(path==='/api/multiple/'&&JSON.parse(raw||'{}').value==='A')await new Promise(r=>setTimeout(r,80));
 if(path==='/api/stream/'){res.writeHead(200,{'Content-Type':'application/x-ndjson'});for(let i=0;i<27;i++)res.write(JSON.stringify({index:i})+'\n');res.end();return;}
 res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({value:path==='/api/slow/'?'slow-ready':path==='/api/multiple/'?JSON.parse(raw).value:'updated',request:++requestCounter}));
});
const source={sha256:'controlled-calibration-source'},rules=['/api/read/','/api/slow/','/api/multiple/','/api/stream/'].map(path=>({id:path,method:path==='/api/stream/'?'GET':'POST',path,semantics:'READ',source,reviewed:true,rationale:'controlled fixture read'}));rules.push({id:'write',method:'POST',path:'/api/write/',semantics:'WRITE',source,reviewed:true,rationale:'controlled fixture write'});
const results=[];let browser;
try{
 await new Promise((yes,no)=>{server.once('error',no);server.listen(0,'0.0.0.0',yes);});
 const base=`http://appdev.woa.com:${server.address().port}`;
 browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 async function one(id,run){const context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage(),blocks=[];try{
  await context.route('**/api/**',async route=>{const request=route.request(),decision=requestPolicy({method:request.method(),url:request.url()},rules);if(decision.decision==='ALLOW')await route.continue();else{blocks.push(decision);await route.abort('blockedbyclient');}});
  await page.goto(base+'/calibration',{waitUntil:'domcontentloaded'});await expect(page.getByRole('button',{name:'更新现有面板',exact:true})).toBeEnabled();
  await run(page,blocks);await page.screenshot({path:resolve(out,id+'.png'),fullPage:true});results.push({id,status:'PASSED'});
 }catch(e){results.push({id,status:'FAILED',error:String(e.message)});try{await page.screenshot({path:resolve(out,id+'-failure.png')});}catch{}}finally{await context.close();}}
 const binding=[{semanticId:'nav.collection',selector:'#nav'}];
 await one('missing-control',async page=>{const before=await page.evaluate(captureUi,{bindings:binding});await page.locator('#nav').evaluate(e=>e.remove());const after=await page.evaluate(captureUi,{bindings:binding});assert.equal(after.errors[0].kind,'MISSING_TARGET');assert.equal(compareSemanticNodes(before.nodes,after.nodes)[0].kind,'MISSING');});
 await one('framework-wrapper',async page=>{const before=await page.evaluate(captureUi,{bindings:binding});await page.locator('#nav').evaluate(e=>{const p=document.createElement('div');p.style.display='contents';e.replaceWith(p);p.append(e);e.className='different-framework-class';});const after=await page.evaluate(captureUi,{bindings:binding});assert.deepEqual(compareSemanticNodes(before.nodes,after.nodes),[]);});
 await one('collapsed-navigation',async page=>{await page.locator('#nav').evaluate(e=>e.textContent='');const s=await page.evaluate(captureUi,{bindings:binding});assert.equal(s.nodes[0].name,'日志采集');assert.equal(s.nodes[0].occluded,false);await page.getByRole('button',{name:'日志采集',exact:true}).click();});
 await one('slow-readiness',async page=>{const start=Date.now();await page.getByRole('button',{name:'慢查询',exact:true}).click();await expect(page.locator('#panel')).toHaveValue('slow-ready',{timeout:6000});assert.ok(Date.now()-start>=2000);});
 await one('post-read-and-blocked-write',async(page,blocks)=>{await page.locator('#update').click();await expect(page.locator('#panel')).toHaveValue('updated');const pending=page.waitForEvent('requestfailed',r=>new URL(r.url()).pathname==='/api/write/');await page.locator('#write').click();await pending;assert.equal(blocks[0].reason,'WRITE_NOT_AUTHORIZED');assert.equal(writes,0);});
 await one('existing-panel-update',async page=>{const count=await page.locator('body *').count();await page.locator('#update').click();await expect(page.locator('#panel')).toHaveValue('updated');assert.equal(await page.locator('body *').count(),count);});
 await one('portal-occlusion',async page=>{await page.locator('#cover').evaluate(e=>e.style.display='block');const blocked=await page.evaluate(captureUi,{bindings:binding});assert.equal(blocked.nodes[0].occluded,true);await page.locator('#cover').evaluate(e=>e.style.display='none');await page.locator('#low').evaluate(e=>e.hidden=false);const lower=await page.evaluate(captureUi,{bindings:binding});assert.equal(lower.nodes[0].occluded,false);assert.ok(lower.nodes[0].hitTests.some(p=>p.hit));});
 await one('request-context-isolation',async page=>{const requests=[];page.on('request',r=>{if(new URL(r.url()).pathname==='/api/multiple/')requests.push({url:r.url(),method:r.method(),body:r.postData()});});await page.locator('#a').click();await page.locator('#b').click();await expect(page.locator('#panel')).toHaveValue('A');assert.equal(requests.length,2);assert.notEqual(requestSignature(requests[0]),requestSignature(requests[1]));});
 await one('stream-completeness',async page=>{const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/stream/');await page.locator('#stream').click();const r=await response;await r.finished();const stream=parseStream(await r.text(),{transportFinished:true});assert.equal(stream.chunks.length,27);assert.equal(stream.complete,true);await expect(page.locator('#panel')).toHaveValue('27');});
 await one('ambiguous-target',async page=>{assert.equal(await page.getByRole('button',{name:'保存',exact:true}).count(),2);const scoped=page.locator('form[data-scope="B"]').getByRole('button',{name:'保存',exact:true});assert.equal(await scoped.count(),1);await scoped.click();await expect(page.locator('#saved')).toHaveText('B');});
 await one('passive-probe',async page=>{await page.locator('#passive').click();await expect(page.locator('#probe')).toHaveText('true|3');});
 await one('wrong-route',async page=>{await page.locator('#wrong').click();await expect(page).toHaveURL(/#\/unexpected$/);const scenario={schemaVersion:1,id:'route',sourceDigest:'s',contextDigest:'c',sourceRefs:[{file:'fixture',symbol:'nav',sha256:'s'}],actions:[{id:'nav',target:{scope:'main',semanticId:'nav'},ready:[{id:'ready'}],expected:[{id:'effect'}]}]};const run={sourceDigest:'s',contextDigest:'c',fixtureDigest:'f',actions:[{id:'nav',routeMatched:new URL(page.url()).hash==='#/expected',targetMatches:1,ready:[{id:'ready',passed:true}],assertions:[{id:'effect',passed:true}]}]};assert.equal(evaluateRun({scenario,run,baseline:{complete:true,selfReplayPassed:true,fixtureDigest:'f'}}).outcome,'INVALID_RUN');});
 await one('finite-animation-readiness', async page => {
  await page.evaluate(() => {
   const element = document.createElement('div');element.id = 'animated';element.style.cssText = 'height:40px;width:120px;transform-origin:top';document.body.append(element);
   element.animate([{transform:'scaleY(.1)'},{transform:'scaleY(1)'}], {duration:250,fill:'forwards'});
   element.animate([{opacity:.9},{opacity:1}], {duration:800,iterations:Infinity});
  });
  await waitForUiIdle(page.locator('#animated'));
  assert.equal((await page.locator('#animated').boundingBox()).height,40);
 });
 await one('semantic-name-binding', async page => {
  await page.evaluate(() => {const element=document.createElement('div');element.id='dialog';element.innerHTML='<h2>确认类型</h2><footer>下一步 取消</footer>';document.body.append(element);});
  const bindings=[{semanticId:'dialog',selector:'#dialog',nameSelector:'h2'}];
  const before=await page.evaluate(captureUi,{bindings});
  await page.locator('#dialog footer').evaluate(element=>element.textContent='取消 下一步');
  const after=await page.evaluate(captureUi,{bindings});
  assert.equal(before.nodes[0].name,'确认类型');assert.deepEqual(compareSemanticNodes(before.nodes,after.nodes),[]);
  const invalid=await page.evaluate(captureUi,{bindings:[{semanticId:'dialog',selector:'#dialog',nameSelector:'.missing'}]});
  assert.equal(invalid.errors[0].kind,'INVALID_NAME_TARGET');
 });
 await one('hidden-descendant-name', async page => {
  await page.evaluate(() => {const link=document.createElement('a');link.id='collapsed-link';link.href='#';link.style.cssText='display:block;width:120px;height:32px';link.innerHTML='<span style="display:none">隐藏菜单文字</span><span aria-hidden="true">图标占位</span>';document.body.append(link);});
  const snapshot=await page.evaluate(captureUi,{bindings:[{semanticId:'navigation.link',selector:'#collapsed-link'}]});
  assert.equal(snapshot.nodes[0].role,'link');assert.equal(snapshot.nodes[0].name,'');
  await page.locator('#collapsed-link span').first().evaluate(element=>element.style.display='');
  const expanded=await page.evaluate(captureUi,{bindings:[{semanticId:'navigation.link',selector:'#collapsed-link'}]});
  assert.equal(expanded.nodes[0].name,'隐藏菜单文字');
 });
 const spec=JSON.parse(readFileSync(new URL('../spec/calibration-required.json',import.meta.url),'utf8')),missing=spec.browser.required.filter(id=>!results.some(r=>r.id===id&&r.status==='PASSED'));
 const report={schemaVersion:1,scope:'CONTROLLED_FIXTURE_NOT_PRODUCT_ACCEPTANCE',baseUrl:base,status:missing.length?'FAILED':'BROWSER_CALIBRATION_PASSED',results,missing,backendWrites:writes};writeFileSync(resolve(out,'result.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));if(missing.length)process.exitCode=1;
}catch(e){const report={status:'BLOCKED_ENVIRONMENT',error:String(e.message),results};writeFileSync(resolve(out,'result.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));process.exitCode=1;}finally{await browser?.close();await new Promise(r=>server.close(r));}
