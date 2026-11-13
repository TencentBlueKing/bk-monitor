/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';
import { isNativeSdkModule, nativeSdkVueVitePlugin, nativeSdkVueEsbuildPlugin, patchUserLookupBatches, transformNativeSdkSource } from '../tools/native-sdk-vue.mjs';
const sdk=loadTypeScript(new URL('../src/platform/compat/native-sdk-vue.ts',import.meta.url),{'@vue/compat':Vue});
test('native SDK facade configures private component options and preserves the single Vue runtime',()=>{
  const render=()=>Vue.h('span','nested');
  const options={render,props:{value:String},compatConfig:{RENDER_FUNCTION:false}};
  const component=sdk.defineComponent(options);
  assert.equal(component.render,render);assert.equal(component.props,options.props);
  assert.deepEqual(component.compatConfig,{MODE:3,RENDER_FUNCTION:false,COMPONENT_V_MODEL:false,INSTANCE_ATTRS_CLASS_STYLE:false,ATTR_FALSE_VALUE:false,ATTR_ENUMERATED_COERCION:false});
  assert.equal(sdk.h,Vue.h);assert.equal(sdk.ref,Vue.ref);
  assert.equal(sdk.defineComponent(()=>()=>Vue.h('span')).compatConfig.MODE,3);
  const plain = sdk.configureNativeSdkComponent({ compatConfig: { COMPONENT_V_MODEL: 'suppress-warning' } });
  assert.equal(plain.compatConfig.COMPONENT_V_MODEL, false);
  assert.equal(plain.compatConfig.RENDER_FUNCTION, false);
});

test('compiled private SFC options disable legacy model conversion without changing render and props', () => {
  const original = { props: { modelValue: Array }, render() {} };
  const transformed = transformNativeSdkSource('const sfc = component.__vccOpts || component;', '/workspace');
  assert.match(transformed, /import.*configureNativeSdkComponent/);
  const result = new Function('__bklogConfigureSdk', 'component', transformed.replace(/^import[^\n]+\n/, '') + '\nreturn sfc;')(
    sdk.configureNativeSdkComponent, original,
  );
  assert.equal(result, original);
  assert.equal(result.compatConfig.COMPONENT_V_MODEL, false);
  assert.equal(result.render, original.render);
});
test('dev prebundle and production transforms are limited to official Vue3 SDK modules',()=>{
  const paths=['/deps/@blueking/bk-user-selector/vue3/index.es.min.js','/deps/@blueking/ai-blueking/dist/vue3/index.es.min.js'];
  const other=['/src/features/example.ts','/deps/bk-magic-vue/lib/select.js','/deps/bkui-vue/lib/popover/index.js','/deps/@blueking/date-picker/vue2/index.js'];
  const plugin=nativeSdkVueVitePlugin('/workspace');
  let resolver;nativeSdkVueEsbuildPlugin('/workspace').setup({onLoad(){},onResolve:(_,fn)=>{resolver=fn;}});
  for(const id of paths){assert.ok(isNativeSdkModule(id));assert.match(plugin.transform('import {h} from "vue";',id).code,/native-sdk-vue.ts/);assert.match(resolver({importer:id}).path,/native-sdk-vue.ts/);}
  for(const id of other){assert.equal(isNativeSdkModule(id),false);assert.equal(plugin.transform('import {h} from "vue";',id),undefined);assert.equal(resolver({importer:id}),undefined);}
});

test('official SDK user lookup retains the legacy 100-name batch limit without changing directory parameters', async () => {
  const {readFileSync}=await import('node:fs');
  const {createRequire}=await import('node:module');
  const require=createRequire(import.meta.url);
  const source=readFileSync(require.resolve('@blueking/bk-user-selector/vue3'),'utf8');
  const start=source.indexOf('const getUserList = async (url, params) => {');
  const end=source.indexOf('\n};',start)+3;
  assert.ok(start>0);
  const patched=patchUserLookupBatches(source.slice(start,end));
  assert.equal(patchUserLookupBatches(patched),patched);
  const calls=[];
  const lookup=new Function('jsonpRequest',patched+'\nreturn getUserList;')(async (url,{params})=>{
    calls.push({url,params});return {results:params.exact_lookups.split(',').map(username=>({username}))};
  });
  const names=Array.from({length:205},(_,i)=>`synthetic-${i}`);
  const users=await lookup('/synthetic-directory',{userIds:names});
  assert.deepEqual(calls.map(call=>call.params.exact_lookups.split(',').length),[100,100,5]);
  assert.deepEqual(users.map(user=>user.username),names);
  assert.ok(calls.every(call=>call.params.app_code==='bk-magicbox'&&call.params.page==='1'));
});
