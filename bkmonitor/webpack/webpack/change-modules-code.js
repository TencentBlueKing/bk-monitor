const { constants } = require('node:fs');
const { readFile, access, writeFile } = require('node:fs/promises');
const { resolve } = require('node:path');

// biome-ignore lint/complexity/noStaticOnlyClass: <explanation>
class ChangeCode {
  /**
   * @description: 修改echarts
   * @param {*}
   * @return {*}
   */
  static async changeEchartsCode() {
    const codeUrl = resolve(process.cwd(), 'src/monitor-ui/node_modules/echarts/lib/layout/barGrid.js');
    const exists = await access(codeUrl, constants.R_OK | constants.W_OK)
      .then(() => true)
      .catch(() => false);
    if (!exists) return;
    let chunk = await readFile(codeUrl, 'utf-8');
    chunk = chunk
      .replace(
        'height = (height <= 0 ? -1 : 1) * barMinHeight;',
        'height = height ? (height < 0 ? -1 : 1) * barMinHeight : -1 * barMinHeight;'
      )
      .replace(
        'width = (width < 0 ? -1 : 1) * barMinHeight;',
        'width = width ? (width < 0 ? -1 : 1) * barMinHeight : -1 * barMinHeight;'
      );
    await writeFile(codeUrl, chunk, 'utf-8').catch(e => {
      console.error(e.message || 'change echarts code error');
      process.exit(0);
    });
  }
}
ChangeCode.changeEchartsCode();
