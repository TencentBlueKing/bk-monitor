/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

export const environmentTemplate = readFileSync(new URL('./runtime-environment.html', import.meta.url), 'utf8');
export function productionAssetUrls(html) {
  return html.replace(/\b(src|href)=["']\.\/([^"']+)["']/g, (_match, attribute, file) => `${attribute}="\${BK_STATIC_URL}/${file}"`);
}
export function productionHtml(html) {
  return productionAssetUrls(html)
    .replace(/<title>[^<]*<\/title>/, '<title>${TITLE}</title>')
    .replace('</head>', `${environmentTemplate}\n</head>`);
}
export function productionDelivery() {
  let output;
  return {
    name: 'bklog-production-delivery',
    apply: (_config, env) => env.command === 'build' && !['apm', 'trace'].includes(process.env.MONITOR_APP),
    configResolved(config) { output = resolve(config.root, config.build.outDir); },
    transformIndexHtml: { order: 'post', handler: productionHtml },
    closeBundle() {
      // Vite resolves favicon/HTML asset placeholders after transformIndexHtml.
      const htmlPath = resolve(output, 'index.html');
      writeFileSync(htmlPath, productionAssetUrls(readFileSync(htmlPath, 'utf8')));
      const walk = (dir, prefix = '') => readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
        const path = `${prefix}${entry.name}`;
        return entry.isDirectory() ? walk(resolve(dir, entry.name), `${path}/`) : [path];
      });
      const files = walk(output).filter(file => !/(?:\.html|\.json|\.map)$/.test(file) && file !== 'asset-manifest.js');
      writeFileSync(resolve(output, 'asset-manifest.js'), `self.assetData =${JSON.stringify(files.sort().map(file => '__STATIC_URL__' + file))};\n`);
    },
  };
}
