module.exports = api => {
  api?.cache.never();
  const presets = [
    [
      '@babel/preset-env',
      {
        targets: {
          browsers:
            process.env.APP === 'mobile'
              ? ['>0.03%', 'last 2 versions', 'IE > 9']
              : ['> 0.3%', 'Chrome > 90', 'last 2 versions', 'Firefox ESR', 'not dead'],
          node: 'current',
        },
        useBuiltIns: 'usage',
        corejs: 3,
        debug: false,
      },
    ],
    process.env.APP !== 'trace'
      ? [
          '@vue/babel-preset-jsx',
          {
            compositionAPI: 'native',
            functional: true,
            injectH: true,
            vModel: true,
            vOn: true,
          },
        ]
      : undefined,
  ].filter(Boolean);
  const plugins = [
    '@babel/plugin-transform-runtime',
    process.env.APP === 'mobile'
      ? [
          'import',
          {
            libraryName: 'vant',
            libraryDirectory: 'es',
            style: true,
          },
          'vant',
        ]
      : undefined,
    process.env.APP === 'trace' ? '@vue/babel-plugin-jsx' : undefined,
  ].filter(Boolean);
  return {
    presets,
    plugins,
  };
};
