const eslintVueParser = require('vue-eslint-parser');

const typescriptEslint = require('@typescript-eslint/eslint-plugin');
const typescriptEslintParser = require('@typescript-eslint/parser');
const eslintConfigPrettier = require('eslint-config-prettier');
const codecc = require('eslint-plugin-codecc');
const perfectionist = require('eslint-plugin-perfectionist');
const prettier = require('eslint-plugin-prettier');
const eslintVuePlugin = require('eslint-plugin-vue');
const tencentEslintLegacyRules = require('eslint-config-tencent/ts').rules;
// const tailwind = require('eslint-plugin-tailwindcss');

const OFF = 0;
const WARNING = 1;
const ERROR = 2;
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
  ].map(rule => [`@typescript-eslint/${rule}`, OFF])
);
const recommendedVue2Config = eslintVuePlugin.configs['flat/vue2-recommended'].find(config => config.files);
// 以下是 script = js 的vue 文件 需要和 ts 分开检测
const jsVueFiles = [
  'src/monitor-pc/components/editors/**/*.vue',
  'src/monitor-pc/components/history-dialog/**/*.vue',
  'src/monitor-pc/components/ip-select/**/*.vue',
  'src/monitor-pc/components/log-version/**/*.vue',
  'src/monitor-pc/components/metric-dimension/**/*.vue',
  'src/monitor-pc/components/metric-select/**/*.vue',
  'src/monitor-pc/components/monitor-date-range/**/*.vue',
  'src/monitor-pc/components/polling-loading/**/*.vue',
  'src/monitor-pc/components/svg-icon/**/*.vue',
  'src/monitor-pc/components/svg-wrap/**/*.vue',
  'src/monitor-pc/components/table-filter/**/*.vue',
  'src/monitor-pc/components/verify-input/**/*.vue',
  'src/monitor-pc/pages/alarm-group/**/*.vue',
  'src/monitor-pc/pages/alarm-shield/**/*.vue',
  'src/monitor-pc/pages/collector-config/**/*.vue',
  'src/monitor-pc/pages/collector-upgrade/**/*.vue',
  'src/monitor-pc/pages/event-center/**/*.vue',
  'src/monitor-pc/pages/export-import/**/*.vue',
  'src/monitor-pc/pages/global-config/**/*.vue',
  'src/monitor-pc/pages/home/**/*.vue',
  'src/monitor-pc/pages/monitor-navigation/**/*.vue',
  'src/monitor-pc/pages/performance/*.vue',
  'src/monitor-pc/pages/plugin-manager/**/*.vue',
  'src/monitor-pc/pages/service-classify/**/*.vue',
  'src/monitor-pc/pages/shell-collector/**/*.vue',
  'src/monitor-pc/pages/strategy-config/**/*.vue',
  'src/monitor-pc/pages/uptime-check/**/*.vue',
];
const jsxOrVueSortGroups = {
  customGroups: {
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
  {
    plugins: { prettier },
    rules: { ...prettier.configs.recommended.rules },
  },
  {
    files: ['src/**/*.ts', 'src/**/*.js'],
    ignores: ['src/**/*.tsx', 'src/**/*.vue'],
    plugins: { perfectionist },
    rules: {
      'perfectionist/sort-classes': [
        ERROR,
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
      //   ERROR,
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
        ERROR,
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-exports': [
        ERROR,
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-jsx-props': [
        ERROR,
        {
          ...jsxOrVueSortGroups,
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-maps': [
        ERROR,
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-imports': [
        ERROR,
        {
          type: 'natural',
          order: 'asc',
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
          customGroups: {
            value: {
              top: ['./public-path', './public-path.ts', 'monitor-common/polyfill'],
              vueI18n: ['./i18n/i18n', 'vue', 'vue-*'],
              magicBox: ['./common/import-magicbox-ui', 'monitor-ui/directive/index', 'monitor-static/svg-icons'],
              tsxSupport: ['vue-property-decorator', 'vue-tsx-support'],
            },
            type: {
              top: 'top',
              vueI18n: 'vueI18n',
              magicBox: 'magicBox',
              tsxSupport: 'tsxSupport',
            },
          },
          newlinesBetween: 'always',
          internalPattern: ['@/*', '@router/*', '@store/*', '@page/*', '@static/*'],
          sortSideEffects: true,
        },
      ],
      // 'perfectionist/sort-intersection-types': [
      //   ERROR,
      //   {
      //     type: 'natural',
      //     order: 'asc',
      //   },
      // ],
      'perfectionist/sort-union-types': [
        ERROR,
        {
          order: 'asc',
          type: 'natural',
        },
      ],
      'perfectionist/sort-vue-attributes': [
        ERROR,
        {
          ...jsxOrVueSortGroups,
          type: 'natural',
          order: 'asc',
        },
      ],
    },
  },
  {
    files: ['src/**/*.ts', 'src/**/*.tsx', './**/*.js', 'src/**/*.js'],
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
    },
    rules: {
      'codecc/license': [
        ERROR,
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
      '@typescript-eslint/consistent-type-imports': [
        ERROR,
        {
          prefer: 'type-imports',
          disallowTypeAnnotations: true,
          fixStyle: 'inline-type-imports',
        },
      ],
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
    },
    rules: {
      ...recommendedVue2Config.rules,
      ...tencentEslintLegacyRules,
      '@typescript-eslint/explicit-member-accessibility': OFF,
      'comma-dangle': [ERROR, 'always-multiline'],
      ...deprecateRules,
    },
  },
  {
    ...recommendedVue2Config,
    files: jsVueFiles,
  },
  {
    rules: {
      'vue/html-self-closing': OFF,
      'vue/require-default-prop': OFF,
      'vue/attributes-order': OFF,
    },
  },
  // ...tailwind.configs['flat/recommended'],
  eslintConfigPrettier,
];
