const webpackLog = require('webpack-log');
const crypto = require('node:crypto');
const log = webpackLog({ name: 'monitor-webpack-plugin' });
const RawSource = require('webpack-sources/lib/RawSource');
const CachedSource = require('webpack-sources/lib/CachedSource');
const { transformDistDir, mobileBuildVariates, pcBuildVariates, externalBuildVariates } = require('./utils');
module.exports = class MonitorWebpackPlugin {
  constructor(app, options = {}) {
    this.defaultOption = { cacheVersionKey: '__cache_version___', staticUrlKey: '__STATIC_URL__' };
    this.options = Object.assign({}, this.defaultOption, options);
    this.cacheVersionKey = this.options.cacheVersionKey;
    this.staticUrlKey = this.options.staticUrlKey;
    this.isMobile = app === 'mobile';
    this.isExternal = app === 'external';
    this.modePath = this.isMobile ? '' : transformDistDir(app);
    this.staticUrl = !this.isMobile ? 'STATIC_URL' : 'WEIXIN_STATIC_URL';
    this.variates = this.isExternal
      ? externalBuildVariates
      : (this.isMobile ? mobileBuildVariates : pcBuildVariates) || '';
    this.hasChanged = false;
  }

  apply(compiler) {
    const hookOption = {
      name: 'MonitorWebpackPlugin',
      stage: 'PROCESS_ASSETS_STAGE_ANALYSE',
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
            if (['monitor'].includes(this.modePath)) {
              compilation.assets['static_version.txt'] = new RawSource(crypto.randomBytes(16).toString('hex'));
            }
          } catch (err) {
            log.error(err);
          }
        }
      });
    });
    // if(this.isMobile) {
    //   compiler.hooks.afterEmit.tap(hookOption, (compilation) => {
    //     const chunkItem = compilation.assets['manifest.json']
    //     const isCahedSource = !!chunkItem._source
    //     let chunkSource = isCahedSource ? chunkItem._source._value : chunkItem._value
    //     chunkSource = Buffer.isBuffer(chunkSource) ? Buffer.toString('utf-8') : chunkSource
    //     if(!isCahedSource) {
    //       chunkItem._value = this.resolveManifestJson(chunkSource)
    //     } else {
    //       compilation.assets[key] = new CachedSource(new RawSource(this.resolveManifestJson(chunkSource)))
    //     }
    //   })
    // }
  }

  resolveIndexHtml(chunk) {
    const urls = chunk.match(/(href|src|content)="([^"]+)"/gim);
    if (urls) {
      let res = chunk;
      urls.forEach(url => {
        let machUrl = url.replace(`${this.staticUrl}${this.modePath}/`, '');
        if (
          !/(data:|manifest\.json|http|\/\/)|\$\{STATIC_URL\}| \$\{WEIXIN_STATIC_URL\} |\$\{SITE_URL\}/gim.test(
            machUrl,
          ) &&
          /\.(png|css|js)/gim.test(machUrl)
        ) {
          machUrl = machUrl.replace(
            /([^"])"([^"]+)"/gim,
            `$1"\${${this.staticUrl}}${this.modePath}${this.isMobile ? '' : '/'}$2"`,
          );
        }
        if (this.isMobile) {
          machUrl = machUrl.replace(/\$\{SITE_URL\}/gm, '${WEIXIN_SITE_URL}');
        }
        res = res.replace(url, machUrl);
      });
      const scripts = res.match(/<script template>([^<]+)<\/script>/gim);
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
    if (chunk.match?.(reg)) {
      const res = chunk.replace(reg, 'http://blueking.com');
      return {
        source() {
          return res;
        },
        size() {
          return res.length;
        },
      };
    }
    return null;
  }
  resolveServiceWorker(chunk) {
    const key = crypto.randomBytes(16).toString('hex');
    chunk = chunk.replace(/__cache_version___/gm, key);
    if (this.isMobile) {
      chunk = chunk.replace('${STATIC_URL}', '${WEIXIN_STATIC_URL}');
    }
    return chunk;
  }
  resolveManifestJson(chunk) {
    chunk = chunk
      .replace(/\$\{STATIC_URL\}/gm, '${WEIXIN_STATIC_URL}')
      .replace(/\$\{SITE_URL\}/gm, '${WEIXIN_SITE_URL}');
    return chunk;
  }
};
