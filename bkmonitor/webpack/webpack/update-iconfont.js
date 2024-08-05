/**
 * 自动更新iconfont文件
 * 1、将下载的iconfont字体文件放到./webpack/src/monitor-static/icons/iconfont下 文件名都为
 * iconfont.* 目前只需要 'css', 'ttf', 'woff', 'woff2' 四种格式文件
 * 2、执行npm run iconfont
 */
const fs = require('node:fs');
const path = require('node:path');
const updateFont = () => {
  try {
    const sourcePreFix = 'src/monitor-static/icons';
    // const reg = new RegExp('^@font-face[\\s\\S]*\\.icon-monitor[\\s\\S]*?\\}')
    // 拷贝文件
    const fileMap = ['css', 'ttf', 'woff', 'woff2'];
    fileMap.forEach(item => {
      const sourceFile = path.resolve(`${sourcePreFix}/iconfont/iconfont.${item}`);
      const targetFile = path.resolve(`${sourcePreFix}/monitor-icons.${item}`);
      fs.renameSync(sourceFile, targetFile);
      console.log('文件拷贝成功：', `${sourceFile} => ${targetFile}`);
    });
    // 替换文件
    const targetCssFile = path.resolve(`${sourcePreFix}/monitor-icons.css`);
    let targetCss = fs.readFileSync(targetCssFile, 'utf-8');
    targetCss = targetCss.replace(/iconfont\./g, 'monitor-icons.');
    fs.writeFile(targetCssFile, targetCss, 'utf8', err => {
      if (err) {
        console.log(err);
      } else {
        console.log('success!');
      }
    });
  } catch (err) {
    console.log('读写文件发生错误', err);
  }
};
updateFont();
