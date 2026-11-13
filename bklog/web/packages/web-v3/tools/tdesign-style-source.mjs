/** Lossless declaration ranges for source style blocks; comments/strings are never rewritten. */
export function styleDeclarations(text) {
  const frames = [{ start: 0, head: '', native: false, id: 0 }], declarations = [];
  let quote = '', comment = '', parens = 0, interpolation = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text[i], next = text[i + 1];
    if (comment) {
      if (comment === 'line' && char === '\n') { comment = ''; if (!text.slice(frames.at(-1).start, i).trim().replace(/^\/\/[^\n]*$/, '').trim()) frames.at(-1).start = i + 1; }
      else if (comment === 'block' && char === '*' && next === '/') { comment = ''; i++; }
      continue;
    }
    if (quote) { if (char === '\\') i++; else if (char === quote) quote = ''; continue; }
    if (char === '/' && next === '*') { comment = 'block'; i++; continue; }
    if (char === '/' && next === '/' && !parens) { comment = 'line'; i++; continue; }
    if (char === '"' || char === "'") { quote = char; continue; }
    if (char === '#' && next === '{') { interpolation++; i++; continue; }
    if (interpolation) { if (char === '{') interpolation++; else if (char === '}') interpolation--; continue; }
    if (char === '(' || char === '[') { parens++; continue; }
    if (char === ')' || char === ']') { parens--; continue; }
    if (parens) continue;
    const frame = frames.at(-1);
    if (char === '{') {
      const head = text.slice(frame.start, i).replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '').trim();
      frames.push({ id: i, start: i + 1, head, native: frame.native || /\.t-[\w-]+/.test(head) });
    } else if (char === ';' || char === '}') {
      const raw = text.slice(frame.start, i);
      // Avoid editing comments, Sass statements, custom properties, or selector-like text.
      const match = raw.match(/^(\s*(?:(?:\/\*[\s\S]*?\*\/|\/\/[^\n]*)\s*)*)([-\w]+)(\s*:\s*)([^{};]+)$/);
      if (frame.native && match && !match[2].startsWith('--')) {
        const valueStart = frame.start + match[1].length + match[2].length + match[3].length;
        declarations.push({ property: match[2], start: frame.start, end: i + (char === ';' ? 1 : 0), valueStart, valueEnd: i, value: match[4], block: frame.id, head: frame.head });
      }
      frame.start = i + 1;
      if (char === '}' && frames.length > 1) { frames.pop(); frames.at(-1).start = i + 1; }
    }
  }
  return declarations;
}

export const colorTokens = {
  '#3a84ff': 'brand-primary', '#eaf3ff': 'brand-tint-subtle', '#e1ecff': 'brand-tint', '#699df4': 'brand-hover', '#2761dd': 'brand-active',
  '#313238': 'text-primary', '#63656e': 'text-secondary', '#979ba5': 'text-placeholder', '#c4c6cc': 'text-disabled',
  '#dcdee5': 'border-muted', '#fff': 'surface', '#ffffff': 'surface', '#f5f7fa': 'surface-hover', '#f0f1f5': 'surface-component', '#eaebf0': 'surface-component-hover', '#fafbfd': 'surface-disabled',
  '#4d4f56': 'text-strong', '#ff5656': 'status-error-emphasis', '#d7473f': 'status-error-active', '#a4c6fe': 'border-focus-light',
  '#2dcb56': 'status-success', '#ff9c01': 'status-warning', '#ea3636': 'status-error',
};
export function semanticValue(property, raw) {
  // Never rewrite a dynamic function or an existing variable (including its fallback).
  if (/\b(?:var|rgba?|hsla?|url|linear-gradient|calc)\s*\(|\$|#\{/.test(raw)) return raw;
  if (/^(?:color|background(?:-color)?|border(?:-(?:top|right|bottom|left))?(?:-color)?|outline(?:-color)?|fill|stroke)$/.test(property)) {
    return raw.replace(/#[\da-f]{3,8}\b/gi, value => {
      const color = value.toLowerCase();
      let token = colorTokens[color];
      if (property === 'color' && ['#fff', '#ffffff'].includes(color)) token = 'text-inverse';
      if (/^(border|outline)/.test(property) && color === '#c4c6cc') token = 'border-control';
      if (/^(border|outline)/.test(property) && color === '#979ba5') token = 'border-hover';
      return token ? `var(--bklog-${token}, ${value})` : value;
    });
  }
  if (property === 'box-shadow') {
    const shadow = raw.trim().replace(/\s+/g, ' ').toLowerCase();
    if (shadow === '0 2px 6px 0 #0000001a') return `var(--bklog-shadow-small, ${raw.trim()})`;
    if (shadow === '0 3px 9px 0 #0000001a') return `var(--bklog-shadow-popup, ${raw.trim()})`;
  }
  const match = raw.match(/^\s*(\d+)px(\s*!important)?\s*$/);
  if (!match) return raw;
  const token = property === 'line-height' ? ({16:'line-height-small',20:'line-height-body'})[match[1]] : property === 'font-size' ? ({12:'font-body',14:'font-action',16:'font-large'})[match[1]] : property === 'border-radius' && match[1] === '2' ? 'radius-control' : undefined;
  return token ? `var(--bklog-${token}, ${match[1]}px)${match[2] || ''}` : raw;
}
export function normalizeStyle(text) {
  const changes = styleDeclarations(text).flatMap(decl => {
    const value = semanticValue(decl.property, decl.value);
    return value === decl.value ? [] : [{ start: decl.valueStart, end: decl.valueEnd, value }];
  });
  let output = text;
  for (const change of changes.toReversed()) output = output.slice(0, change.start) + change.value + output.slice(change.end);
  return { output, count: changes.length };
}

/** Resolve only known semantic var() calls, including nested function fallbacks.
 * Quoted CSS strings are left intact. No external parser dependency is needed. */
export function resolveSemanticVariables(value, resolve) {
  let output = '', quote = '';
  for (let i = 0; i < value.length; i++) {
    const char = value[i];
    if (quote) {
      output += char;
      if (char === '\\') output += value[++i] || '';
      else if (char === quote) quote = '';
      continue;
    }
    if (char === '"' || char === "'") { quote = char; output += char; continue; }
    if (value.slice(i, i + 4) !== 'var(') { output += char; continue; }
    let depth = 1, innerQuote = '', comma = -1, end = i + 4;
    for (; end < value.length; end++) {
      const c = value[end];
      if (innerQuote) { if (c === '\\') end++; else if (c === innerQuote) innerQuote = ''; continue; }
      if (c === '"' || c === "'") { innerQuote = c; continue; }
      if (c === '(') depth++;
      else if (c === ')' && --depth === 0) break;
      else if (c === ',' && depth === 1 && comma < 0) comma = end;
    }
    if (depth !== 0) { output += value.slice(i); break; }
    const token = value.slice(i + 4, comma < 0 ? end : comma).trim();
    const fallback = comma < 0 ? undefined : value.slice(comma + 1, end).trim();
    const replacement = token.startsWith('--bklog-') ? resolve(token, fallback) : undefined;
    output += replacement === undefined ? value.slice(i, end + 1) : replacement;
    i = end;
  }
  return output;
}
