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
module.exports = function (api) {
  api && api.cache.never();
  const presets = [
    [
      '@babel/preset-env',
      {
        targets: {
          browsers: ['> 1%', 'last 1 versions', 'not ie <= 11'],
          node: 'current'
        },
        useBuiltIns: 'usage',
        corejs: 3,
        debug: false
      }
    ],
    process.env.APP !== 'trace' ? [
      '@vue/babel-preset-jsx',
      {
        compositionAPI: 'auto',
      }
    ] : undefined
  ].filter(Boolean);
  const plugins = [
    '@babel/plugin-transform-runtime',
    // process.env.APP !== 'trace' ? [
    //   'babel-plugin-import-bk-magic-vue',
    //   {
    //     baseLibName: 'bk-magic-vue'
    //   }
    // ] : undefined,
    process.env.APP === 'pc' ? [
      'component',
      {
        libraryName: 'element-ui',
        styleLibraryName: 'theme-chalk'
      }
    ] : undefined,
    process.env.APP === 'mobile' ? [
      'import',
      {
        libraryName: 'vant',
        libraryDirectory: 'es',
        style: true
      },
      'vant'
    ] : undefined,
    process.env.APP === 'trace' ? '@vue/babel-plugin-jsx' : undefined,
    process.env.APP === 'trace' ? [
      'import-bkui-vue',
      {
        libraryName: 'bkui-vue',
        style: true
      }
    ] : undefined
  ].filter(Boolean);
  return {
    presets,
    plugins
  };
};
