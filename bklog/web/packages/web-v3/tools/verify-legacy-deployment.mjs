/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, relative, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { productionOutput } from './production-paths.mjs';
import { resolveInstalledLogWeb } from './legacy-static-entry.mjs';

const packageRoot = fileURLToPath(new URL('../', import.meta.url));
const hash = content => createHash('sha256').update(content).digest('hex');

const listFiles = (dir, prefix = '') => {
  const result = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    const full = resolve(dir, entry.name);
    if (entry.isDirectory()) result.push(...listFiles(full, rel));
    else result.push(rel);
  }
  return result.sort();
};

export function verifyLegacyDeployment(output, expectedRoot = resolve(packageRoot, 'public/legacy-v1')) {
  const root = resolve(output, 'legacy-v1');
  for (const file of ['index.html', 'host.js']) {
    if (!existsSync(resolve(root, file))) throw Error(`Missing deployed legacy V1 ${file}`);
    if (hash(readFileSync(resolve(root, file))) !== hash(readFileSync(resolve(expectedRoot, file))))
      throw Error(`Deployed legacy V1 ${file} differs from its source`);
  }
  const manifestPath = resolve(root, 'sealed-manifest.json');
  if (!existsSync(manifestPath)) throw Error('Missing deployed legacy V1 sealed-manifest.json');
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));

  const installed = resolveInstalledLogWeb(packageRoot);
  if (
    manifest.version !== installed.version ||
    manifest.entry?.entryJs !== installed.entry.entryJs ||
    manifest.entry?.entryCss !== installed.entry.entryCss
  ) {
    throw Error(
      `Legacy V1 sealed-manifest.json (${manifest.version}, ${manifest.entry?.entryJs}, ${manifest.entry?.entryCss}) does not match installed @blueking/log-web (${installed.version}, ${installed.entry.entryJs}, ${installed.entry.entryCss})`,
    );
  }

  if (!readFileSync(resolve(root, 'index.html'), 'utf8').includes('./host.js'))
    throw Error('Legacy V1 index does not load its host');
  const assets = resolve(root, 'assets');
  if (!existsSync(assets)) throw Error('Missing deployed legacy V1 assets directory');
  if (!manifest.files?.length) throw Error('Legacy V1 asset manifest is empty');

  const expectedPaths = new Set();
  for (const file of manifest.files) {
    const target = resolve(assets, file.path),
      path = relative(assets, target);
    if (isAbsolute(path) || path === '..' || path.startsWith('../')) throw Error('Invalid legacy V1 asset path');
    if (!existsSync(target) || hash(readFileSync(target)) !== file.sha256)
      throw Error(`Missing or changed legacy V1 asset: ${file.path}`);
    expectedPaths.add(file.path);
  }

  const installedFiles = listFiles(installed.distDir);
  const deployedFiles = listFiles(assets);
  if (
    installedFiles.length !== deployedFiles.length ||
    installedFiles.some((file, index) => file !== deployedFiles[index] || !expectedPaths.has(file))
  ) {
    throw Error('Deployed legacy V1 assets do not match installed @blueking/log-web dist files');
  }

  for (const entry of [manifest.entry?.entryJs, manifest.entry?.entryCss])
    if (!manifest.files.some(file => file.path === entry))
      throw Error('Legacy V1 entry is absent from the sealed asset manifest');
  return {
    status: 'STATIC_DELIVERY_VERIFIED',
    version: manifest.version,
    files: manifest.files.length,
    runtimeAccepted: manifest.hostReady === true,
  };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  console.log(JSON.stringify(verifyLegacyDeployment(productionOutput), null, 2));
