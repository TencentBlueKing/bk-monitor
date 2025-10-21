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

// ESLint v9 扁平配置（Flat Config）
// 兼容引入 eslint-config-tencent、plugin:vue/recommended、plugin:prettier/recommended

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { FlatCompat } = require('@eslint/eslintrc');
// eslint-disable-next-line @typescript-eslint/no-require-imports
const js = require('@eslint/js');

const compat = new FlatCompat({ baseDirectory: __dirname });

module.exports = [
  js.configs.recommended,

  // 兼容旧版共享配置
  ...compat.extends('tencent'),
  ...compat.extends('plugin:vue/recommended'),
  ...compat.extends('plugin:prettier/recommended'),

  // 基础语言选项与全局
  {
    files: ['**/*.{js,ts,tsx,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        NODE_ENV: 'readonly',
        __webpack_public_path__: 'readonly'
      }
    },
    plugins: {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      prettier: require('eslint-plugin-prettier')
    },
    rules: {
      // 统一使用单引号
      quotes: ['error', 'single', { avoidEscape: true, allowTemplateLiterals: false }],
      // JSX 属性使用单引号
      'jsx-quotes': ['error', 'prefer-single'],
      'no-param-reassign': 'off',
      'prefer-destructuring': 'off',
      'no-underscore-dangle': 'off',
      'no-restricted-syntax': 'off',
      'array-callback-return': 'off',
      'no-nested-ternary': 'off',
      'arrow-body-style': 'off',
      'no-restricted-properties': 'off',
      'function-paren-newline': 'off',
      // 同步 prettier 的单引号策略
      'prettier/prettier': ['error', { singleQuote: true, jsxSingleQuote: true }]
    }
  },

  // TypeScript / TSX
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      parser: require('@typescript-eslint/parser'),
      parserOptions: {
        project: './tsconfig.json',
        ecmaFeatures: { jsx: true }
      }
    },
    plugins: {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      '@typescript-eslint': require('@typescript-eslint/eslint-plugin')
    }
  },

  // Vue 文件
  {
    files: ['**/*.vue'],
    languageOptions: {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      parser: require('vue-eslint-parser'),
      parserOptions: {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        parser: require('@typescript-eslint/parser'),
        project: './tsconfig.json',
        extraFileExtensions: ['.vue'],
        ecmaFeatures: { jsx: true }
      }
    },
    plugins: {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      vue: require('eslint-plugin-vue')
    },
    rules: {
      'vue/no-lone-template': 'off',
      'vue/no-confusing-v-for-v-if': 'off',
      'vue/multi-word-component-names': 'off',
      'vue/order-in-components': [
        'error',
        {
          order: [
            'el',
            'name',
            'parent',
            'functional',
            ['delimiters', 'comments'],
            ['components', 'directives', 'filters'],
            'extends',
            'mixins',
            'inheritAttrs',
            'model',
            ['props', 'propsData'],
            'data',
            'computed',
            'watch',
            'LIFECYCLE_HOOKS',
            'methods',
            ['template', 'render'],
            'renderError'
          ]
        }
      ],
      'vue/require-default-prop': 'off',
      'vue/no-side-effects-in-computed-properties': 'off'
    }
  }
];