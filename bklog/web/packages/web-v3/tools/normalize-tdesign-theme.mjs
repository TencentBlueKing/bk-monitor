/** Normalize common visuals, without changing selectors, layout or event code. */
import { readFileSync, writeFileSync, readdirSync, mkdirSync, existsSync } from 'node:fs';
import { resolve, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { normalizeStyle } from './tdesign-style-source.mjs';
export function styleSections(file, text) {
  if (file.endsWith('.scss')) return [{ start: 0, end: text.length, content: text }];
  if (!file.endsWith('.vue')) return [];
  return [...text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map(match => ({ start: match.index + match[0].indexOf('>') + 1, end: match.index + match[0].lastIndexOf('</style>'), content: match[1] }));
}
const project = fileURLToPath(new URL('../', import.meta.url)), source = resolve(project, 'src');
const write = process.argv.includes('--write');
const archive = process.argv.find(arg => arg.startsWith('--archive='))?.slice('--archive='.length);
if (write && (!archive || !resolve(archive).startsWith('/private/tmp/'))) throw new Error('Writing requires an external /private/tmp source archive');
const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? walk(resolve(dir, entry.name)) : entry.isFile() ? [resolve(dir, entry.name)] : []);
const records = [];
for (const path of walk(source)) {
  const file = relative(source, path);
  if (!/^(features|shared\/ui|shared\/global|shared\/styles|app\/shell)\//.test(file)) continue;
  if (!/\.(scss|vue)$/.test(path)) continue;
  const original = readFileSync(path, 'utf8');
  let output = original, count = 0;
  for (const section of styleSections(file, original).toReversed()) {
    const result = normalizeStyle(section.content);
    count += result.count;
    output = output.slice(0, section.start) + result.output + output.slice(section.end);
  }
  if (!count) continue;
  records.push({ file, declarations: count });
  if (write) {
    const target = resolve(archive, file); mkdirSync(dirname(target), { recursive: true });
    if (!existsSync(target)) writeFileSync(target, original); writeFileSync(path, output);
  }
}
console.log(JSON.stringify({ mode: write ? 'written' : 'dry-run', files: records.length, declarations: records.reduce((sum, file) => sum + file.declarations, 0), records }, null, 2));
