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

module.exports = {
  root: true,
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: {
      js: '@typescript-eslint/parser',
      ts: '@typescript-eslint/parser',
      '<template>': 'espree'
    },
    ecmaVersion: 2018,
    sourceType: 'module',
    extraFileExtensions: ['.vue'],
    ecmaFeatures: {
      globalReturn: false,
      impliedStrict: false,
      jsx: true
    }
  },
  extends: ['eslint-config-tencent', 'plugin:vue/recommended'],
  globals: {
    NODE_ENV: false,
    __webpack_public_path__: false
  },
  plugins: ['prettier'],
  rules: {
    'no-param-reassign': 'off',
    'prefer-destructuring': 'off',
    'no-underscore-dangle': 'off',
    'no-restricted-syntax': 'off',
    'array-callback-return': 'off',
    'no-nested-ternary': 'off',
    'arrow-body-style': 'off',
    'no-restricted-properties': 'off',
    'function-paren-newline': 'off',
    'vue/no-lone-template': 'off',
    'vue/no-confusing-v-for-v-if': 'off',
    'vue/multi-word-component-names': 'off',
    'prettier/prettier': 'error',
    // props 必须要有默认值，不限制
    'vue/require-default-prop': 'off',
    // 禁止在计算属性对属性进行修改，不限制
    'vue/no-side-effects-in-computed-properties': 'off',
    // 官方推荐顺序
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
    ]
  },
  overrides: [
    {
      files: ['*.vue', '*.js', '*.ts', '*.tsx'],
      extends: ['plugin:prettier/recommended']
    }
  ]
};
