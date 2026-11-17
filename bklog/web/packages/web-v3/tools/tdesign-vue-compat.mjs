/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { resolve } from 'node:path';
import { readFile } from 'node:fs/promises';

export const isTDesignVueModule = id => /\/tdesign-vue-next\/(?:es|esm)\//.test(id.replaceAll('\\', '/'));
const facade = root => resolve(root, 'src/platform/compat/tdesign/native-vue-runtime.ts');
export const transformTDesignVueSource = (code, root) =>
  code.replace(/from\s*(['"])vue\1/g, `from ${JSON.stringify(facade(root))}`);

// Scope compatibility metadata to components actually imported by the app.
// Iterating the package namespace retains every public component and icon.
export function tdesignVueCompatVitePlugin(root) {
  return { name: 'tdesign-vue-compat', enforce: 'pre', transform(code, id) {
    if (!isTDesignVueModule(id)) return;
    const contents = transformTDesignVueSource(code, root);
    return contents === code ? undefined : { code: contents, map: null };
  } };
}
export function tdesignVueCompatEsbuildPlugin(root) {
  return { name: 'tdesign-vue-compat', setup(build) {
    build.onLoad({ filter: /tdesign-vue-next[\/\\](?:es|esm)[\/\\].*\.(?:mjs|js)$/ }, async args => {
      if (!isTDesignVueModule(args.path)) return null;
      const source = await readFile(args.path, 'utf8');
      const contents = transformTDesignVueSource(source, root);
      return contents === source ? null : { contents, loader: 'js' };
    });
  } };
}
