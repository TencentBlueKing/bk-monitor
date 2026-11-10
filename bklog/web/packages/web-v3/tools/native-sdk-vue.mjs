/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { resolve } from 'node:path';
export const isNativeSdkModule = id =>
  /\/@blueking\/(?:date-picker|bk-user-selector)\/vue3\//.test(id.replaceAll('\\', '/'));
const facade = root => resolve(root,'src/platform/compat/native-sdk-vue.ts');
/** Restrict native component options to the official Vue3 SDK dependency graph. */
export function nativeSdkVueVitePlugin(root) {
  return { name:'native-sdk-vue',enforce:'pre',transform(code,id) {
    if(!isNativeSdkModule(id))return;
    return {code:code.replace(/from\s*(['"])vue\1/g,`from ${JSON.stringify(facade(root))}`),map:null};
  }};
}
export function nativeSdkVueEsbuildPlugin(root) {
  return {name:'native-sdk-vue',setup(build) {
    build.onResolve({filter:/^vue$/},args=>isNativeSdkModule(args.importer)?{path:facade(root)}:undefined);
  }};
}
