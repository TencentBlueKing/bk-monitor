const typescriptEslint = require('@typescript-eslint/eslint-plugin');
const eslintConfigPrettier = require('eslint-config-prettier');
const prettier = require('eslint-plugin-prettier');
const typescriptEslintParser = require('@typescript-eslint/parser');
const codecc = require('eslint-plugin-codecc');
const eslintVueParser = require('vue-eslint-parser');
// const perfectionistNatural = require('eslint-plugin-perfectionist/configs/recommended-natural');
const simpleImportSort = require('eslint-plugin-simple-import-sort');
const eslintVuePlugin = require('eslint-plugin-vue');
const tencentEslintLegacyRules = require('eslint-config-tencent/ts').rules; // tencent ts eslint
//deprecating formatting rules https://typescript-eslint.io/blog/deprecating-formatting-rules
const deprecateRules = {
  '@typescript-eslint/ban-ts-comment': 'off',
  '@typescript-eslint/block-spacing': 'off',
  '@typescript-eslint/brace-style': 'off',
  '@typescript-eslint/comma-dangle': 'off',
  '@typescript-eslint/comma-spacing': 'off',
  '@typescript-eslint/func-call-spacing': 'off',
  '@typescript-eslint/indent': 'off',
  '@typescript-eslint/key-spacing': 'off',
  '@typescript-eslint/keyword-spacing': 'off',
  '@typescript-eslint/lines-around-comment': 'off',
  '@typescript-eslint/lines-between-class-members': 'off',
  '@typescript-eslint/member-delimiter-style': 'off',
  '@typescript-eslint/no-explicit-any': 'off',
  '@typescript-eslint/no-extra-parens': 'off',
  '@typescript-eslint/no-extra-semi': 'off',
  '@typescript-eslint/padding-line-between-statements': 'off',
  '@typescript-eslint/quotes': 'off',
  '@typescript-eslint/semi': 'off',
  '@typescript-eslint/space-before-blocks': 'off',
  '@typescript-eslint/space-before-function-paren': 'off',
  '@typescript-eslint/space-infix-ops': 'off',
  '@typescript-eslint/type-annotation-spacing': 'off',
};
module.exports = [
  {
    ignores: ['node_modules', 'dist', 'vue2/*', 'vue3/*'],
  },
  eslintConfigPrettier,
  // perfectionistNatural,
  {
    plugins: {
      prettier,
    },
    rules: {
      ...prettier.configs.recommended.rules,
    },
  },
  {
    files: ['src/**/*.ts', 'src/**/*.tsx', 'webpack/**/*.js', './*.js'],
    ignores: [],
    languageOptions: {
      parser: typescriptEslintParser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
          legacyDecorators: true,
        },
        ecmaVersion: 'latest',
        project: true,
        // sourceType: 'module',
        // tsconfigRootDir: __dirname,
      },
    },
    linterOptions: {},
    plugins: {
      '@typescript-eslint': typescriptEslint,
      codecc,
      'simple-import-sort': simpleImportSort,
    },
    rules: {
      'codecc/license': [
        'error',
        {
          license: `/*
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
*/\n`,
          pattern: '.*Tencent is pleased to support the open source community.+',
        },
      ],
      ...typescriptEslint.configs.recommended.rules,
      ...tencentEslintLegacyRules,
      ...deprecateRules,
      // 'import/first': 'error',
      // 'import/newline-after-import': 'error',
      // 'import/no-duplicates': 'error',
      'simple-import-sort/exports': 'error',
      'simple-import-sort/imports': [
        'error',
        {
          groups: [
            [
              '^(assert|buffer|child_process|cluster|console|constants|crypto|dgram|dns|domain|events|fs|http|https|module|net|os|path|punycode|querystring|readline|repl|stream|string_decoder|sys|timers|tls|tty|url|util|vm|zlib|freelist|v8|process|async_hooks|http2|perf_hooks)(/.*|$)',
            ],
            // Packages. `react` related packages come first.
            ['^vue', '^@?\\w'],
            // Internal packages.
            ['^(@|@company|@ui|components|utils|config|vendored-lib)(/.*|$)'],
            // Side effect imports.
            ['^\\u0000'],
            // Parent imports. Put `..` last.
            ['^\\.\\.(?!/?$)', '^\\.\\./?$'],
            // Other relative imports. Put same-folder imports and `.` last.
            ['^\\./(?=.*/)(?!/?$)', '^\\.(?!/?$)', '^\\./?$'],
            // Style imports.
            ['^.+\\.s?css$'],
          ],
        },
      ],
    },
    settings: {},
  },
  {
    files: ['src/**/*.vue'],
    languageOptions: {
      parser: eslintVueParser,
      parserOptions: {
        allowAutomaticSingleRunInference: false,
        ecmaFeatures: {
          jsx: true,
          legacyDecorators: true,
        },
        ecmaVersion: 'latest',
        extraFileExtensions: ['.vue'],
        parser: {
          '<template>': 'espree',
          ts: typescriptEslintParser,
        },
        project: true,
      },
    },
    plugins: {
      '@typescript-eslint': typescriptEslint,
      vue: eslintVuePlugin,
      'simple-import-sort': simpleImportSort,
    },
    rules: {
      ...eslintVuePlugin.configs['vue3-recommended'].rules,
      ...tencentEslintLegacyRules,
      '@typescript-eslint/explicit-member-accessibility': 'off',
      'comma-dangle': ['error', 'always-multiline'],
      'vue/attributes-order': 'off',
      ...deprecateRules,
    },
  },
];
