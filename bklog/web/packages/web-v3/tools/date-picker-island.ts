import { build } from 'esbuild';
import type { Plugin } from 'vite';
import { resolve } from 'node:path';
const publicId = 'virtual:bklog-native-date-picker';
const privateId = '\0' + publicId;
/** Bundle the complete SDK graph, including TDesign adapters, on native Vue3. */
export async function bundleDatePicker(root: string) {
  const result = await build({
    entryPoints: [resolve(root, 'src/platform/sdk/date-picker/native-entry.ts')],
    bundle: true,
    write: false,
    format: 'esm',
    platform: 'browser',
    target: 'es2022',
    minify: true,
    metafile: true,
    define: {
      'process.env.NODE_ENV': '"production"',
      __VUE_OPTIONS_API__: 'true',
      __VUE_PROD_DEVTOOLS__: 'false',
      __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
    },
    alias: {
      vue: resolve(root, 'node_modules/vue/dist/vue.runtime.esm-bundler.js'),
      'bkui-vue/lib/icon': resolve(root, 'src/platform/compat/tdesign/bkui-icons.ts'),
      'bkui-vue': resolve(root, 'src/platform/compat/tdesign/bkui-vue.ts'),
    },
    loader: { '.css': 'empty' },
  });
  const inputs = Object.keys(result.metafile.inputs);
  if (inputs.some((path) => path.includes('@vue/compat') || path.includes('vue-runtime.mjs')))
    throw new Error('DatePicker island unexpectedly imported the compatibility runtime');
  return { code: result.outputFiles[0].text, inputs };
}
export function datePickerIsland(root: string): Plugin {
  let pending: ReturnType<typeof bundleDatePicker> | undefined;
  return {
    name: 'bklog-native-date-picker',
    enforce: 'pre',
    resolveId(id) {
      if (id === publicId) return privateId;
    },
    async load(id) {
      if (id !== privateId) return;
      const result = await (pending ??= bundleDatePicker(root));
      for (const file of result.inputs) this.addWatchFile(resolve(root, file));
      return result.code;
    },
    watchChange() {
      pending = undefined;
    },
  };
}
