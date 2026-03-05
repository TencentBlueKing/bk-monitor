#!/usr/bin/env node
/**
 * 本地极速定位助手（只扫描 bklog/web/src）。
 *
 * 用法：
 *   node scripts/ai-locate.js "url 参数"
 *   node scripts/ai-locate.js "日志检索 url-resolver" --rg
 */

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const SRC_DIR = path.resolve(__dirname, '..', 'src');
const SERVICES_INDEX = path.resolve(SRC_DIR, 'services', 'index.js');

// 最小信号集：只保留“形态词”，业务模块词全部交给 serviceKey / fallback 扫描
const SIGNAL_MAP = [
  {
    re: /(url|query|参数|地址栏|分享|share|resolver)/i,
    anchors: ['src/store/url-resolver.ts', 'src/store/default-values.ts', 'src/views/retrieve-v3/use-app-init.tsx'],
    rg: ['convertQueryToStore', 'resolveParamsToUrl', 'route.query', 'router.replace'],
  },
  {
    re: /(路由|router|route|path|跳转)/i,
    anchors: ['src/router/', 'src/views/'],
    rg: ['router.replace', 'router.push', 'beforeEach', 'route.params', 'route.query'],
  },
  {
    re: /(接口|api|http|axios|拦截|请求|响应|header|cookie)/i,
    anchors: ['src/api/index.js', 'src/services/index.js'],
    rg: ['axiosInstance', 'interceptors', 'headers', 'baseURL', 'serviceList'],
  },
  {
    re: /(store|vuex|状态|缓存|localStorage|storage|commit|dispatch)/i,
    anchors: ['src/store/index.js', 'src/store/'],
    rg: ['Vuex', 'commit(', 'dispatch(', 'localStorage', 'state:', 'mutations:', 'actions:'],
  },
];

function uniq(arr) {
  return [...new Set(arr)].filter(Boolean);
}

function usage() {
  console.log(
    [
      'ai-locate (bklog/web/src)',
      '',
      'node scripts/ai-locate.js "<keyword>" [--rg]',
      '',
      'Examples:',
      '  node scripts/ai-locate.js "日志检索 url 参数"',
      '  node scripts/ai-locate.js "axios 拦截器" --rg',
    ].join('\n'),
  );
}

function hasUppercase(s) {
  return /[A-Z]/.test(s);
}

function tryRunRg(args) {
  const ver = spawnSync('rg', ['--version'], { encoding: 'utf8' });
  if (ver.status !== 0) return { ok: false, stdout: '' };
  const res = spawnSync('rg', args, { encoding: 'utf8' });
  return { ok: res.status === 0, stdout: res.stdout || '' };
}

function walkFiles(dir, out, limit) {
  if (out.length >= limit) return;
  let entries = [];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch (_) {
    return;
  }
  for (const e of entries) {
    if (out.length >= limit) return;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      // src 内部不应该有 node_modules；这里做一下保险
      if (e.name === 'node_modules' || e.name.startsWith('.')) continue;
      walkFiles(p, out, limit);
      continue;
    }
    if (!e.isFile()) continue;
    if (!/\.(ts|tsx|js|vue)$/.test(e.name)) continue;
    out.push(p);
  }
}

function scanFilesWithPatterns(rootDir, patterns, fileLimit = 30) {
  const files = [];
  walkFiles(rootDir, files, 50000);

  const hits = [];
  const smartPatterns = patterns
    .map(p => String(p || '').trim())
    .filter(Boolean)
    .map(p => ({
      raw: p,
      cs: hasUppercase(p),
      needle: hasUppercase(p) ? p : p.toLowerCase(),
    }));

  for (const f of files) {
    if (hits.length >= fileLimit) break;
    let content = '';
    try {
      content = fs.readFileSync(f, 'utf8');
    } catch (_) {
      continue;
    }
    const hay = smartPatterns.some(p => {
      const target = p.cs ? content : content.toLowerCase();
      return target.includes(p.needle);
    });
    if (hay) hits.push(f);
  }

  return hits;
}

function scanFileLines(fileAbs, needle, maxLines = 10) {
  let content = '';
  try {
    content = fs.readFileSync(fileAbs, 'utf8');
  } catch (_) {
    return [];
  }
  const cs = hasUppercase(needle);
  const n = cs ? needle : needle.toLowerCase();
  const lines = content.split(/\r?\n/);
  const out = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const target = cs ? line : line.toLowerCase();
    if (target.includes(n)) {
      out.push(`${i + 1}:${line}`);
      if (out.length >= maxLines) break;
    }
  }
  return out;
}

function extractServiceKeys(text) {
  // e.g. retrieve/generateQueryString, favorite/getFavorite
  const re = /([a-zA-Z][\w-]*)\/([a-zA-Z][\w-]*)/g;
  const keys = [];
  let m;
  while ((m = re.exec(text))) {
    keys.push({ ns: m[1], action: m[2], raw: m[0] });
  }
  return keys;
}

