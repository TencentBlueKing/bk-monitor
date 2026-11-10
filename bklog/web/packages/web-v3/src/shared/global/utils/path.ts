// 实现 path.join 功能, 组合为一个合法路径, 并且去掉重复的 /
// 例如： a/, /b/ -> a/b

/**
 * 组合多个路径片段为一个合法路径，去掉重复的斜杠
 * @param paths 路径片段数组
 * @returns 组合后的路径
 */
export function join(...paths: string[]): string {
  if (paths.length === 0) {
    return '';
  }

  return paths.reduce((acc, path) => {
    if (acc.length > 0) {
      return `${acc.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`;
    }

    return path;
  }, '');
}
