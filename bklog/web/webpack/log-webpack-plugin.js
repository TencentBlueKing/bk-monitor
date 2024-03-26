/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

/* eslint-disable max-len */
/* eslint-disable no-underscore-dangle */
const webpackLog = require('webpack-log');
const crypto = require('crypto');
const log = webpackLog({ name: 'log-webpack-plugin' });
const RawSource = require('webpack-sources/lib/RawSource');
const CachedSource = require('webpack-sources/lib/CachedSource');
module.exports = class LogWebpackPlugin {
  constructor(config, options = {}) {
    this.defaultOption = { cacheVersionKey: '__cache_version___', staticUrlKey: '__STATIC_URL__' };
    this.options = Object.assign({}, this.defaultOption, options);
    this.cacheVersionKey = this.options.cacheVersionKey;
    this.staticUrlKey = this.options.staticUrlKey;
    this.modePath = '';
    this.staticUrl = 'BK_STATIC_URL';
    this.variates = config.pcBuildVariates || '';
    this.hasChanged = false;
  }

  apply(compiler) {
    const hookOption = {
      name: 'LogWebpackPlugin',
      stage: 'PROCESS_ASSETS_STAGE_ANALYSE'
    };
    compiler.hooks.thisCompilation.tap(hookOption, compilation => {
      compilation.hooks.afterProcessAssets.tap(hookOption, () => {
        if (!this.hasChanged && compilation.assets) {
          try {
            this.hasChanged = true;
            const assetManifestData = [];
            Object.keys(compilation.assets).forEach(key => {
              const chunkItem = compilation.assets[key];
              const isCahedSource = !!chunkItem._source;
              let chunkSource = isCahedSource ? chunkItem._source._value : chunkItem._value;
              chunkSource = Buffer.isBuffer(chunkSource) ? Buffer.toString('utf-8') : chunkSource;
              if (chunkSource) {
                // 去敏感信息
                // Object.assign(chunkItem, this.resolveInternalInfo(chunkSource))
                if (key.match(/\.css$/gi)) {
                  if (!isCahedSource) {
                    chunkItem._value = this.resolveCssFont(chunkSource);
                  } else {
                    compilation.assets[key] = new CachedSource(new RawSource(this.resolveCssFont(chunkSource)));
                  }
                } else if (key.match(/index\.html/gi)) {
                  if (!isCahedSource) {
                    chunkItem._value = this.resolveIndexHtml(chunkSource);
                  } else {
                    compilation.assets[key] = new CachedSource(new RawSource(this.resolveIndexHtml(chunkSource)));
                  }
                } else if (key.match(/service-worker\.js/i)) {
                  if (!isCahedSource) {
                    chunkItem._value = this.resolveServiceWorker(chunkSource);
                  } else {
                    compilation.assets[key] = new CachedSource(new RawSource(this.resolveServiceWorker(chunkSource)));
                  }
                }
              }
              if (!key.match(/(\.DS_Store|\.html|service-worker\.js|\.json)$/gi)) {
                assetManifestData.push(this.staticUrlKey + key);
              }
            });
            const assetChunk = `self.assetData =${JSON.stringify(assetManifestData)}`;
            compilation.assets['asset-manifest.js'] = new RawSource(assetChunk);
          } catch (err) {
            log.error(err);
          }
        }
      });
    });
  }

  resolveIndexHtml(chunk) {
    const urls = chunk.match(/(href|src|content)="([^"]+)"/gim);
    if (urls) {
      let res = chunk;
      urls.forEach(url => {
        let machUrl = url.replace(`${this.staticUrl}${this.modePath}/`, '');
        if (
          !/(data:|manifest\.json|http|\/\/)|\$\{BK_STATIC_URL\}| \$\{WEIXIN_STATIC_URL\} |\$\{SITE_URL\}/gim.test(
            machUrl
          ) &&
          /\.(png|css|js)/gim.test(machUrl)
        ) {
          machUrl = machUrl.replace(/([^"])"([^"]+)"/gim, `$1"\${${this.staticUrl}}${this.modePath}/$2"`);
        }
        res = res.replace(url, machUrl);
      });
      const scripts = res.match(/<script template>*<\/script>/gim);
      if (scripts) {
        scripts.forEach(script => {
          res = res.replace(script, this.variates);
        });
      }
      return res;
    }
    return chunk;
  }

  resolveCssFont(chunk) {
    if (!chunk) return chunk;
    const urls = chunk.match(/url\((\/fonts\/|img\/)[^)]+\)/gim);
    if (urls) {
      let res = chunk;
      urls.forEach(url => {
        const machUrl = url
          .replace(/url\(((\/fonts\/)[^)]+)\)/gim, 'url("..$1")')
          .replace(/url\(((img\/)[^)]+)\)/gim, 'url("../$1")');
        res = res.replace(url, machUrl);
      });
      return res;
    }
    return chunk;
  }

  resolveInternalInfo(chunk) {
    const reg = /((http:\/\/|ftp:\/\/|https:\/\/|\/\/)?(([^./"' \u4e00-\u9fa5（]+\.)*(oa\.com|ied\.com)+))/gi;
    if (chunk.match && chunk.match(reg)) {
      const res = chunk.replace(reg, 'http://blueking.com');
      return {
        source() {
          return res;
        },
        size() {
          return res.length;
        }
      };
    }
    return null;
  }
  resolveServiceWorker(chunk) {
    chunk = chunk.replace('__cache_version___', crypto.randomBytes(16).toString('hex'));
    return chunk;
  }
};
