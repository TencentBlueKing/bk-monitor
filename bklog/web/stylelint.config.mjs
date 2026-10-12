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

export default {
  extends: ['stylelint-config-recommended-vue', 'stylelint-config-recess-order'],
  overrides: [
    {
      customSyntax: 'postcss-scss',
      files: ['*.scss', '*.css', '**/*.scss', '**/*.css'],
    },
    {
      customSyntax: 'postcss-sass',
      files: ['*.sass', '**/*.sass'],
    },
    {
      customSyntax: 'postcss-html',
      files: ['*.vue', '**/*.vue'],
    },
  ],
  plugins: ['stylelint-scss', 'stylelint-order'],
  rules: {
    'at-rule-no-unknown': [true, { ignoreAtRules: ['/.*/'] }],
    'at-rule-no-vendor-prefix': true,
    'comment-empty-line-before': ['always', { except: ['first-nested'] }],
    'declaration-no-important': true,
    'max-nesting-depth': 10,
    'media-feature-name-no-vendor-prefix': true,
    'order/order': ['declarations', { type: 'at-rule' }, { hasBlock: true, type: 'at-rule' }, 'rules'],
    'property-no-vendor-prefix': true,
    'rule-empty-line-before': ['always', { except: ['first-nested'], ignore: ['after-comment'] }],
    'scss/at-extend-no-missing-placeholder': true,
    'scss/dollar-variable-pattern': '^_?[a-z]+[\\w-]*$',
    'selector-max-id': 3,
    'selector-no-vendor-prefix': true,
    'value-no-vendor-prefix': true,
  },
};
