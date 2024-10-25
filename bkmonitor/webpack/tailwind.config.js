const { transformAppDir } = require('./webpack/utils');
const appName = transformAppDir(process.env.APP);
/** @type {import('tailwindcss').Config} */
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
    spacing: {
      px: '1px',
      0: '0px',
      0.5: '2px',
      1: '4px',
      1.5: '6px',
      2: '8px',
      2.5: '10px',
      3: '12px',
      3.5: '14px',
      4: '16px',
      5: '20px',
      6: '24px',
      7: '28px',
      8: '32px',
      9: '36px',
      10: '40px',
      11: '44px',
      12: '48px',
      14: '56px',
      16: '64px',
      20: '80px',
      24: '96px',
      28: '112px',
      32: '128px',
      36: '144px',
      40: '160px',
      44: '176px',
      48: '192px',
      52: '208px',
      56: '224px',
      60: '240px',
      64: '256px',
      72: '288px',
      80: '320px',
      96: '384px',
    },
  },
  plugins: [],
};
