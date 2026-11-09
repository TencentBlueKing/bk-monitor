/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
export function monitorHostFixture(packageRoot) {
  const require=createRequire(resolve(packageRoot,'../../package.json'));
  return {
    name:'monitor-host-contract-fixture',apply:'serve',
    resolveId(id) {
      if(id==='/__fixtures__/native-controls.ts')return resolve(packageRoot,'tests/browser/native-controls.ts');
      if(id==='/__fixtures__/state-i18n.ts')return resolve(packageRoot,'tests/browser/state-i18n.ts');
      if(id==='/__fixtures__/monitor-host.ts')return resolve(packageRoot,'tests/browser/monitor-host.ts');
      if(id==='/__fixtures__/vue2-runtime')return require.resolve('vue/dist/vue.runtime.esm.js');
    },
    configureServer(server) {
      server.middlewares.use(async(req,res,next)=>{
        const route=new URL(req.url||'/','http://localhost').pathname;
        if(!['/__fixtures__/monitor-host','/__fixtures__/state-i18n','/__fixtures__/native-controls'].includes(route))return next();
        try {
          const html=readFileSync(resolve(packageRoot,route==='/__fixtures__/native-controls'?'tests/browser/native-controls.html':route==='/__fixtures__/state-i18n'?'tests/browser/state-i18n.html':'tests/browser/monitor-host.html'),'utf8');
          res.setHeader('Content-Type','text/html; charset=utf-8');
          res.end(await server.transformIndexHtml(req.url,html));
        }catch(error){next(error);}
      });
    },
  };
}
