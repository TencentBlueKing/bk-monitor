import { readFile } from 'node:fs/promises';
export function upgradeLegacyRefMetadata(code) {
  return code.replace(/\brefInFor(?=\s*:)/g, 'ref_for').replace(/(['"])refInFor\1(?=\s*:)/g, '$1ref_for$1');
}
const isLegacyControl = id => /[/\\]bk-magic-vue[/\\](?:lib|dist)[/\\].*\.js(?:\?|$)/.test(id);
// Convert render metadata only, scoped to the remaining V2 controls in UI Dev.
export const legacyRefsVitePlugin = () => ({
  name: 'migration-legacy-ref-metadata',
  enforce: 'pre',
  transform(code, id) {
    if (isLegacyControl(id)) return { code: upgradeLegacyRefMetadata(code), map: null };
  },
});
export const legacyRefsEsbuildPlugin = () => ({
  name: 'migration-legacy-ref-metadata',
  setup(build) {
    build.onLoad({ filter: /\.js$/ }, async args => {
      if (!isLegacyControl(args.path)) return;
      return { contents: upgradeLegacyRefMetadata(await readFile(args.path, 'utf8')), loader: 'js' };
    });
  },
});
