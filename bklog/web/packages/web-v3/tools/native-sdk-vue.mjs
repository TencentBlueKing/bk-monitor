/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { resolve } from 'node:path';
import { readFile } from 'node:fs/promises';
export const isNativeSdkModule = id =>
  /\/@blueking\/(?:bk-user-selector\/vue3|ai-blueking\/dist\/vue3)\//.test(id.replaceAll('\\', '/'));
/** Preserve the old directory API's 100-name limit for SDK lookup and paste. */
export function patchUserLookupBatches(code) {
  const anchor = 'const getUserList = async (url, params) => {';
  if (!code.includes(anchor) || code.includes('bklog-sdk-lookup-batches')) return code;
  return code.replace(anchor, `${anchor}
    /* bklog-sdk-lookup-batches */
    if ((params.userIds?.length || 0) > 100) {
      const batches = [];
      for (let start = 0; start < params.userIds.length; start += 100)
        batches.push(getUserList(url, { ...params, userIds: params.userIds.slice(start, start + 100) }));
      return (await Promise.all(batches)).flat();
    }`);
}
const facade = root => resolve(root,'src/platform/compat/native-sdk-vue.ts');
export function transformNativeSdkSource(code, root) {
  let configureSfc = false;
  code = code.replace(/const ([\w$]+) = ([\w$]+)\.__vccOpts \|\| \2;/g, (_match, target, component) => {
    configureSfc = true;
    return `const ${target} = __bklogConfigureSdk(${component}.__vccOpts || ${component});`;
  });
  if(configureSfc) code = `import { configureNativeSdkComponent as __bklogConfigureSdk } from ${JSON.stringify(facade(root))};\n${code}`;
  return code.replace(/from\s*(['"])vue\1/g,`from ${JSON.stringify(facade(root))}`);
}
/** Restrict native component options to the official Vue3 SDK dependency graph. */
export function nativeSdkVueVitePlugin(root) {
  return { name:'native-sdk-vue',enforce:'pre',transform(code,id) {
    if(!isNativeSdkModule(id))return;
    if(id.includes('/bk-user-selector/')) code = patchUserLookupBatches(code);
    return {code:transformNativeSdkSource(code, root),map:null};
  }};
}
export function nativeSdkVueEsbuildPlugin(root) {
  return {name:'native-sdk-vue',setup(build) {
    build.onLoad({filter:/\.(?:mjs|js)$/}, async args => {
      if(!isNativeSdkModule(args.path)) return;
      let code = await readFile(args.path, 'utf8');
      if(args.path.includes('/bk-user-selector/')) code = patchUserLookupBatches(code);
      return { contents: transformNativeSdkSource(code, root), loader: 'js' };
    });
    build.onResolve({filter:/^vue$/},args=>isNativeSdkModule(args.importer)?{path:facade(root)}:undefined);
  }};
}
