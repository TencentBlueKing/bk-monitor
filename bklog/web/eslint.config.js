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
const typescriptEslint = require('@typescript-eslint/eslint-plugin');
const typescriptEslintParser = require('@typescript-eslint/parser');
const codecc = require('eslint-plugin-codecc');
const eslintVueParser = require('vue-eslint-parser');
const perfectionist = require('eslint-plugin-perfectionist');
const eslintVuePlugin = require('eslint-plugin-vue');
const { rules: tencentEslintLegacyRules } = require('eslint-config-tencent/ts');

const deprecateRules = Object.fromEntries(
  [
    'ban-ts-comment',
    'block-spacing',
    'brace-style',
    'comma-dangle',
    'comma-spacing',
    'func-call-spacing',
    'indent',
    'key-spacing',
    'keyword-spacing',
    'lines-around-comment',
    'lines-between-class-members',
    'member-delimiter-style',
    'no-extra-parens',
    'no-extra-semi',
    'padding-line-between-statements',
    'quotes',
    'semi',
    'space-before-blocks',
    'space-before-function-paren',
    'space-infix-ops',
    'type-annotation-spacing',
  ].map(rule => [`@typescript-eslint/${rule}`, 'off']),
);
const jsxOrVueSortGroups = {
  'custom-groups': {
    DEFINITION: '*(is|vIs|v-is)',
    LIST_RENDERING: '*(v-for|vFor)',
    CONDITIONALS: '*(v-if|v-else-if|v-else|vIf|vElseIf|vElse)',
    RENDER_MODIFIERS: '*(v-pre|v-once|vPre|vOnce)',
    GLOBAL: 'id',
    UNIQUE: '*(ref|key)',
    WIDTH: 'width',
    HEIGHT: 'height',
    STYLE: '*style',
    CLASS: '*(class|ext-cls|extCls)',
    TWO_WAY_BINDING: '*(v-model|vModel)',
    SLOT: '*(v-slot|slot|vSlot)',
    OTHER_DIRECTIVES: 'v-*',
    EVENTS: '*(on*|v-on|vOn|@*)',
    CONTENT: '*(v-html|v-text|vHtml|vText)',
  },
  groups: [
    'DEFINITION',
    'LIST_RENDERING',
    'CONDITIONALS',
    'RENDER_MODIFIERS',
    'GLOBAL',
    'UNIQUE',
    'STYLE',
    'WIDTH',
    'HEIGHT',
    'CLASS',
    'TWO_WAY_BINDING',
    'SLOT',
    'OTHER_DIRECTIVES',
    'multiline',
    'unknown',
    'shorthand',
    'EVENTS',
  ],
};
module.exports = [
  {
    files: ['*.js', '**/*.js', '*.ts', '**/*.ts'],
    ignores: ['*.tsx', '**/*.tsx', '*.vue', '**/*.vue'],
    plugins: { perfectionist },
    rules: {
      'perfectionist/sort-classes': [
        'error',
        {
          groups: [
            'decorated-accessor-property',
            'static-private-method',
            'private-property',
            'static-property',
            'index-signature',
            'private-method',
            'static-method',
            'property',
            'private-decorated-accessor-property',
            'private-decorated-property',
            'decorated-property',
            'constructor',
            ['get-method', 'set-method'],
            'decorated-set-method',
            'decorated-get-method',
            'decorated-method',
            'unknown',
            'method',
          ],
          order: 'asc',
          type: 'natural',
        },
      ],
      // 'perfectionist/sort-objects': [
      //   'error',
      //   {
      //     'custom-groups': {
      //       ID: '*(id|ID|Id)',
      //       NAME: '*(name|Name|NAME)',
      //       path: 'path',
      //       // components: 'components',
      //       // directives: 'directives',
      //       // emits: 'emits',
      //       // props: 'props',
      //       // setup: 'setup',
      //       // render: 'render',
      //     },
      //     groups: ['ID', 'NAME', 'path', 'unknown'],
      //     order: 'asc',
      //     'partition-by-comment': 'Part:**',
      //     type: 'natural',
      //   },
      // ],
    },
  },
  {
    plugins: { perfectionist },
    rules: {
      'perfectionist/sort-enums': [
        'error',
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-exports': [
        'error',
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-imports': [
        'error',
        {
          'custom-groups': {
            type: {
              magicBox: 'magicBox',
              top: 'top',
              tsxSupport: 'tsxSupport',
              vueI18n: 'vueI18n',
            },
            value: {
              magicBox: ['./common/import-magicbox-ui', 'monitor-ui/directive/index', 'monitor-static/svg-icons'],
              top: ['./public-path', './public-path.ts', 'monitor-common/polyfill'],
              tsxSupport: ['vue-property-decorator', 'vue-tsx-support'],
              vueI18n: ['./i18n/i18n', 'vue', 'vue-*'],
            },
          },
          groups: [
            'top',
            'vueI18n',
            'magicBox',
            'tsxSupport',
            ['builtin', 'external'],
            ['internal', 'sibling', 'parent', 'side-effect', 'index', 'object'],
            'unknown',
            ['type', 'builtin-type', 'external-type', 'internal-type', 'parent-type', 'sibling-type', 'index-type'],
            ['style', 'side-effect-style'],
          ],
          'internal-pattern': ['@/*', '@router/*', '@store/*', '@page/*', '@static/*'],
          'newlines-between': 'always',
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-jsx-props': [
        'error',
        {
          ...jsxOrVueSortGroups,
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-maps': [
        'error',
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      // 'perfectionist/sort-intersection-types': [
      //   'error',
      //   {
      //     type: 'natural',
      //     order: 'asc',
      //   },
      // ],
      'perfectionist/sort-union-types': [
        'error',
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-vue-attributes': [
        'error',
        {
          ...jsxOrVueSortGroups,
          type: 'natural',
          order: 'asc',
        },
      ],
    },
  },
  {
    files: ['*.js', '**/*.js', '*.ts', '**/*.ts', '*.tsx', '**/*.tsx'],
    ignores: [],
    languageOptions: {
      parser: typescriptEslintParser,
      parserOptions: {
        ecmaVersion: 'latest',
        project: true,
      },
    },
    plugins: {
      '@typescript-eslint': typescriptEslint,
      codecc,
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
    },
  },
  ...eslintVuePlugin.configs['flat/recommended'].map(config =>
    config.files
      ? {
          ...config,
          files: ['*.vue', '**/*.vue'],
          languageOptions: {
            ...config.languageOptions,
            parser: eslintVueParser,
            parserOptions: {
              ...config.languageOptions.parserOptions,
              allowAutomaticSingleRunInference: false,
              ecmaFeatures: { jsx: true, legacyDecorators: true },
              ecmaVersion: 'latest',
              extraFileExtensions: ['.vue'],
              parser: typescriptEslintParser,
              project: true,
              tsconfigRootDir: process.cwd(),
            },
          },
          plugins: {
            '@typescript-eslint': typescriptEslint,
            vue: eslintVuePlugin,
          },
          rules: {
            ...config.rules,
            ...tencentEslintLegacyRules,
            '@typescript-eslint/explicit-member-accessibility': 'off',
            'comma-dangle': ['error', 'always-multiline'],
            ...deprecateRules,
          },
        }
      : config,
  ),
  {
    rules: {
      'vue/html-self-closing': 'off',
      'vue/require-default-prop': 'off',
      'vue/attributes-order': 'off',
    },
  },
  {
    ignores: ['node_modules'],
  },
  {
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/no-reserved-component-names': 'off',
      'vue/no-deprecated-v-bind-sync': 'off',
      'vue/require-explicit-emits': 'off',
      '@typescript-eslint/no-require-imports': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-var-requires': 'off',
      '@typescript-eslint/dot-notation': [
        'error',
        {
          allowKeywords: true,
        },
      ],
      'perfectionist/sort-classes': 'off',
      'declaration-no-important': 'off',
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
  }
];
