import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../..', import.meta.url));
const req = createRequire(root + '/package.json');
const { parse } = req('@babel/parser');
const traverse = req('@babel/traverse').default;
const { parse: parseSfc } = req('@vue/compiler-sfc');
const { baseParse } = req('@vue/compiler-dom');
const changes = [];
function js(s) {
  const edits = [];
  traverse(parse(s, { sourceType: 'module', plugins: ['typescript', 'jsx', 'decorators-legacy'] }), {
    JSXOpeningElement({ node }) {
      if (!['TableColumn', 'bkTableColumn', 'bk-table-column'].includes(node.name.name)) return;
      const attrs = node.attributes;
      if (attrs.some(x => x.name?.name === 'nativeCellSlot')) return;
      const slots = attrs.find(x => x.name?.name === 'v-slots')?.value?.expression;
      if (
        slots &&
        (slots.type !== 'ObjectExpression' ||
          slots.properties.some(p => p.type === 'ObjectProperty' && (p.key.name || p.key.value) === 'default'))
      )
        edits.push({ at: node.name.end, text: ' nativeCellSlot={true}' });
    },
  });
  for (const e of edits.sort((a, b) => b.at - a.at)) s = s.slice(0, e.at) + e.text + s.slice(e.at);
  return { code: s, count: edits.length };
}
function go(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = dir + '/' + e.name;
    if (e.isDirectory()) {
      go(p);
      continue;
    }
    if (!/\.(?:tsx|jsx|vue)$/.test(p)) continue;
    let s = readFileSync(p, 'utf8');
    let count = 0;
    if (p.endsWith('.vue')) {
      const d = parseSfc(s).descriptor;
      const t = d.template;
      if (t) {
        const edits = [];
        function walk(n) {
          if (
            n.type === 1 &&
            ['bk-table-column', 'TableColumn'].includes(n.tag) &&
            !n.props.some(p => p.name === 'native-cell-slot') &&
            n.children.some(
              c =>
                c.type === 1 &&
                c.tag === 'template' &&
                c.props.some(
                  p => p.type === 7 && p.name === 'slot' && p.exp && (!p.arg || p.arg.content === 'default'),
                ),
            )
          )
            edits.push({ at: t.loc.start.offset + n.loc.start.offset + 1 + n.tag.length, text: ' native-cell-slot' });
          for (const c of n.children || []) walk(c);
        }
        walk(baseParse(t.content));
        for (const e of edits.sort((a, b) => b.at - a.at)) s = s.slice(0, e.at) + e.text + s.slice(e.at);
        count += edits.length;
      }
    } else {
      const r = js(s);
      s = r.code;
      count = r.count;
    }
    if (count) {
      writeFileSync(p, s);
      changes.push({ file: p.slice((root + '/packages/web-v3/src-native/').length), count });
    }
  }
}
go(root + '/packages/web-v3/src-native');
writeFileSync('/tmp/bklog-business-cell-slots.json', JSON.stringify(changes, null, 2));
console.log({ files: changes.length, columns: changes.reduce((s, c) => s + c.count, 0) });
