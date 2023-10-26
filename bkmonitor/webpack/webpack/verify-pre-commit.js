const colors = require('picocolors');
// precommit lint
if (!/lint-staged/.test(process.env.npm_execpath || '')) {
  console.log();
  console.error(`  ${colors.bgRed(colors.white(' ERROR '))} ${colors.red('未检测到 lint-staged')}\n
        ${colors.green('请使用 npm i -g lint-staged 安装')}\n
    `);
  process.exit(1);
}
