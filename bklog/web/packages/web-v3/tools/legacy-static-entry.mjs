/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { createHash } from 'node:crypto';
import { cpSync, createReadStream, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { extname, isAbsolute, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const defaultPackageRoot = fileURLToPath(new URL('../', import.meta.url));
const LOG_WEB_PACKAGE = '@blueking/log-web';
const VIRTUAL_LOG_WEB_ID = '\0bklog-legacy-log-web-manifest';

const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.eot': 'application/vnd.ms-fontobject',
  '.gif': 'image/gif',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ttf': 'font/ttf',
  '.txt': 'text/plain; charset=utf-8',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

const sha256 = content => createHash('sha256').update(content).digest('hex');

const walkFiles = (dir, prefix = '') => {
  const entries = readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name));
  const files = [];
  for (const entry of entries) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    const full = resolve(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(full, rel));
    } else {
      const content = readFileSync(full);
      files.push({ path: rel, bytes: content.length, sha256: sha256(content) });
    }
  }
  return files;
};

const loadLogWebEntry = distDir => {
  const entryFile = resolve(distDir, 'index.js');
  if (!existsSync(entryFile)) throw Error(`Missing ${LOG_WEB_PACKAGE} dist entry: ${entryFile}`);
  const require = createRequire(import.meta.url);
  delete require.cache[entryFile];
  const entry = require(entryFile);
  if (!entry?.entryJs || !entry?.entryCss) {
    throw Error(`Invalid ${LOG_WEB_PACKAGE} dist manifest in ${entryFile}`);
  }
  return { entryJs: entry.entryJs, entryCss: entry.entryCss };
};

export function resolveInstalledLogWeb(packageRoot = defaultPackageRoot) {
  const hostPkg = JSON.parse(readFileSync(resolve(packageRoot, 'package.json'), 'utf8'));
  const declaredVersion = hostPkg.dependencies?.[LOG_WEB_PACKAGE];
  const pkgDir = resolve(packageRoot, 'node_modules', LOG_WEB_PACKAGE);
  const pkgJsonPath = resolve(pkgDir, 'package.json');
  if (!existsSync(pkgJsonPath)) {
    throw Error(`Missing installed ${LOG_WEB_PACKAGE} package at ${pkgDir}`);
  }
  const installedPkg = JSON.parse(readFileSync(pkgJsonPath, 'utf8'));
  if (declaredVersion && /^\d+\.\d+\.\d+(?:[-+].+)?$/.test(declaredVersion) && installedPkg.version !== declaredVersion) {
    throw Error(
      `Installed ${LOG_WEB_PACKAGE}@${installedPkg.version} does not match package.json (${declaredVersion}); run pnpm install`,
    );
  }
  const distDir = resolve(pkgDir, 'dist');
  const entry = loadLogWebEntry(distDir);
  return {
    packageName: installedPkg.name || LOG_WEB_PACKAGE,
    version: installedPkg.version,
    declaredVersion,
    distDir,
    entry,
  };
}

export function buildSealedManifest(resolved) {
  const files = walkFiles(resolved.distDir).sort((a, b) => a.path.localeCompare(b.path));
  return {
    schemaVersion: 1,
    package: resolved.packageName,
    version: resolved.version,
    entry: resolved.entry,
    provenance: 'Synced directly from installed @blueking/log-web matching package.json',
    hostReady: false,
    files,
  };
}

