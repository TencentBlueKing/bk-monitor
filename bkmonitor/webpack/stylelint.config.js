/** @type {import('stylelint').Config} */
export default {
  extends: ['stylelint-config-standard-scss', 'stylelint-config-recommended-vue/scss', 'stylelint-config-recess-order'],
  overrides: [
    {
      customSyntax: 'postcss-scss',
      files: ['**/*.scss', '**/*.css'],
    },
    {
      customSyntax: 'postcss-html',
      files: ['**/*.vue'],
      rules: {},
    },
  ],
  plugins: ['stylelint-scss', 'stylelint-order'],
  rules: {
    'at-rule-no-unknown': [
      true,
      {
        ignoreAtRules: ['/.*/'],
      },
    ],
    'at-rule-no-vendor-prefix': true,
    'comment-empty-line-before': ['always', { except: ['first-nested'] }],
    // Sass rules
    'max-nesting-depth': 10,
    // 不要使用已被 autoprefixer 支持的浏览器前缀
    'media-feature-name-no-vendor-prefix': true,
    'order/order': ['declarations', { type: 'at-rule' }, { hasBlock: true, type: 'at-rule' }, 'rules'],
    'property-no-vendor-prefix': true,
    // 去掉多个import、extends、父子声明之间的空行 --开始
    'rule-empty-line-before': [
      'always',
      {
        except: ['first-nested'],
        ignore: ['after-comment'],
      },
    ],
    'scss/at-extend-no-missing-placeholder': true,
    'scss/dollar-variable-pattern': '^_?[a-z]+[\\w-]*$',
    'selector-max-id': 3,
    'selector-no-vendor-prefix': true,
    'value-no-vendor-prefix': true,
  },
};
