/**
 * Webpack loader：把包在 JSX 块注释里的 `// #if` 指令展开成独立行，供后续 ifdef-loader 解析。
 * 逻辑与 scripts/monitor-alarm-center/build.ts 中 ifdefPlugin 使用的正则一致。
 */
// 标准 CommonJS 导出：供 webpack.config.js 的 path.resolve 引用本文件路径
module.exports = function jsxIfdefNormalizeLoader(source) {
  // source：当前模块的原始字符串内容（TS/TSX 源码）
  // 声明本 loader 对同一模块输入可缓存，便于 webpack 在增量构建时跳过重复执行
  this.cacheable?.();
  // 源码不含 `#if` 则无需正则，避免对超大文件做无意义扫描
  if (!source.includes('#if')) return source;
  // 将「花括号 + 块注释包裹的 // #if 行」整块替换为「仅保留块注释内的 // #if 那一行」；$1 为捕获组（裸露指令行）。
  // 正则从左到右：匹配左花括号与 /*；可选空白；捕获组为 // 与 #if|elif|else|endif 及该行剩余；非贪婪到换行前；空白、*/、右花括号；g 为全局替换。
  // 返回值交给管道中下一条 loader（ifdef-loader）继续处理。
  return source.replace(/\{\/\*\s*(\/\/\s*#(?:if|elif|else|endif)[^\n]*?)\s*\*\/\}/g, '$1');
};
