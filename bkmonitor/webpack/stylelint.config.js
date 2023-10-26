module.exports = {
  plugins: [
    'stylelint-scss',
    'stylelint-order'
  ],
  extends: [
    'stylelint-config-recommended-vue',
    'stylelint-config-recess-order'
  ],
  rules: {
    // Base rules
    indentation: 2,
    'number-leading-zero': 'never',
    'string-quotes': 'single',
    'selector-max-id': 3,
    'selector-list-comma-newline-after': 'always',
    'comment-empty-line-before': [
      'always',
      { except: ['first-nested'] }
    ],
    'block-opening-brace-space-before': 'always',
    'declaration-colon-space-after': 'always',
    'declaration-colon-space-before': 'never',
    'declaration-block-single-line-max-declarations': 1,
    // Sass rules
    'max-nesting-depth': 10,
    'scss/dollar-variable-pattern': '^_?[a-z]+[\\w-]*$',
    'scss/at-extend-no-missing-placeholder': true,
    'order/order': [
      'declarations',
      { type: 'at-rule' },
      { type: 'at-rule', hasBlock: true },
      'rules'
    ],

    // 不要使用已被 autoprefixer 支持的浏览器前缀
    'media-feature-name-no-vendor-prefix': true,
    'at-rule-no-unknown': [true, {
      ignoreAtRules: ['/.*/']
    }],
    'at-rule-no-vendor-prefix': true,
    'selector-no-vendor-prefix': true,
    'property-no-vendor-prefix': true,
    'value-no-vendor-prefix': true,
    // 颜色值要小写
    'color-hex-case': 'lower',
    // 颜色值能短则短
    'color-hex-length': 'short',
    // 不能用important
    'declaration-no-important': true,
    // 去掉多个import、extends、父子声明之间的空行 --开始
    'rule-empty-line-before': ['always', {
      except: ['first-nested'],
      ignore: ['after-comment']
    }],
    'at-rule-empty-line-before': ['always', {
      except: ['first-nested',  'blockless-after-blockless'],
      ignore: ['after-comment']
    }]
  },
  overrides: [
    {
      files: ['*.scss', '*.css', './**/*.scss'],
      customSyntax: 'postcss-scss'
    },
    {
      files: ['*.vue', './**/*.vue'],
      customSyntax: 'postcss-html'
    }
  ]
};
