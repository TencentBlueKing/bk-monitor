/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

const RawSource = require('webpack-sources/lib/RawSource');

/**
 * 从编译产物中提取 entryJs 和 entryCss，生成 asset-manifest.js 模块文件
 */
module.exports = class HtmlToManifestPlugin {
  constructor(options = {}) {
    this.options = options;
    this.outputFileName = options.outputFileName || 'index.js';
  }

  apply(compiler) {
    const hookOption = {
      name: 'HtmlToManifestPlugin',
      stage: compiler.webpack.Compilation.PROCESS_ASSETS_STAGE_OPTIMIZE,
    };

    compiler.hooks.thisCompilation.tap(hookOption, (compilation) => {
      compilation.hooks.processAssets.tap(hookOption, () => {
        try {
          let entryJs = '';
          let entryCss = '';

          // 方法1: 尝试从 index.html 中提取（如果存在）
          const indexHtmlAsset = compilation.assets['index.html'];
          if (indexHtmlAsset) {
            let htmlContent = '';
            if (indexHtmlAsset.source) {
              htmlContent = indexHtmlAsset.source();
            } else if (indexHtmlAsset._source) {
              htmlContent = indexHtmlAsset._source.source
                ? indexHtmlAsset._source.source()
                : (indexHtmlAsset._source._value || '');
            } else {
              htmlContent = indexHtmlAsset._value || '';
            }

            if (Buffer.isBuffer(htmlContent)) {
              htmlContent = htmlContent.toString('utf-8');
            }

            // 从 HTML 中提取 JS 和 CSS 文件路径
            const jsMatches = htmlContent.match(/<script(?![^>]*template)[^>]*src=["']([^"']+\.js[^"']*)["'][^>]*>/gi);
            const cssMatches = htmlContent.match(/<link[^>]*rel=["']stylesheet["'][^>]*href=["']([^"']+\.css[^"']*)["'][^>]*>/gi);

            if (jsMatches && jsMatches.length > 0) {
              const jsMatch = jsMatches[0].match(/src=["']([^"']+\.js[^"']*)["']/i);
              if (jsMatch) {
                entryJs = jsMatch[1];
              }
            }

            if (cssMatches && cssMatches.length > 0) {
              const cssMatch = cssMatches[0].match(/href=["']([^"']+\.css[^"']*)["']/i);
              if (cssMatch) {
                entryCss = cssMatch[1];
              }
            }

            // 删除 index.html
            delete compilation.assets['index.html'];
          }

          // 方法2: 如果从 HTML 中未提取到，直接从 compilation.assets 中查找入口文件
          if (!entryJs || !entryCss) {
            const assetNames = Object.keys(compilation.assets);

            // 查找主入口 JS 文件（通常以 main 开头）
            if (!entryJs) {
              const mainJsFiles = assetNames.filter((name) => {
                return name.match(/^js\/main\.[^/]+\.js$/) || name.match(/^main\.[^/]+\.js$/);
              });
              if (mainJsFiles.length > 0) {
                entryJs = mainJsFiles[0];
              } else {
                // 如果没有找到 main.js，找第一个 JS 文件
                const jsFiles = assetNames.filter(name => name.endsWith('.js') && !name.includes('.worker.'));
                if (jsFiles.length > 0) {
                  entryJs = jsFiles[0];
                }
              }
            }

            // 查找主入口 CSS 文件
            if (!entryCss) {
              const mainCssFiles = assetNames.filter((name) => {
                return name.match(/^css\/main\.[^/]+\.css$/) || name.match(/^main\.[^/]+\.css$/);
              });
              if (mainCssFiles.length > 0) {
                entryCss = mainCssFiles[0];
              } else {
                // 如果没有找到 main.css，找第一个 CSS 文件
                const cssFiles = assetNames.filter(name => name.endsWith('.css'));
                if (cssFiles.length > 0) {
                  entryCss = cssFiles[0];
                }
              }
            }
          }

          // 确保路径是相对路径（相对于 main.js 的位置）
          // 如果路径是绝对路径（以 / 开头），转换为相对路径
          const normalizeToRelativePath = (assetPath) => {
            if (!assetPath) {
              return assetPath;
            }
            // 如果已经是相对路径，直接返回
            if (!assetPath.startsWith('/')) {
              return assetPath;
            }
            // 移除开头的 /，转换为相对路径
            return assetPath.substring(1);
          };

          const entryJsRelative = normalizeToRelativePath(entryJs);
          const entryCssRelative = normalizeToRelativePath(entryCss);

          // 生成 JS 对象内容（CommonJS 模块格式，可被快速 import）
          // 使用相对路径，这样在调用时可以根据 main.js 的位置动态解析
          const manifestContent = `module.exports = ${JSON.stringify({ entryJs: entryJsRelative, entryCss: entryCssRelative }, null, 2)};`;

          // 创建 asset-manifest.js 文件
          compilation.assets[this.outputFileName] = new RawSource(manifestContent);
        } catch (err) {
          compilation.errors.push(new Error(`HtmlToManifestPlugin: ${err.message}`));
        }
      });
    });
  }
};

