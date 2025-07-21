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
module.exports = [
  ...require('@blueking/bkui-lint/eslint'),
  {
    plugins: {
      security: require('eslint-plugin-security'),
    },
    rules: {
      '@typescript-eslint/dot-notation': [
        'error',
        {
          allowKeywords: true,
        },
      ],
      '@typescript-eslint/naming-convention': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-require-imports': 'off',
      '@typescript-eslint/no-var-requires': 'off',
      'declaration-no-important': 'off',
      'perfectionist/sort-classes': 'off',
      'perfectionist/sort-enums': [
        'error',
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      // 排序规则
      'perfectionist/sort-imports': [
        'error',
        {
          groups: [
            'type',
            'react',
            'builtin',
            'external',
            'internal',
            'parent',
            'sibling',
            'index',
            'object',
            'unknown',
          ],
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-jsx-props': [
        'error',
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-objects': [
        'error',
        {
          order: 'asc',
          type: 'natural',
        },
      ],

      // 'security/detect-disable-mustache-escape': 'warn',
      'security/detect-eval-with-expression': 'error',
      // 基础规则
      'vue/multi-word-component-names': 'off',
      'vue/no-deprecated-v-bind-sync': 'off',
      'vue/no-reserved-component-names': 'off',

      // 安全检测规则
      // 'security/detect-object-injection': 'warn',
      // 'security/detect-non-literal-regexp': 'warn',
      // 'security/detect-unsafe-regex': 'warn',
      // 'security/detect-buffer-noassert': 'warn',
      // 'security/detect-child-process': 'warn',
      'vue/require-explicit-emits': 'off',
      // 'security/detect-no-csrf-before-method-override': 'warn',
      // 'security/detect-non-literal-fs-filename': 'warn',
      // 'security/detect-non-literal-require': 'warn',
      // 'security/detect-possible-timing-attacks': 'warn',
      // 'security/detect-pseudoRandomBytes': 'warn',
    },
  },
  {
    ignores: [
      '**/node_modules',
      '**/lib',
      '**/dist',
      '/dev',
      '/docs',
      '/plugins',
      '/src/__tests__/demos',
      'src/**/.config',
    ],
  },
];
