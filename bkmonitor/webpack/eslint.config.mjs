import jsEslint from '@eslint/js';
import eslintConfigPrettier from 'eslint-config-prettier';
import tencentEslintLegacyRules from 'eslint-config-tencent/ts';
import codecc from 'eslint-plugin-codecc';
import perfectionist from 'eslint-plugin-perfectionist';
import prettier from 'eslint-plugin-prettier';
import eslintVuePlugin from 'eslint-plugin-vue';
import tsEslint from 'typescript-eslint';

const OFF = 0;
const WARNING = 1;
const ERROR = 2;
const jsxOrVueSortGroups = {
  customGroups: [
    {
      groupName: 'DEFINITION',
      elementNamePattern: ['^is$', '^vIs$', '^v-is$'],
    },
    {
      groupName: 'LIST_RENDERING',
      elementNamePattern: ['^v-for$', '^vFor$'],
    },
    {
      groupName: 'CONDITIONALS',
      elementNamePattern: ['^v-if$', '^v-else-if$', '^v-else$', '^vIf$', '^vElseIf$', '^vElse$'],
    },
    {
      groupName: 'RENDER_MODIFIERS',
      elementNamePattern: ['^v-pre$', '^v-once$', '^vPre$', '^vOnce$'],
    },
    {
      groupName: 'GLOBAL',
      elementNamePattern: '^id$',
    },
    {
      groupName: 'UNIQUE',
      elementNamePattern: ['^ref$', '^key$'],
    },
    {
      groupName: 'WIDTH',
      elementNamePattern: '^width$',
    },
    {
      groupName: 'HEIGHT',
      elementNamePattern: '^height$',
    },
    {
      groupName: 'STYLE',
      elementNamePattern: '^style$',
    },
    {
      groupName: 'CLASS',
      elementNamePattern: ['^class$', '^ext-cls$', '^extCls$'],
    },
    {
      groupName: 'TWO_WAY_BINDING',
      elementNamePattern: ['^v-model$', '^vModel$'],
    },
    {
      groupName: 'SLOT',
      elementNamePattern: ['^v-slot$', '^slot$', '^vSlot$'],
    },
    {
      groupName: 'OTHER_DIRECTIVES',
      elementNamePattern: '^v-',
    },
    {
      groupName: 'EVENTS',
      elementNamePattern: ['^on\\w+', '^v-on', '^vOn', '^@\\w+', '^on-'],
    },
    {
      groupName: 'CONTENT',
      elementNamePattern: ['^v-html$', '^v-text$', '^vHtml$', '^vText$'],
    },
  ],
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
export default [
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
      './src/monitor-api/modules/*',
    ],
  },
  {
    plugins: { prettier },
    rules: { ...prettier.configs.recommended.rules },
  },
  ...tsEslint.config(
    jsEslint.configs.recommended,
    tsEslint.configs.recommended,
    ...eslintVuePlugin.configs['flat/vue2-recommended'],
    {
      files: ['*.vue', '**/*.vue'],
      languageOptions: {
        parserOptions: {
          parser: '@typescript-eslint/parser',
        },
      },
      rules: {
        'vue/attributes-order': [
          ERROR,
          {
            order: [
              'DEFINITION',
              'LIST_RENDERING',
              'CONDITIONALS',
              'RENDER_MODIFIERS',
              'GLOBAL',
              'UNIQUE',
              'TWO_WAY_BINDING',
              'SLOT',
              'OTHER_DIRECTIVES',
              'OTHER_ATTR',
              'EVENTS',
              'CONTENT',
            ],
            alphabetical: false,
          },
        ],
      },
    }
  ),
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
      'perfectionist/sort-heritage-clauses': [
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
            ['side-effect-style', 'style'],
          ],
          customGroups: [
            {
              groupName: 'top',
              elementNamePattern: ['./public-path', './public-path.ts', 'monitor-common/polyfill'],
            },
            {
              groupName: 'vueI18n',
              elementNamePattern: ['./i18n/i18n', '^vue$'],
            },
            {
              groupName: 'magicBox',
              elementNamePattern: [
                './common/import-magicbox-ui',
                'monitor-ui/directive/index',
                'monitor-static/svg-icons',
              ],
            },
            {
              groupName: 'tsxSupport',
              elementNamePattern: ['vue-property-decorator', 'vue-tsx-support'],
            },
          ],
          fallbackSort: {
            type: 'natural',
            order: 'asc',
          },
          newlinesBetween: 'always',
          internalPattern: ['^@/', '^@router/', '^@store/', '^@page/', '^@static/'],
          sortSideEffects: true,
        },
      ],
      'perfectionist/sort-interfaces': [
        ERROR,
        {
          order: 'asc',
          type: 'natural',
          groups: ['unknown', 'method', 'multiline-member'],
        },
      ],
      'perfectionist/sort-intersection-types': [
        ERROR,
        {
          type: 'natural',
          order: 'asc',
        },
      ],
      'perfectionist/sort-named-exports': [
        ERROR,
        {
          type: 'natural',
          order: 'asc',
        },
      ],
      'perfectionist/sort-modules': [
        ERROR,
        {
          type: 'natural',
          order: 'asc',
          groups: [
            'declare-enum',
            'export-enum',
            'enum',
            ['declare-interface', 'declare-type'],
            ['export-interface', 'export-type'],
            ['interface', 'type'],
            'declare-class',
            'class',
            'export-class',
            'declare-function',
            'export-function',
            'function',
          ],
        },
      ],
      'perfectionist/sort-named-imports': [
        ERROR,
        {
          type: 'natural',
          order: 'asc',
          groups: ['type-import', 'value-import', 'unknown'],
        },
      ],
      'perfectionist/sort-object-types': [
        ERROR,
        {
          type: 'natural',
          order: 'asc',
        },
      ],
      'perfectionist/sort-union-types': [
        ERROR,
        {
          type: 'natural',
          order: 'asc',
        },
      ],
      'perfectionist/sort-variable-declarations': [
        ERROR,
        {
          type: 'natural',
          order: 'asc',
        },
      ],
      'perfectionist/sort-switch-case': OFF,
      'perfectionist/sort-sets': OFF,
      // 'perfectionist/sort-vue-attributes': [
      //   ERROR,
      //   {
      //     ...jsxOrVueSortGroups,
      //     type: 'natural',
      //     order: 'asc',
      //   },
      // ],
    },
  },
  {
    files: ['src/**/*.ts', 'src/**/*.tsx', './**/*.js', 'src/**/*.js'],
    ignores: [],
    languageOptions: {
      parser: tsEslint.parser,
      parserOptions: {
        ecmaFeatures: { jsx: true, legacyDecorators: true },
        ecmaVersion: 'latest',
        project: true,
      },
    },
    plugins: {
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
      ...tencentEslintLegacyRules.rules,
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
  {
    files: ['./*.js', 'public/**/*.js', 'webpack/*.js'],
    rules: {
      '@typescript-eslint/no-require-imports': OFF,
      'codecc/license': OFF,
    },
  },
  eslintConfigPrettier,
  {
    files: ['src/trace/**/*.tsx', 'src/trace/**/*.ts'],
    plugins: {
      'monitor-vue3': {
        rules: {
          'no-ref': {
            meta: {
              type: 'suggestion',
              fixable: null,
              messages: {
                // vueuse 推荐
                'no-ref': `建议使用 shallowRef 替代 ref 或者
1、使用 import { ref as deepRef } from 'vue'; deepRef 来替换 ref 的名称;
2、使用 import { createRef } from '@vueuse/core'; createRef(initialData, true); 来替换 ref 的名称;`,
              },
              hasSuggestions: true,
            },
            create(context) {
              return {
                CallExpression(node) {
                  if (node.callee.type === 'Identifier' && node.callee.name === 'ref') {
                    context.report({
                      node,
                      messageId: 'no-ref',
                    });
                  }
                },
              };
            },
          },
        },
      },
    },
    rules: {
      'monitor-vue3/no-ref': WARNING,
    },
  },
  {
    rules: {
      'no-undef': OFF,
      'no-case-declarations': OFF, // biome lint/style/noCaseDeclarations
      'vue/require-default-prop': OFF,
      '@typescript-eslint/no-explicit-any': OFF, // biome lint/suspicious/noExplicitAny
      '@typescript-eslint/ban-ts-comment': [
        WARNING,
        {
          minimumDescriptionLength: 0,
          'ts-check': false,
          'ts-expect-error': false,
          'ts-ignore': false,
          'ts-nocheck': false,
        },
      ],
      '@typescript-eslint/no-unused-vars': OFF, // biome lint/style/noUnusedVars
      'vue/html-self-closing': [
        ERROR,
        {
          html: {
            void: 'always',
            normal: 'always',
            component: 'always',
          },
          svg: 'always',
          math: 'always',
        },
      ],
      '@typescript-eslint/no-unused-expressions': OFF, // biome lint/style/noUnusedExpressions
    },
  },
];
