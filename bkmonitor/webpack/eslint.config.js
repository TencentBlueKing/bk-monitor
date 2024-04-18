const typescriptEslint = require('@typescript-eslint/eslint-plugin');
const eslintConfigPrettier = require('eslint-config-prettier');
const prettier = require('eslint-plugin-prettier');
const typescriptEslintParser = require('@typescript-eslint/parser');
const codecc = require('eslint-plugin-codecc');
const eslintVueParser = require('vue-eslint-parser');
// const perfectionist = require('eslint-plugin-perfectionist');
const simpleImportSort = require('eslint-plugin-simple-import-sort');
const eslintVuePlugin = require('eslint-plugin-vue');
const tencentEslintLegacyRules = require('eslint-config-tencent/ts').rules;
// const tencentEslintBaseRules = require('eslint-config-tencent/base').rules;
const importSortRules = {
  'simple-import-sort/exports': 'error',
  'simple-import-sort/imports': [
    'error',
    {
      groups: [
        // System packages
        [
          '^(assert|buffer|child_process|cluster|console|constants|crypto|dgram|dns|domain|events|fs|http|https|module|net|os|path|punycode|querystring|readline|repl|stream|string_decoder|sys|timers|tls|tty|url|util|vm|zlib|freelist|v8|process|async_hooks|http2|perf_hooks)(/.*|$)',
        ],
        // Vue & external packages
        ['^vue', '^@?\\w'],
        // Internal packages
        ['^(@|@company|@ui|components|utils|config|vendored-lib)(/.*|$)'],
        ['^\\u0000'], // Side effect imports
        ['^\\.\\.(?!/?$)', '^\\.\\./?$'], // Parent imports
        ['^\\./(?=.*/)(?!/?$)', '^\\.(?!/?$)', '^\\./?$'], // Other relative imports
        ['^.+\\.s?css$'], // Style imports
      ],
    },
  ],
};

// Deprecate formatting rules https://typescript-eslint.io/blog/deprecating-formatting-rules
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
    'no-explicit-any',
    'no-extra-parens',
    'no-extra-semi',
    'padding-line-between-statements',
    'quotes',
    'semi',
    'space-before-blocks',
    'space-before-function-paren',
    'space-infix-ops',
    'type-annotation-spacing',
    'no-misused-promises',
  ].map(rule => [`@typescript-eslint/${rule}`, 'off']),
);

