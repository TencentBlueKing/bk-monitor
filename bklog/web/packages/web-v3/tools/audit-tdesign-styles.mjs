/** Source-only style inventory. Never reads runtime evidence or business data. */
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = join(project, 'src');
function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name);
    return entry.isDirectory() ? walk(path) : entry.isFile() ? [path] : [];
  });
}
function inspect(path, kind, text) {
  const clean = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
  const classes = clean.match(/\.t-[\w-]+/g) || [];
  const tokens = [...clean.matchAll(/(--td-[\w-]+)\s*:/g)].map(match => match[1]);
  if (!classes.length && !tokens.length) return null;
  const file = relative(source, path).replaceAll('\\', '/');
  return {
    file, kind, module: file.split('/').slice(0, 2).join('/'),
    classReferences: classes.length,
    classes: [...new Set(classes)].sort(),
    componentFamilies: [...new Set(classes.map(value => value.split(/__|--/)[0]))].sort(),
    declaredTokens: [...new Set(tokens)].sort(),
    // Count all important declarations in a matched file, not only TDesign rules.
    importantInFile: (clean.match(/!important/g) || []).length,
  };
}
const files = walk(source).flatMap(path => {
  if (path.endsWith('.scss')) return [inspect(path, 'scss', readFileSync(path, 'utf8'))].filter(Boolean);
  if (path.endsWith('.vue')) {
    const styles = [...readFileSync(path, 'utf8').matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map(match => match[1]).join('\n');
    return [inspect(path, 'vue-style', styles)].filter(Boolean);
  }
  return [];
}).sort((a, b) => a.file.localeCompare(b.file));
const scss = files.filter(item => item.kind === 'scss' && item.classReferences);
const modules = {}, families = {};
for (const file of scss) {
  modules[file.module] = (modules[file.module] || 0) + 1;
  for (const family of file.componentFamilies) families[family] = (families[family] || 0) + 1;
}
const library = resolve(dirname(fileURLToPath(import.meta.resolve('tdesign-vue-next/package.json'))));
const css = walk(join(library, 'es')).filter(path => path.endsWith('.css')).map(path => readFileSync(path, 'utf8')).join('\n');
const usedTokens = new Set([...css.matchAll(/var\((--td-[\w-]+)/g)].map(match => match[1]));
const themeTokens = [...new Set(files.filter(file => file.file.startsWith('shared/styles/theme/')).flatMap(file => file.declaredTokens))].sort();
console.log(JSON.stringify({
  schemaVersion: 1,
  scope: 'Source SCSS and Vue style blocks only; no runtime data; lexical inventory, not cascade or reachability proof.',
  tdesignVersion: JSON.parse(readFileSync(join(library, 'package.json'), 'utf8')).version,
  summary: {
    scssFilesWithClasses: scss.length,
    scssClassReferences: scss.reduce((sum, file) => sum + file.classReferences, 0),
    importantInMatchedScssFiles: scss.reduce((sum, file) => sum + file.importantInFile, 0),
    vueStyleFilesWithClasses: files.filter(file => file.kind === 'vue-style' && file.classReferences).length,
    modules, families,
    themeDeclaredTokens: themeTokens.length,
    themeTokensWithoutInstalledCssConsumer: themeTokens.filter(token => !usedTokens.has(token)),
  }, files,
}, null, 2));
