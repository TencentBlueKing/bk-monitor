/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { resolve, dirname, relative, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { productionOutput } from './production-paths.mjs';
import { environmentTemplate } from './production-delivery.mjs';

export function verifyProductionBuild(output = productionOutput) {
  const root = resolve(output), html = readFileSync(resolve(root, 'index.html'), 'utf8');
  if (!html.includes(environmentTemplate) || !html.includes('${TITLE}')) throw Error('Missing server runtime template');
  const urls = [...html.matchAll(/\b(?:src|href)="([^"]+)"/g)].map(match => match[1]);
  const assets = urls.filter(url => url.startsWith('${BK_STATIC_URL}/'));
  if (!assets.some(url => url.endsWith('.js')) || !assets.some(url => url.endsWith('.css'))) throw Error('Missing production script or stylesheet');
  function check(file, from = root) {
    const target = resolve(from, decodeURIComponent(file.split(/[?#]/)[0]));
    const path = relative(root, target);
    if (isAbsolute(path) || path === '..' || path.startsWith('../') || !existsSync(target)) throw Error(`Missing/escaping asset: ${file}`);
  }
  for (const asset of assets) check(asset.slice('${BK_STATIC_URL}/'.length));
  if (urls.some(url => !url.startsWith('${BK_STATIC_URL}/') && !/^(?:https?:|data:|\/\/|#)/.test(url))) throw Error('Build URL bypasses the deployment prefix');
  const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? walk(resolve(dir, entry.name)) : [resolve(dir, entry.name)]);
  const files = walk(root);
  for (const file of files.filter(file => file.endsWith('.css') && !file.includes('/legacy-v1/'))) {
    for (const [, url] of readFileSync(file, 'utf8').matchAll(/url\(["']?([^)'"\s]+)["']?\)/g)) {
      if (/^(?:data:|https?:|\/\/|#)/.test(url)) continue;
      check(url, dirname(file));
    }
  }
  if (files.some(file => /\.(?:map|tsx?|jsx)$/.test(file) || /(?:^|\/)(?:\.cookie(?:\..*)?|\.env(?:\..*)?)$/.test(file))) throw Error('Private/debug file in production output');
  const manifest = readFileSync(resolve(root, 'asset-manifest.js'), 'utf8');
  const listed = JSON.parse(manifest.slice(manifest.indexOf('=') + 1).trim().replace(/;$/, ''));
  for (const file of listed) {
    if (!file.startsWith('__STATIC_URL__')) throw Error('Invalid asset manifest prefix');
    check(file.slice('__STATIC_URL__'.length));
  }
  return { status: 'PRODUCTION_DELIVERY_VERIFIED', assets: files.length, htmlAssets: assets.length };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) console.log(JSON.stringify(verifyProductionBuild(process.argv[2]), null, 2));
