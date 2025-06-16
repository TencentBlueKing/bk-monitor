export default class StaticUtil {
  static getRegExp(reg: string | RegExp | number | boolean, defaultFlags = ''): RegExp {
    // 如果已经是 RegExp 对象，直接返回
    if (reg instanceof RegExp) return reg;

    const regString = String(reg).trim();

    // 判定是否为标准正则表达式字符串 /pattern/flags
    if (regString.startsWith('/') && regString.lastIndexOf('/') > 0) {
      const lastSlashIndex = regString.lastIndexOf('/');
      const pattern = regString.slice(1, lastSlashIndex); // 提取正则表达式的主体部分
      let flags = regString.slice(lastSlashIndex + 1); // 提取正则表达式的 flags（可能为空）
      flags = Array.from(new Set(...flags.split(''), ...(defaultFlags ?? '').split(''))).join('');

      // 如果 flags 中包含非法字符，直接将整个字符串作为普通字符串处理
      if (!/^[gimsuy]*$/.test(flags)) {
        return new RegExp(regString.replace(/([.*+?^${}()|[\]\\])/g, '\\$1'), defaultFlags); // 转义特殊字符
      }

      try {
        return new RegExp(pattern, flags); // 创建 RegExp 对象
      } catch (error) {
        console.error(`Invalid regular expression: ${regString}`, error);
        throw error; // 如果正则表达式无效，抛出错误
      }
    }

    // 如果不是标准正则表达式字符串，将字符串作为整体处理
    try {
      return new RegExp(regString.replace(/([.*+?^${}()|[\]\\])/g, '\\$1'), defaultFlags); // 转义特殊字符
    } catch (error) {
      console.error(`Invalid regular expression: ${regString}`, error);
      throw error; // 如果正则表达式无效，抛出错误
    }
  }
}