const recommendedVue2Config = eslintVuePlugin.configs['flat/vue2-recommended'].find(config => config.files);
const jsVueFiles = ['src/monitor-pc/pages/collector-config/**/*.vue', 'src/monitor-pc/pages/plugin-manager/**/*.vue'];
const vueCommonRules = {
  'vue/html-self-closing': [
    'error',
    {
      html: {
        component: 'always',
        normal: 'always',
        void: 'always',
      },
      math: 'always',
      svg: 'always',
    },
  ],
};
module.exports = [
  {
    ignores: [
      'node_modules',
      'dist',
      '*.json',
      './monitor/*',
      './apm/*',
      './fta/*',
      './weixin/*',
      './trace/*',
      './external/*',
      './mp/*',
    ],
  },
  eslintConfigPrettier,
  {
    plugins: { prettier },
    rules: { ...prettier.configs.recommended.rules },
  },
  // {
  //   files: ['src/**/*.ts', 'src/**/*.js'],
  //   ignores: ['src/**/*.tsx', 'src/**/*.vue'],
  //   plugins: { perfectionist },
  //   rules: {
  //     'perfectionist/sort-classes': [
  //       'error',
  //       {
  //         groups: [
  //           'private-decorated-accessor-property',
  //           'decorated-accessor-property',
  //           'private-decorated-property',
  //           'static-private-method',
  //           'decorated-set-method',
  //           'decorated-get-method',
  //           'decorated-property',
  //           'decorated-method',
  //           'private-property',
  //           'static-property',
  //           'index-signature',
  //           'private-method',
  //           'static-method',
  //           'property',
  //           'constructor',
  //           ['get-method', 'set-method'],
  //           'unknown',
  //           'method',
  //         ],
  //         order: 'asc',
  //         type: 'natural',
  //       },
  //     ],
  //     'perfectionist/sort-objects': [
  //       'error',
  //       {
  //         'custom-groups': {
  //           ID: '*(id|ID|Id)',
  //           NAME: '*(name|Name|NAME)',
  //           components: 'components',
  //           directives: 'directives',
  //           emits: 'emits',
  //           props: 'props',
  //           setup: 'setup',
  //           render: 'render',
  //         },
  //         groups: ['ID', 'NAME', 'components', 'directives', 'emits', 'props', 'setup', 'render', 'unknown'],
  //         order: 'asc',
  //         'partition-by-comment': 'Part:**',
  //         type: 'natural',
  //       },
  //     ],
  //   },
  // },
  // {
  //   plugins: { perfectionist },
  //   rules: {
  //     'perfectionist/sort-enums': [
  //       'error',
  //       {
  //         order: 'asc',
  //         type: 'natural',
  //       },
  //     ],
  //     'perfectionist/sort-exports': [
  //       'error',
  //       {
  //         order: 'asc',
  //         type: 'natural',
  //       },
  //     ],
  //     'perfectionist/sort-jsx-props': [
  //       'error',
  //       {
  //         'custom-groups': {
  //           CLASS: '*class',
  //           DEFINITION: 'is',
  //           DIRECTIVE: 'v-*',
  //           EVENTS: '*(on*|v-on)',
  //           GLOBAL: 'id',
  //           SLOT: '*(v-slot|slot)',
  //           STYLE: '*style',
  //           TWO_WAY_BINDING: '*(v-model|vModel)',
  //           UNIQUE: '*(ref|key)',
  //         },
  //         groups: [
  //           'DEFINITION',
  //           'GLOBAL',
  //           'UNIQUE',
  //           'STYLE',
  //           'CLASS',
  //           'TWO_WAY_BINDING',
  //           'SLOT',
  //           'DIRECTIVE',
  //           'multiline',
  //           'unknown',
  //           'shorthand',
  //           'EVENTS',
  //         ],
  //         order: 'asc',
  //         type: 'natural',
  //       },
  //     ],
  //     'perfectionist/sort-maps': [
  //       'error',
  //       {
  //         order: 'asc',
  //         type: 'natural',
  //       },
  //     ],
  //     'perfectionist/sort-imports': [
  //       'error',
  //       {
  //         type: 'natural',
  //         order: 'asc',
  //         groups: [
  //           'top',
  //           'vueI18n',
  //           'magicBox',
  //           'tsxSupport',
  //           ['builtin', 'external'],
  //           ['internal', 'sibling', 'parent', 'side-effect', 'index', 'object'],
  //           'unknown',
  //           ['type', 'builtin-type', 'external-type', 'internal-type', 'parent-type', 'sibling-type', 'index-type'],
  //           ['style', 'side-effect-style'],
  //         ],
  //         'custom-groups': {
  //           value: {
  //             top: ['./public-path', './public-path.ts', 'monitor-common/polyfill'],
  //             vueI18n: ['./i18n/i18n', 'vue'],
  //             magicBox: ['./common/import-magicbox-ui', 'monitor-ui/directive/index', 'monitor-static/svg-icons'],
  //             tsxSupport: ['vue-property-decorator', 'vue-tsx-support'],
  //           },
  //           type: {
  //             top: 'top',
  //             vueI18n: 'vueI18n',
  //             magicBox: 'magicBox',
  //             tsxSupport: 'tsxSupport',
  //           },
  //         },
  //         'newlines-between': 'always',
  //         // 'internal-pattern': ['@/components/**', '@/stores/**', '@/pages/**', '@/lib/**'],
  //       },
  //     ],
  //     // 'perfectionist/sort-intersection-types': [
  //     //   'error',
  //     //   {
  //     //     type: 'natural',
  //     //     order: 'asc',
  //     //   },
  //     // ],
  //     'perfectionist/sort-union-types': [
  //       'error',
  //       {
  //         order: 'asc',
  //         type: 'natural',
  //       },
  //     ],
  //   },
  // },
  {
    files: ['src/**/*.ts', 'src/**/*.tsx', './**/*.js'],
    ignores: [],
    languageOptions: {
      parser: typescriptEslintParser,
      parserOptions: {
        ecmaFeatures: { jsx: true, legacyDecorators: true },
        ecmaVersion: 'latest',
        project: true,
      },
    },
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
      ...importSortRules,
    },
  },
  ...eslintVuePlugin.configs['flat/vue2-recommended'].filter(config => !config.files?.length),
  {
    ...recommendedVue2Config,
    files: ['src/**/*.vue'],
    ignores: jsVueFiles,
    languageOptions: {
      ...recommendedVue2Config.languageOptions,
      parser: eslintVueParser,
      parserOptions: {
        ...recommendedVue2Config.languageOptions.parserOptions,
        allowAutomaticSingleRunInference: false,
        ecmaFeatures: { jsx: true, legacyDecorators: true },
        ecmaVersion: 'latest',
        extraFileExtensions: ['.vue'],
        parser: {
          cjs: 'espree',
          cts: typescriptEslintParser,
          js: 'espree',
          jsx: 'espree',
          mjs: 'espree',
          mts: typescriptEslintParser,
          ts: typescriptEslintParser,
          tsx: typescriptEslintParser,
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
      ...recommendedVue2Config.rules,
      ...tencentEslintLegacyRules,
      '@typescript-eslint/explicit-member-accessibility': 'off',
      'comma-dangle': ['error', 'always-multiline'],
      ...importSortRules,
      ...deprecateRules,
      ...vueCommonRules,
    },
  },
  {
    ...recommendedVue2Config,
    files: jsVueFiles,
    rules: {
      ...vueCommonRules,
    },
  },
];
