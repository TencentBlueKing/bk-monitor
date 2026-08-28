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

import path from 'node:path';
import { fileURLToPath } from 'node:url';

import js from '@eslint/js';
import eslintConfigPrettier from 'eslint-config-prettier';
import createTencentConfig from 'eslint-config-tencent/flat';
import vuePlugin from 'eslint-plugin-vue';
import globals from 'globals';
import typescriptEslint from 'typescript-eslint';
import vueParser from 'vue-eslint-parser';

const dirname = path.dirname(fileURLToPath(import.meta.url));

const typescriptProblemRules = {
  '@typescript-eslint/no-duplicate-enum-values': 'error',
  '@typescript-eslint/no-extra-non-null-assertion': 'error',
  '@typescript-eslint/no-misused-new': 'error',
  '@typescript-eslint/no-namespace': 'error',
  '@typescript-eslint/no-non-null-asserted-optional-chain': 'error',
  '@typescript-eslint/no-unnecessary-type-constraint': 'error',
  '@typescript-eslint/no-unsafe-declaration-merging': 'error',
  '@typescript-eslint/prefer-as-const': 'error',
  '@typescript-eslint/prefer-namespace-keyword': 'error',
};

const typescriptMigrationWarnings = {
  '@typescript-eslint/no-empty-object-type': 'warn',
  '@typescript-eslint/no-this-alias': 'warn',
  '@typescript-eslint/no-unused-expressions': 'warn',
  '@typescript-eslint/triple-slash-reference': 'warn',
};

export default [
  {
    ignores: ['.aafe/**', 'node_modules/**', 'packages/web-v1/**', 'monitor-*/**'],
  },
  js.configs.recommended,
  ...createTencentConfig({}),
  ...vuePlugin.configs['flat/recommended'],
  {
    files: ['src/**/*.{js,ts,tsx,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.commonjs,
        NODE_ENV: 'readonly',
        __webpack_public_path__: 'readonly',
      },
    },
    rules: {
      'array-callback-return': 'off',
      'arrow-body-style': 'off',
      'function-paren-newline': 'off',
      'linebreak-style': 'off',
      'no-nested-ternary': 'off',
      'no-param-reassign': 'off',
      'no-restricted-properties': 'off',
      'no-restricted-syntax': 'off',
      'no-underscore-dangle': 'off',
      'prefer-destructuring': 'off',
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: typescriptEslint.parser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
        project: './tsconfig.json',
        tsconfigRootDir: dirname,
      },
    },
    plugins: {
      '@typescript-eslint': typescriptEslint.plugin,
    },
    rules: {
      'no-undef': 'off',
      'no-unused-expressions': 'off',
      'no-unused-vars': 'off',
      ...typescriptProblemRules,
      ...typescriptMigrationWarnings,
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-require-imports': 'off',
      '@typescript-eslint/no-unnecessary-parameter-property-assignment': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          args: 'after-used',
          argsIgnorePattern: '^_.+',
          ignoreRestSiblings: true,
          varsIgnorePattern: '^_.+',
        },
      ],
      '@typescript-eslint/no-useless-empty-export': 'warn',
      '@typescript-eslint/no-var-requires': 'off',
      '@typescript-eslint/no-wrapper-object-types': 'warn',
    },
  },
  {
    files: ['src/**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
        extraFileExtensions: ['.vue'],
        parser: typescriptEslint.parser,
      },
    },
    plugins: {
      '@typescript-eslint': typescriptEslint.plugin,
    },
    rules: {
      'no-unused-expressions': 'off',
      ...typescriptProblemRules,
      ...typescriptMigrationWarnings,
      '@typescript-eslint/no-require-imports': 'off',
      '@typescript-eslint/no-var-requires': 'off',
      'vue/multi-word-component-names': 'off',
      'vue/no-confusing-v-for-v-if': 'off',
      'vue/no-lone-template': 'off',
      'vue/no-side-effects-in-computed-properties': 'off',
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
            'renderError',
          ],
        },
      ],
      'vue/require-default-prop': 'off',
    },
  },
  eslintConfigPrettier,
];
