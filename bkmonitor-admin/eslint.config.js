import js from '@eslint/js';
import query from '@tanstack/eslint-plugin-query';
import prettier from 'eslint-config-prettier';
import globals from 'globals';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: [
      'dist',
      'node_modules',
      'coverage',
      'playwright-report',
      'test-results',
      'pnpm-lock.yaml',
      '*.config.js',
      '*.config.ts',
      'eslint.config.js',
      'tailwind.config.ts'
    ]
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  react.configs.flat.recommended,
  react.configs.flat['jsx-runtime'],
  jsxA11y.flatConfigs.recommended,
  ...query.configs['flat/recommended'],
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname
      },
      globals: {
        ...globals.browser,
        ...globals.es2022
      }
    },
    settings: {
      react: {
        version: 'detect'
      }
    },
    plugins: {
      'react-hooks': reactHooks
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'inline-type-imports' }
      ],
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': [
        'error',
        { checksVoidReturn: { attributes: false } }
      ],
      'react/prop-types': 'off',
      'react/jsx-no-leaked-render': ['error', { validStrategies: ['ternary'] }],
      'react/no-unstable-nested-components': 'off'
    }
  },
  {
    files: ['src/shared/components/ui/**/*.tsx'],
    rules: {
      'jsx-a11y/heading-has-content': 'off',
      'jsx-a11y/label-has-associated-control': 'off'
    }
  },
  prettier
);
