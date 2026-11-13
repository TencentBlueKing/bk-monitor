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
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
export function monitorHostFixture(packageRoot) {
  const require=createRequire(resolve(packageRoot,'../web-v2/package.json'));
  return {
    name:'monitor-host-contract-fixture',apply:'serve',
    resolveId(id) {
      if(id==='/__fixtures__/collection-create-ui.tsx')return resolve(packageRoot,'fixtures/collection-create-ui.tsx');
      if(id==='/__fixtures__/list-skeleton-contract.tsx')return resolve(packageRoot,'fixtures/list-skeleton-contract.tsx');
      if(id==='/__fixtures__/date-picker-contract.ts')return resolve(packageRoot,'fixtures/date-picker-contract.ts');
      if(id==='/__fixtures__/sdk-vue3-contract.tsx')return resolve(packageRoot,'fixtures/sdk-vue3-contract.tsx');
      if(id==='/__fixtures__/first-render-contract.tsx')return resolve(packageRoot,'fixtures/first-render-contract.tsx');
      if(id==='/__fixtures__/collection-label-contract.tsx')return resolve(packageRoot,'fixtures/collection-label-contract.tsx');
      if(id==='/__fixtures__/management-loading-contract.tsx')return resolve(packageRoot,'fixtures/management-loading-contract.tsx');
      if(id==='/__fixtures__/native-model-contract.ts')return resolve(packageRoot,'fixtures/native-model-contract.ts');
      if(id==='/__fixtures__/native-controls.ts')return resolve(packageRoot,'tests/browser/native-controls.ts');
      if(id==='/__fixtures__/state-i18n.ts')return resolve(packageRoot,'tests/browser/state-i18n.ts');
      if(id==='/__fixtures__/monitor-host.ts')return resolve(packageRoot,'tests/browser/monitor-host.ts');
      if(id==='/__fixtures__/vue2-runtime')return require.resolve('vue/dist/vue.runtime.esm.js');
    },
    configureServer(server) {
      server.middlewares.use(async(req,res,next)=>{
        const route=new URL(req.url||'/','http://localhost').pathname;
        if(route==='/__fixtures__/collection-create-ui') {
          const html=readFileSync(resolve(packageRoot,'fixtures/collection-create-ui.html'),'utf8');
          res.setHeader('Content-Type','text/html; charset=utf-8');
          res.end(await server.transformIndexHtml(req.url,html));return;
        }
        if(route==='/__fixtures__/list-skeleton-contract') {
          const html=readFileSync(resolve(packageRoot,'fixtures/list-skeleton-contract.html'),'utf8');
          res.setHeader('Content-Type','text/html; charset=utf-8');
          res.end(await server.transformIndexHtml(req.url,html));return;
        }
        if(route==='/__fixtures__/date-picker-contract') {
          const html=readFileSync(resolve(packageRoot,'fixtures/date-picker-contract.html'),'utf8');
          res.setHeader('Content-Type','text/html; charset=utf-8');
          res.end(await server.transformIndexHtml(req.url,html));return;
        }
        if(route==='/__fixtures__/sdk-user-directory') {
          const query=new URL(req.url,'http://localhost').searchParams;
          const callback=query.get('callback')||'';
          if(!/^[A-Za-z_$][\w$]*$/.test(callback)){res.statusCode=400;res.end();return;}
          const users=[{username:'synthetic.alex',display_name:'Synthetic Alpha'},{username:'synthetic.blair',display_name:'Synthetic Beta'}];
          const exact=query.get('exact_lookups')?.split(',');
          const keyword=query.get('fuzzy_lookups')||'';
          const results=users.filter(user=>exact?exact.includes(user.username):user.username.includes(keyword));
          res.setHeader('Content-Type','application/javascript');
          res.end(`${callback}(${JSON.stringify({code:0,data:{results}})});`);return;
        }
        if(!['/__fixtures__/sdk-vue3-contract','/__fixtures__/first-render-contract','/__fixtures__/monitor-host','/__fixtures__/state-i18n','/__fixtures__/native-controls','/__fixtures__/native-model-contract','/__fixtures__/collection-label-contract','/__fixtures__/management-loading-contract'].includes(route))return next();
        try {
          const html=readFileSync(resolve(packageRoot,route==='/__fixtures__/sdk-vue3-contract'?'fixtures/sdk-vue3-contract.html':route==='/__fixtures__/first-render-contract'?'fixtures/first-render-contract.html':route==='/__fixtures__/management-loading-contract'?'fixtures/management-loading-contract.html':route==='/__fixtures__/collection-label-contract'?'fixtures/collection-label-contract.html':route==='/__fixtures__/native-model-contract'?'fixtures/native-model-contract.html':route==='/__fixtures__/native-controls'?'tests/browser/native-controls.html':route==='/__fixtures__/state-i18n'?'tests/browser/state-i18n.html':'tests/browser/monitor-host.html'),'utf8');
          res.setHeader('Content-Type','text/html; charset=utf-8');
          res.end(await server.transformIndexHtml(req.url,html));
        }catch(error){next(error);}
      });
    },
  };
}
