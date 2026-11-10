/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import fs from 'node:fs';
import { resolve, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { parse } from '@vue/compiler-sfc';
const root = fileURLToPath(new URL('../', import.meta.url));
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(x => x.isDirectory() ? walk(resolve(dir, x.name)) : [resolve(dir, x.name)]);
const theme = expression => {
  const value = expression.replace(/^['"]|['"]$/g, '');
  return /^(success|warning|error|info|loading|question)$/.test(value) ? JSON.stringify(value) : /^['"]/.test(expression) ? '"info"' : expression;
};
export function migrateButtonFeedback(source, filename) {
  const edits = [], skipped = []; let buttons = 0, messages = 0;
  const put = (start, end, text) => edits.push({ start, end, text });
  const descriptor = filename.endsWith('.vue') ? parse(source).descriptor : null;
  const blocks = descriptor ? [descriptor.script, descriptor.scriptSetup].filter(Boolean).map(s => ({text:s.content, offset:s.loc.start.offset})) : [{text:source, offset:0}];
  for (const block of blocks) {
    const ast = ts.createSourceFile(filename, block.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const buttonNames = new Set(['bk-button']); const messageNames = new Set();
    const imports = []; const native = new Set();
    for (const node of ast.statements) if (ts.isImportDeclaration(node) && /compat\/tdesign\/magic-controls/.test(node.moduleSpecifier.text)) {
      const elements = [...(node.importClause?.namedBindings?.elements || [])];
      for (const element of elements) {
        const name = (element.propertyName || element.name).text;
        if (name === 'bkButton') buttonNames.add(element.name.text);
        if (name === 'bkMessage') messageNames.add(element.name.text);
      }
      imports.push({node, elements});
    }
    const pos = n => block.offset + n.getStart(ast), end = n => block.offset + n.end;
    const jsxAttr = attr => !attr.initializer ? 'true' : ts.isJsxExpression(attr.initializer) ? attr.initializer.expression?.getText(ast) || 'true' : attr.initializer.getText(ast);
    const visit = node => {
      if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && buttonNames.has(node.tagName.getText(ast))) {
        buttons++;
        if (node.tagName.getText(ast) === 'bk-button') { put(pos(node.tagName), end(node.tagName), 'TButton'); native.add('Button as TButton'); }
        const props = [...node.attributes.properties].filter(ts.isJsxAttribute);
        const text = props.find(p => p.name.getText(ast) === 'text'), outline = props.find(p => p.name.getText(ast) === 'outline');
        for (const attr of props) {
          const name = attr.name.getText(ast), value = jsxAttr(attr);
          if (name === 'text' || name === 'outline') put(pos(attr), end(attr), '');
          if (name === 'theme' && /^['"]dark['"]$/.test(value)) put(pos(attr.initializer), end(attr.initializer), '"default"');
          if (name === 'ext-cls') {
            const cls = props.find(p => p.name.getText(ast) === 'class');
            if (cls) { put(pos(cls.initializer), end(cls.initializer), `{[${jsxAttr(cls)}, ${value}]}`); put(pos(attr), end(attr), ''); }
            else put(pos(attr.name), end(attr.name), 'class');
          }
          if (name === 'icon') put(pos(attr), end(attr), `icon={() => <span class={\`bk-icon icon-\${${value}}\`} />}`);
          if (name === 'title') put(pos(attr), end(attr), `{...({ title: ${value} } satisfies import('vue').HTMLAttributes)}`);
          if (name === 'onclick') put(pos(attr.name), end(attr.name), 'onClick');
        }
        if (text || outline) {
          const fallback = outline ? `(${jsxAttr(outline)}) ? 'outline' : 'base'` : `'base'`;
          const value = text ? `(${jsxAttr(text)}) ? 'text' : (${fallback})` : fallback;
          put(block.offset + node.attributes.end, block.offset + node.attributes.end, ` variant={${value}}`);
        }
      }
      if (ts.isJsxClosingElement(node) && node.tagName.getText(ast) === 'bk-button') put(pos(node.tagName), end(node.tagName), 'TButton');
      if (ts.isCallExpression(node) && (messageNames.has(node.expression.getText(ast)) || /\.\$bkMessage$/.test(node.expression.getText(ast)))) {
        const arg = node.arguments[0];
        if (!arg || !ts.isObjectLiteralExpression(arg)) { skipped.push({kind:'message',expression:node.getText(ast)}); return; }
        const names = arg.properties.map(p => p.name?.getText(ast));
        const unsupported = names.filter(n => !['message','content','theme','delay','zIndex'].includes(n));
        if (unsupported.length) { skipped.push({kind:'message',expression:node.getText(ast),unsupported}); return; }
        const properties = arg.properties.map(p => ({ name:p.name.getText(ast), value:ts.isShorthandPropertyAssignment(p) ? p.name.getText(ast) : p.initializer.getText(ast) }));
        const messageTheme = theme(properties.find(p => p.name === 'theme')?.value || "'info'");
        if (!/^['"]/.test(messageTheme) && !messageTheme.includes('?')) { skipped.push({kind:'message',expression:node.getText(ast),unsupported:['dynamic-theme']}); return; }
        const options = properties.filter(p => p.name !== 'theme').map(p => `${p.name==='message'?'content':p.name==='delay'?'duration':p.name}: ${p.value}`).join(', ');
        put(pos(node), end(node), `TDesignMessage(${messageTheme}, { ${options} })`); messages++; native.add('MessagePlugin as TDesignMessage');
      }
      ts.forEachChild(node, visit);
    };
    visit(ast);
    for (const {node,elements} of imports) {
      const retained = elements.filter(e => {
        const name = (e.propertyName || e.name).text;
        if (name === 'bkButton') { native.add(`Button as ${e.name.text}`); return false; }
        if (name === 'bkMessage') {
          // Keep an import only while a call with an unconverted richer contract remains.
          const identifier = e.name.text;
          if (skipped.some(x => x.expression?.startsWith(identifier+'('))) return true;
          return false;
        }
        return true;
      });
      if (retained.length !== elements.length) put(pos(node),end(node),retained.length ? `import ${node.importClause?.isTypeOnly?'type ':''}{ ${retained.map(e=>e.getText(ast)).join(', ')} } from ${node.moduleSpecifier.getText(ast)};` : '');
    }
    if (native.size) put(block.offset,block.offset,`\nimport { ${[...native].join(', ')} } from 'tdesign-vue-next';\n`);
  }
  if (descriptor?.template?.ast) {
    const visit = node => {
      if (node.type === 1 && node.tag === 'bk-button') {
        buttons++;
        const start=node.loc.start.offset, local=node.loc.source;
        put(start+1,start+1+node.tag.length,'t-button');
        const close=local.lastIndexOf('</bk-button'); if(close>=0) put(start+close+2,start+close+2+node.tag.length,'t-button');
        const props=node.props; const name=p=>p.type===6?p.name:p.arg?.content; const expression=p=>p.type===6 ? p.value ? JSON.stringify(p.value.content) : 'true' : p.exp?.content || 'true';
        const text=props.find(p=>name(p)==='text'), outline=props.find(p=>name(p)==='outline');
        for(const p of props) {
          const n=name(p), value=expression(p);
          if(n==='text'||n==='outline') put(p.loc.start.offset,p.loc.end.offset,'');
          if(n==='theme' && value==='"dark"') put(p.loc.start.offset,p.loc.end.offset,'theme="default"');
          if(n==='ext-cls') {
            const cls=props.find(p=>name(p)==='class');
            if(cls){put(cls.loc.start.offset,cls.loc.end.offset,`:class="[${expression(cls).replaceAll('"',"'")}, ${value.replaceAll('"',"'")}]"`);put(p.loc.start.offset,p.loc.end.offset,'');}
            else put(p.loc.start.offset,p.loc.end.offset,p.loc.source.replace('ext-cls','class'));
          }
          if(n==='icon') {
            put(p.loc.start.offset,p.loc.end.offset,'');
            const content=`<template #icon><span :class="\`bk-icon icon-\${${value.replaceAll('"',"'")}}\`"></span></template>`;
            const opening=local.indexOf('>');
            if(local[opening-1]==='/'){put(start+opening-1,start+opening+1,`>${content}</t-button>`);}else put(start+opening+1,start+opening+1,content);
          }
          if(p.type===7&&p.name==='on'&&p.modifiers.some(m=>(m.content||m)==='native')) put(p.loc.start.offset,p.loc.end.offset,p.loc.source.replace('.native',''));
        }
        if(text||outline) {
          const fallback=outline?`(${expression(outline)}) ? 'outline' : 'base'`:`'base'`;
          const value=text?`(${expression(text)}) ? 'text' : (${fallback})`:fallback;
          put(start+1+node.tag.length,start+1+node.tag.length,` :variant="${value.replaceAll('"',"'")}"`);
        }
      }
      for(const child of node.children||[])visit(child);
    };
    visit(descriptor.template.ast);
  }
  const sorted=edits.sort((a,b)=>b.start-a.start||b.end-a.end);
  for(let i=0;i<sorted.length-1;i++) if(sorted[i+1].end>sorted[i].start && sorted[i+1].start!==sorted[i].start) throw Error(`Overlapping edit: ${filename}`);
  let output=source;for(const e of sorted)output=output.slice(0,e.start)+e.text+output.slice(e.end);
  // CSS hooks refer to the native rendered button, not an old control class.
  output=output.replace(/\.bk-button(?![\w-])/g, '.t-button');
  return {output,buttons,messages,skipped};
}
if (process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const report={files:[],buttons:0,messages:0,skipped:[]};
  for(const file of walk(resolve(root,'src')).filter(f=>/\.(vue|[jt]sx?)$/.test(f)&&!f.includes('/platform/compat/')&&!f.endsWith('.d.ts'))) {
    const source=fs.readFileSync(file,'utf8');const result=migrateButtonFeedback(source,file);
    report.buttons+=result.buttons;report.messages+=result.messages;report.skipped.push(...result.skipped.map(x=>({file:relative(root,file),...x})));
    if(result.output!==source){report.files.push(relative(root,file));if(process.argv.includes('--write')){const backup=resolve('/tmp/bklog-native-controls-before',relative(root,file));if(!fs.existsSync(backup)){fs.mkdirSync(dirname(backup),{recursive:true});fs.writeFileSync(backup,source);}fs.writeFileSync(file,result.output);}}
  }
  fs.writeFileSync(resolve(root,'ai-native/button-feedback-migration.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({files:report.files.length,buttons:report.buttons,messages:report.messages,skipped:report.skipped.length}));
}