export function syncLegacyDeployment(output, packageRoot = defaultPackageRoot) {
  const resolved = resolveInstalledLogWeb(packageRoot);
  const manifest = buildSealedManifest(resolved);
  const legacySourceDir = resolve(packageRoot, 'public/legacy-v1');
  const legacyOutDir = resolve(output, 'legacy-v1');
  const assetsOutDir = resolve(legacyOutDir, 'assets');

  mkdirSync(legacyOutDir, { recursive: true });
  for (const file of ['index.html', 'host.js']) {
    cpSync(resolve(legacySourceDir, file), resolve(legacyOutDir, file));
  }
  rmSync(assetsOutDir, { recursive: true, force: true });
  cpSync(resolved.distDir, assetsOutDir, { recursive: true });
  writeFileSync(resolve(legacyOutDir, 'sealed-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
  return { version: resolved.version, entry: resolved.entry, files: manifest.files.length };
}

export function rewriteLegacyEntry(requestUrl, base = '/') {
  const url = new URL(requestUrl || '/', 'http://localhost');
  const prefix = base.startsWith('/') ? base.replace(/\/?$/, '/') : '/';
  if (![`${prefix}legacy-v1`, `${prefix}legacy-v1/`].includes(url.pathname)) return requestUrl;
  return `${prefix}legacy-v1/index.html${url.search}`;
}

export function legacyStaticEntry(packageRoot = defaultPackageRoot) {
  let output;
  let isBuild = false;
  let cachedManifestKey = '';
  let cachedManifestJson = '';

  const getLiveManifestJson = () => {
    const resolved = resolveInstalledLogWeb(packageRoot);
    const key = `${resolved.version}|${resolved.entry.entryJs}|${resolved.entry.entryCss}`;
    if (key !== cachedManifestKey) {
      cachedManifestJson = `${JSON.stringify(buildSealedManifest(resolved), null, 2)}\n`;
      cachedManifestKey = key;
    }
    return cachedManifestJson;
  };

  return {
    name: 'legacy-v1-static-entry',
    enforce: 'pre',
    configResolved(config) {
      isBuild = config.command === 'build';
      output = resolve(config.root, config.build.outDir);
    },
    resolveId(id) {
      if (id === LOG_WEB_PACKAGE) return VIRTUAL_LOG_WEB_ID;
      return null;
    },
    load(id) {
      if (id !== VIRTUAL_LOG_WEB_ID) return null;
      const resolved = resolveInstalledLogWeb(packageRoot);
      return `export default ${JSON.stringify(resolved.entry)};\n`;
    },
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const prefix = server.config.base.startsWith('/') ? server.config.base.replace(/\/?$/, '/') : '/';
        const url = new URL(request.url || '/', 'http://localhost');
        const pathname = url.pathname;

        if (pathname === `${prefix}legacy-v1/sealed-manifest.json`) {
          const body = getLiveManifestJson();
          response.statusCode = 200;
          response.setHeader('Content-Type', MIME_TYPES['.json']);
          response.setHeader('Cache-Control', 'no-cache');
          if (request.method === 'HEAD') {
            response.end();
          } else {
            response.end(body);
          }
          return;
        }

        const assetsPrefix = `${prefix}legacy-v1/assets/`;
        if (pathname.startsWith(assetsPrefix)) {
          const resolved = resolveInstalledLogWeb(packageRoot);
          const relPath = decodeURIComponent(pathname.slice(assetsPrefix.length));
          const target = resolve(resolved.distDir, relPath);
          const relCheck = relative(resolved.distDir, target);
          if (
            !relPath ||
            isAbsolute(relCheck) ||
            relCheck === '..' ||
            relCheck.startsWith('../') ||
            !existsSync(target) ||
            !statSync(target).isFile()
          ) {
            response.statusCode = 404;
            response.end('Not Found');
            return;
          }
          response.statusCode = 200;
          response.setHeader('Content-Type', MIME_TYPES[extname(target).toLowerCase()] || 'application/octet-stream');
          response.setHeader('Cache-Control', 'no-cache');
          if (request.method === 'HEAD') {
            response.end();
          } else {
            createReadStream(target).pipe(response);
          }
          return;
        }

        request.url = rewriteLegacyEntry(request.url, server.config.base);
        next();
      });
    },
    closeBundle() {
      if (!isBuild || ['apm', 'trace'].includes(process.env.MONITOR_APP)) return;
      syncLegacyDeployment(output, packageRoot);
    },
  };
}
