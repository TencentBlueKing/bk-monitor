// Project-owned Vite E2E overlay. Load existing plugins, aliases and transforms.
import { loadConfigFromFile } from 'vite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import settings from './local.settings.e2e.aafe.cjs';
const checkout = path.dirname(fileURLToPath(import.meta.url));
export default async (env) => {
  const source = process.env.AAFE_E2E_CONFIG_ROOT || checkout;
  const dev = JSON.parse(fs.readFileSync(path.join(source, '.aafe/config.json'), 'utf8')).e2e.devServer;
  const filename = dev.viteConfig ? path.resolve(checkout, dev.viteConfig) : undefined;
  if (filename === fileURLToPath(import.meta.url)) throw new Error('E2E wrapper cannot load itself');
  const loaded = await loadConfigFromFile(env, filename, checkout);
  if (filename && !loaded) throw new Error('Existing Vite config could not be loaded');
  const base = loaded?.config || {};
  const proxy = Object.fromEntries(settings.proxy[0].context.map((prefix) => [prefix, {
    target: settings.devProxyUrl, changeOrigin: true, secure: settings.proxy[0].secure,
    configure(server) { server.on('proxyReq', settings.proxy[0].onProxyReq); }
  }]));
  // Replace proxy map: never merge everyday development cookies/targets into E2E.
  return { ...base, server: { ...base.server, host: settings.host, port: settings.port,
    strictPort: true, open: false, https: false, proxy, allowedHosts: [settings.host, 'localhost'] } };
};
