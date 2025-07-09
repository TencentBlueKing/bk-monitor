module.exports = {
  purge: ['./src/**/*.html', './src/**/*.tsx', './src/**/*.vue', './src/**/*.js'],
  darkMode: false, // or 'media' or 'class'
  theme: {
    extend: {},
  },
  variants: {
    extend: {},
  },
  plugins: [require('daisyui')],
  daisyui: {
    themes: false, // 或设置为 true 启用默认主题
  },
};