function resolveServiceModuleFile(importPath) {
  // importPath like './retrieve' or './log-clustering'
  const base = path.resolve(path.dirname(SERVICES_INDEX), importPath);
  const candidates = [`${base}.ts`, `${base}.js`];
  for (const f of candidates) {
    try {
      if (fs.existsSync(f)) return f;
    } catch (_) {
      // ignore
    }
  }
  return null;
}

function buildServiceNsMap() {
  // ns -> { fileRel, fileAbs, importLine }
  const map = new Map();
  let content = '';
  try {
    content = fs.readFileSync(SERVICES_INDEX, 'utf8');
  } catch (_) {
    return map;
  }
  const lines = content.split(/\r?\n/);

  // Parse: import * as retrieve from './retrieve';
  const importRe = /^\s*import\s+\*\s+as\s+([a-zA-Z][\w]*)\s+from\s+['"](\.\/[^'"]+)['"]\s*;?\s*$/;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const m = line.match(importRe);
    if (!m) continue;
    const ns = m[1];
    const importPath = m[2];
    const fileAbs = resolveServiceModuleFile(importPath);
    const fileRel = fileAbs ? path.relative(path.resolve(__dirname, '..'), fileAbs) : `src/services/${importPath.slice(2)}`;
    map.set(ns, { fileRel, fileAbs, importLine: i + 1 });
  }

  return map;
}

const argv = process.argv.slice(2);
if (!argv.length || argv.includes('-h') || argv.includes('--help')) {
  usage();
  process.exit(0);
}

const enableRg = argv.includes('--rg');
const keywords = argv.filter(a => a !== '--rg').join(' ').trim();

const matched = SIGNAL_MAP.filter(t => t.re.test(keywords));
const anchors = uniq(matched.flatMap(t => t.anchors));

console.log('Scope:', SRC_DIR);
console.log('Anchors:');
anchors.forEach(a => console.log('  -', a));

// 三段式：signal → serviceKey → file
const serviceKeys = extractServiceKeys(keywords);
if (serviceKeys.length) {
  const nsMap = buildServiceNsMap();
  console.log('\nServiceKeys:');
  for (const k of serviceKeys) {
    const hit = nsMap.get(k.ns);
    if (!hit) {
      console.log(`  - ${k.raw} -> (ns not found) src/services/index.js`);
      continue;
    }
    const loc = hit.importLine ? ` (services/index.js:L${hit.importLine})` : '';
    console.log(`  - ${k.raw} -> ${hit.fileRel}${loc}`);
  }
}

if (!enableRg) {
  process.exit(0);
}

const rgSeeds = uniq(matched.flatMap(t => t.rg));
const patterns = rgSeeds.length ? rgSeeds : [keywords];

console.log('\nrg candidates (top 30 files):');
const files = [];
for (const p of patterns) {
  const res = tryRunRg(['--files-with-matches', '-S', p, SRC_DIR]);
  if (res.ok && res.stdout) {
    res.stdout
      .split(/\r?\n/)
      .filter(Boolean)
      .slice(0, 30)
      .forEach(f => files.push(path.relative(path.resolve(__dirname, '..'), f)));
  }
}
if (files.length) {
  uniq(files)
    .slice(0, 30)
    .forEach(f => console.log('  -', f));
} else {
  // fallback: no rg in env
  const hitAbs = scanFilesWithPatterns(SRC_DIR, patterns, 30);
  hitAbs
    .map(f => path.relative(path.resolve(__dirname, '..'), f))
    .forEach(f => console.log('  -', f));
}

// 若输入包含 serviceKey，则优先在命中的 service module 文件内定位 action
if (serviceKeys.length) {
  const nsMap = buildServiceNsMap();
  console.log('\nrg service actions:');
  for (const k of serviceKeys) {
    const hit = nsMap.get(k.ns);
    if (!hit?.fileAbs) continue;
    const rgRes = tryRunRg(['-n', '-S', k.action, hit.fileAbs]);
    if (rgRes.ok && rgRes.stdout) {
      const outLines = rgRes.stdout.split(/\r?\n/).filter(Boolean).slice(0, 10);
      console.log(`  - ${k.raw} in ${hit.fileRel}`);
      outLines.forEach(l => console.log(`      ${l}`));
      continue;
    }
    const lineHits = scanFileLines(hit.fileAbs, k.action, 10);
    if (lineHits.length) {
      console.log(`  - ${k.raw} in ${hit.fileRel}`);
      lineHits.forEach(l => console.log(`      ${hit.fileRel}:${l}`));
      continue;
    }
    console.log(`  - ${k.raw} in ${hit.fileRel} (no match)`);
  }
}

