/** @type {import('tailwindcss').Config} */
const { transformAppDir } = require('./webpack/utils');
const appName = transformAppDir(process.env.APP);
console.info(appName, '========');
module.exports = {
  content: [
    `./src/${appName}/pages/**/*.{tsx, vue}`,
    `./src/${appName}/components/**/*.{tsx, vue}`,
    ...(!['trace'].includes(process.env.APP)
      ? ['./src/monitor-ui/chart-plugins/**/*.tsx', './src/monitor-ui/monitor-echarts/**/*.tsx']
      : [`./src/${appName}/plugins/**/*.tsx`]),
  ],
  theme: {
    extend: {
      boxShadow: {
        homeOverviewItem: '0px 1px 8px 0px #f0f1f5',
      },
      fontSize: {
        16: '16px',
      },
      colors: {
        primary: '#3A84FF',
        error: '#EA3636',
        warning: '#FF9C01',
        health: '#2DCB56',
        baseColor: '#63656E',
        baseBorderColor: '#DCDEE5',
        313238: '#313238',
        '979BA5': '#979BA5',
        C4C6CC: '#C4C6CC',
        EAEBF0: '#EAEBF0',
        F0F1F5: '#F0F1F5',
      },
    },
  },
  plugins: [],
};
