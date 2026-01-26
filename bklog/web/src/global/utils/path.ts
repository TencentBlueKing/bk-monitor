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

  // 过滤掉空字符串
  const validPaths = paths.filter(path => path.length > 0);

  if (validPaths.length === 0) {
    return '';
  }

  // 组合所有路径，用单个斜杠连接
  const combined = validPaths.join('/');

  // 去掉重复的斜杠，但保留开头的斜杠（如果第一个路径以 / 开头）
  const normalized = combined.replace(/\/+/g, '/');

  // 如果原始第一个路径以 / 开头，确保结果也以 / 开头
  const startsWithSlash = validPaths[0].startsWith('/');
  const result = startsWithSlash && !normalized.startsWith('/')
    ? `/${normalized}`
    : normalized;

  return result;
}
