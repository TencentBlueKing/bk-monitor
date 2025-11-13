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
const fs = require('node:fs');
const postcss = require('postcss');
const { resolve } = require('node:path');

const input = fs.readFileSync(resolve(__dirname, '../node_modules/bk-magic-vue/dist/bk-magic-vue.min.css'), 'utf-8'); // 需要添加前缀的输入文件
postcss([
  postcss.plugin('postcss-add-monitor-class', () => {
    return root => {
      root.walkRules(rule => {
        // 对于每个规则，更新它的选择器
        rule.selectors = rule.selectors.map(selector => {
          if (/^\.(tippy-|bk-tooltip-|bk-option-|bk-select-search-input|bk-select-dropdown-)/.test(selector)) {
            return selector;
          }
          // if (/^\.(bk-form-|bk-input-|bk-button-|bk-select-dropdown-)/.test(selector)) {
          //   return `.monitor-trace-log ${selector}, .tippy-content ${selector}`;
          // }
          return `.tippy-content ${selector}, .monitor-trace-log ${selector}`;
        });
      });
    };
  }),
])
  .process(input, { from: undefined })
  .then(result => {
    const cssText = result.css.replace(/url\((fonts|images)([^)]+)(\))/gim, 'url(../$1$2$3');
    fs.appendFileSync(resolve(__dirname, '../monitor-trace-retrieve/css/main.css'), cssText); // 最终生成的文件
  });
