/** @type {import('postcss-load-config').Config} */
module.exports = {
  plugins: {
    'tailwindcss/nesting': {}, // 可选，如果需要嵌套支持
    tailwindcss: {},
    autoprefixer: {
      ignoreUnknownProperties: true,
    },
  },
};
