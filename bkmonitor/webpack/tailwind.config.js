/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/monitor-pc/pages/home/**.tsx'],
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
