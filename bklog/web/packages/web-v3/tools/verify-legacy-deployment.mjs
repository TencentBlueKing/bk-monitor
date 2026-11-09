/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, relative, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
const packageRoot = fileURLToPath(new URL('../', import.meta.url));
const hash = content => createHash('sha256').update(content).digest('hex');
export function verifyLegacyDeployment(output, expectedRoot = resolve(packageRoot, 'public/legacy-v1')) {
  const root = resolve(output, 'legacy-v1');
  for (const file of ['index.html', 'host.js', 'sealed-manifest.json']) {
    if (!existsSync(resolve(root, file))) throw Error(`Missing deployed legacy V1 ${file}`);
    if (hash(readFileSync(resolve(root, file))) !== hash(readFileSync(resolve(expectedRoot, file))))
      throw Error(`Deployed legacy V1 ${file} differs from its source`);
  }
  const manifest = JSON.parse(readFileSync(resolve(root, 'sealed-manifest.json')));
  if (!readFileSync(resolve(root, 'index.html'), 'utf8').includes('./host.js'))
    throw Error('Legacy V1 index does not load its host');
  const assets = resolve(root, 'assets');
  if (!manifest.files?.length) throw Error('Legacy V1 asset manifest is empty');
  for (const file of manifest.files) {
    const target = resolve(assets, file.path),
      path = relative(assets, target);
    if (isAbsolute(path) || path === '..' || path.startsWith('../')) throw Error('Invalid legacy V1 asset path');
    if (!existsSync(target) || hash(readFileSync(target)) !== file.sha256)
      throw Error(`Missing or changed legacy V1 asset: ${file.path}`);
  }
  for (const entry of [manifest.entry?.entryJs, manifest.entry?.entryCss])
    if (!manifest.files.some(file => file.path === entry))
      throw Error('Legacy V1 entry is absent from the sealed asset manifest');
  return {
    status: 'STATIC_DELIVERY_VERIFIED',
    files: manifest.files.length,
    runtimeAccepted: manifest.hostReady === true,
  };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  console.log(JSON.stringify(verifyLegacyDeployment(resolve(packageRoot, 'dist')), null, 2));
