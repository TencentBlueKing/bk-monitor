/** @type {import('postcss-load-config').Config} */
module.exports = {
  plugins: [
    require('tailwindcss'),
    require('tailwindcss/nesting'),
    require('postcss-preset-env')({
      stage: 3,
      features: {
        'nesting-rules': false,
      },
    }),
  ],
};
