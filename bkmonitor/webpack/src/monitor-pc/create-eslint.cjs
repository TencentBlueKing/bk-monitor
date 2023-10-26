/* eslint-disable codecc/comment-ratio */
const tsParser = require('@typescript-eslint/parser');
const vueRules = require('./vue-rules.cjs');
/**
 *
 * @param {string} tsconfigDir tsconfig.json的路径
 * @returns eslint配置
 */
function createEslint(tsconfigDir) {
  return  {
    root: true,
    env: {
      browser: true,
      es6: true,
      node: true
    },
    extends: [
      'eslint-config-tencent',
      'plugin:vue/recommended'
    ],
    globals: {
      NODE_ENV: true,
      SITE_URL: true,
      __webpack_public_path__: true
    },
    plugins: ['vue', 'codecc', 'simple-import-sort', 'prettier'],
    rules: {
      '@typescript-eslint/no-unused-vars': ['error'],
      '@typescript-eslint/explicit-member-accessibility': 'off',
      'comma-dangle': ['error', 'never'],
      'codecc/comment-ratio': ['error', 10],
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
          pattern: '.*Tencent is pleased to support the open source community.+'
        }
      ],
      '@typescript-eslint/member-ordering': 'off',
      'simple-import-sort/imports': [
        'error',
        {
          groups: [
            [
              '^(assert|buffer|child_process|cluster|console|constants|crypto|dgram|dns|domain|events|fs|http|https|module|net|os|path|punycode|querystring|readline|repl|stream|string_decoder|sys|timers|tls|tty|url|util|vm|zlib|freelist|v8|process|async_hooks|http2|perf_hooks)(/.*|$)'
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
            ['^.+\\.s?css$']
          ]
        }
      ],
      'simple-import-sort/exports': 'error',
      'import/first': 'error',
      'import/newline-after-import': 'error',
      'import/no-duplicates': 'error',
      'arrow-body-style': 'off',
      'prefer-arrow-callback': 'off'
    },
    overrides: [
      {
        files: ['*.vue'],
        extends: ['eslint-config-tencent/ts'],
        parser: 'vue-eslint-parser',
        rules: {
          ...vueRules
        },
        parserOptions: {
          parser: tsParser,
          ecmaVersion: 2018,
          tsconfigRootDir: tsconfigDir,
          sourceType: 'module',
          project: './tsconfig.eslint.json',
          extraFileExtensions: ['.vue'],
          ecmaFeatures: {
            globalReturn: false,
            impliedStrict: false,
            jsx: true
          }
        }
      },
      {
        files: ['*.ts', '*.tsx'],
        extends: ['eslint-config-tencent/ts', 'plugin:prettier/recommended'],
        rules: {
          indent: 'off',
          '@typescript-eslint/indent': 'off',
          'prettier/prettier': 'error',
          '@typescript-eslint/no-misused-promises': [
            'error',
            {
              checksVoidReturn: false,
              checksVoidReturn: false,
              checksSpreads: false
            }
          ]
        },
        parser: '@typescript-eslint/parser',
        parserOptions: {
          ecmaVersion: 2018,
          tsconfigRootDir: tsconfigDir,
          sourceType: 'module',
          project: './tsconfig.eslint.json'
        }
      },
      {
        files: ['*.js'],
        parser: '@typescript-eslint/parser',
        extends: ['plugin:prettier/recommended'],
        parserOptions: {
          tsconfigRootDir: tsconfigDir,
          project: './tsconfig.eslint.json'
        },
        rules: {
          '@typescript-eslint/no-misused-promises': [
            'error',
            {
              checksVoidReturn: false,
              checksVoidReturn: false,
              checksSpreads: false
            }
          ],
          'max-len': [
            'error',
            {
              code: 120,
              ignoreStrings: true,
              ignoreUrls: true,
              ignoreRegExpLiterals: true,
              ignoreTemplateLiterals: true
            }
          ],
          'prettier/prettier': 'error'
        }
      }
    ]
  };
}
module.exports = {
  createEslint
};
