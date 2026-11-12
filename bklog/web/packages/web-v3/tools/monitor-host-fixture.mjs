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
  const require=createRequire(resolve(packageRoot,'../../package.json'));
  return {
    name:'monitor-host-contract-fixture',apply:'serve',
    resolveId(id) {
      if(id==='/__fixtures__/collection-label-contract.tsx')return resolve(packageRoot,'fixtures/collection-label-contract.tsx');
      if(id==='/__fixtures__/native-model-contract.ts')return resolve(packageRoot,'fixtures/native-model-contract.ts');
      if(id==='/__fixtures__/native-controls.ts')return resolve(packageRoot,'tests/browser/native-controls.ts');
      if(id==='/__fixtures__/state-i18n.ts')return resolve(packageRoot,'tests/browser/state-i18n.ts');
      if(id==='/__fixtures__/monitor-host.ts')return resolve(packageRoot,'tests/browser/monitor-host.ts');
      if(id==='/__fixtures__/vue2-runtime')return require.resolve('vue/dist/vue.runtime.esm.js');
    },
    configureServer(server) {
      server.middlewares.use(async(req,res,next)=>{
        const route=new URL(req.url||'/','http://localhost').pathname;
        if(!['/__fixtures__/monitor-host','/__fixtures__/state-i18n','/__fixtures__/native-controls','/__fixtures__/native-model-contract','/__fixtures__/collection-label-contract'].includes(route))return next();
        try {
          const html=readFileSync(resolve(packageRoot,route==='/__fixtures__/collection-label-contract'?'fixtures/collection-label-contract.html':route==='/__fixtures__/native-model-contract'?'fixtures/native-model-contract.html':route==='/__fixtures__/native-controls'?'tests/browser/native-controls.html':route==='/__fixtures__/state-i18n'?'tests/browser/state-i18n.html':'tests/browser/monitor-host.html'),'utf8');
          res.setHeader('Content-Type','text/html; charset=utf-8');
          res.end(await server.transformIndexHtml(req.url,html));
        }catch(error){next(error);}
      });
    },
  };
}
