/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { parse } = require('@babel/parser');
const traverse = require('@babel/traverse').default;
// Change only framework syntax nodes; keep business expressions and comments.
export function upgradeJsxContracts(source) {
  const parseSource = code =>
    parse(code, { sourceType: 'module', plugins: ['typescript', 'jsx', 'decorators-legacy'] });
  const ast = parseSource(source);
  const edits = [];
  traverse(ast, {
    JSXAttribute({ node }) {
      if (node.name.type !== 'JSXIdentifier') return;
      const name = node.name.name;
      if (name === 'scopedSlots') edits.push({ start: node.name.start, end: node.name.end, text: 'v-slots' });
      else if (/^on-[A-Za-z][\w-]*$/.test(name)) {
        const event = name.slice(3).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
        edits.push({
          start: node.name.start,
          end: node.name.end,
          text: `on${event[0].toUpperCase()}${event.slice(1)}`,
        });
      }
    },
  });
  const apply = (code, edits) => {
    for (const edit of edits.sort((a, b) => b.start - a.start))
      code = code.slice(0, edit.start) + edit.text + code.slice(edit.end);
    return code;
  };
  let code = apply(source, edits);
  let changes = edits.length;
  // Work from inner to outer spreads so nested callbacks retain prior edits.
  while (true) {
    const spreads = [];
    traverse(parseSource(code), {
      JSXSpreadAttribute({ node }) {
        const object = node.argument;
        if (object.type !== 'ObjectExpression' || object.properties.length !== 1) return;
        const property = object.properties[0];
        if (property.type !== 'ObjectProperty' || property.computed || property.key.name !== 'scopedSlots') return;
        spreads.push({
          start: node.start,
          end: node.end,
          text: `v-slots={${code.slice(property.value.start, property.value.end)}}`,
        });
      },
    });
    if (!spreads.length) break;
    const innermost = spreads.filter(
      parent => !spreads.some(child => child !== parent && child.start > parent.start && child.end < parent.end),
    );
    code = apply(code, innermost);
    changes += innermost.length;
  }
  return { code, changes };
}

// JSX slot="content" is no longer a named slot in Vue3. Move direct named
// children to native slot functions; preserve existing slots and default children.
export function upgradeJsxNamedSlots(source) {
  let code = source;
  let changes = 0;
  while (true) {
    const ast = parse(code, { sourceType: 'module', plugins: ['typescript', 'jsx', 'decorators-legacy'] });
    const parents = [];
    traverse(ast, {
      JSXElement({ node }) {
        const children = node.children
          .filter(child => child.type === 'JSXElement')
          .map(child => ({
            child,
            slot: child.openingElement.attributes.find(
              a => a.type === 'JSXAttribute' && a.name.name === 'slot' && a.value?.type === 'StringLiteral',
            ),
          }))
          .filter(item => item.slot);
        if (children.length) parents.push({ node, children });
      },
    });
    if (!parents.length) break;
    const inner = parents.filter(
      p => !parents.some(c => c !== p && c.node.start > p.node.start && c.node.end < p.node.end),
    );
    const edits = [];
    for (const { node, children } of inner) {
      const entries = children.map(({ child, slot }) => {
        let content = code.slice(child.start, slot.start) + code.slice(slot.end, child.end);
        if (child.openingElement.name.name === 'template') {
          content = '<>' + code.slice(child.openingElement.end, child.closingElement.start) + '</>';
        }
        edits.push({ start: child.start, end: child.end, text: '' });
        return `${JSON.stringify(slot.value.value)}: () => (${content})`;
      });
      const existing = node.openingElement.attributes.find(a => a.type === 'JSXAttribute' && a.name.name === 'v-slots');
      if (existing) {
        if (existing.value?.type !== 'JSXExpressionContainer') throw new Error('Unsupported v-slots value');
        const value = existing.value.expression;
        edits.push({
          start: existing.start,
          end: existing.end,
          text: `v-slots={{...(${code.slice(value.start, value.end)}), ${entries.join(', ')}}}`,
        });
      } else
        edits.push({
          start: node.openingElement.name.end,
          end: node.openingElement.name.end,
          text: ` v-slots={{${entries.join(', ')}}}`,
        });
      changes += children.length;
    }
    for (const edit of edits.sort((a, b) => b.start - a.start))
      code = code.slice(0, edit.start) + edit.text + code.slice(edit.end);
  }
  return { code, changes };
}

export function upgradeJsxListenerObjects(source) {
  let code = source;
  let changes = 0;
  while (true) {
    const edits = [];
    traverse(parse(code, { sourceType: 'module', plugins: ['typescript', 'jsx', 'decorators-legacy'] }), {
      JSXSpreadAttribute({ node }) {
        if (node.argument.type !== 'ObjectExpression') return;
        for (const prop of node.argument.properties) {
          if (
            prop.type !== 'ObjectProperty' ||
            prop.computed ||
            (prop.key.name || prop.key.value) !== 'on' ||
            prop.value.type !== 'ObjectExpression'
          )
            continue;
          if (
            !prop.value.properties.every(
              p => p.type === 'ObjectProperty' && !p.computed && ['Identifier', 'StringLiteral'].includes(p.key.type),
            )
          )
            continue;
          const entries = prop.value.properties.map(p => {
            const event = (p.key.name || p.key.value).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
            return `${JSON.stringify('on' + event[0].toUpperCase() + event.slice(1))}: ${code.slice(p.value.start, p.value.end)}`;
          });
          edits.push({ start: prop.start, end: prop.end, text: entries.join(', ') });
        }
      },
    });
    if (!edits.length) break;
    const inner = edits.filter(p => !edits.some(c => c !== p && c.start > p.start && c.end < p.end));
    for (const e of inner.sort((a, b) => b.start - a.start)) code = code.slice(0, e.start) + e.text + code.slice(e.end);
    changes += inner.length;
  }
  return { code, changes };
}

export function upgradeJsxPropBags(source) {
  let code = source;
  let changes = 0;
  while (true) {
    const edits = [];
    traverse(parse(code, { sourceType: 'module', plugins: ['typescript', 'jsx', 'decorators-legacy'] }), {
      JSXSpreadAttribute({ node }) {
        if (node.argument.type !== 'ObjectExpression') return;
        for (const prop of node.argument.properties) {
          if (
            prop.type === 'ObjectProperty' &&
            !prop.computed &&
            ['props', 'attrs', 'domProps'].includes(prop.key.name || prop.key.value)
          )
            edits.push({
              start: prop.start,
              end: prop.end,
              text: `...(${code.slice(prop.value.start, prop.value.end)})`,
            });
        }
      },
    });
    if (!edits.length) break;
    const inner = edits.filter(p => !edits.some(c => c !== p && c.start > p.start && c.end < p.end));
    for (const e of inner.sort((a, b) => b.start - a.start)) code = code.slice(0, e.start) + e.text + code.slice(e.end);
    changes += inner.length;
  }
  return { code, changes };
}
