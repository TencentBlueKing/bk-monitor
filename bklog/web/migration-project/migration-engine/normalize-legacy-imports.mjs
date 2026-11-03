import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../..', import.meta.url));
const req = createRequire(root + '/packages/web-v2/package.json');
const { parse } = req('@babel/parser');
const { parse: parseSfc } = req('@vue/compiler-sfc');
const changes = [];
function edit(s) {
  if (!/from ['"]bk-magic-vue['"]/.test(s)) return { code: s, count: 0 };
  const ast = parse(s, { sourceType: 'module', plugins: ['typescript', 'jsx', 'decorators-legacy'] });
  const edits = [];
  for (const n of ast.program.body) {
    if (n.type !== 'ImportDeclaration' || n.source.value !== 'bk-magic-vue' || n.importKind === 'type') continue;
    for (const spec of n.specifiers) {
      if (spec.type !== 'ImportSpecifier' || spec.importKind === 'type' || !/^[A-Z]/.test(spec.imported.name)) continue;
      edits.push({ start: spec.start, end: spec.end, text: `bk${spec.imported.name} as ${spec.local.name}` });
    }
  }
  for (const e of edits.sort((a, b) => b.start - a.start)) s = s.slice(0, e.start) + e.text + s.slice(e.end);
  return { code: s, count: edits.length };
}
function go(dir) {
  for (const ent of readdirSync(dir, { withFileTypes: true })) {
    const p = dir + '/' + ent.name;
    if (ent.isDirectory()) {
      go(p);
      continue;
    }
    if (!/\.(?:[jt]sx?|vue)$/.test(p)) continue;
    let s = readFileSync(p, 'utf8');
    let result;
    if (p.endsWith('.vue')) {
      const d = parseSfc(s).descriptor;
      let count = 0;
      for (const b of [d.scriptSetup, d.script]
        .filter(Boolean)
        .sort((a, b) => b.loc.start.offset - a.loc.start.offset)) {
        const r = edit(b.content);
        if (r.count) {
          s = s.slice(0, b.loc.start.offset) + r.code + s.slice(b.loc.end.offset);
          count += r.count;
        }
      }
      result = { code: s, count };
    } else result = edit(s);
    if (result.count) {
      writeFileSync(p, result.code);
      changes.push({ file: p.slice((root + '/packages/web-v3/src-native/').length), count: result.count });
    }
  }
}
go(root + '/packages/web-v3/src-native');
writeFileSync('/tmp/bklog-business-imports.json', JSON.stringify(changes, null, 2));
console.log({ files: changes.length, imports: changes.reduce((n, r) => n + r.count, 0) });
