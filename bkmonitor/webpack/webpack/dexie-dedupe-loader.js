/**
 * monitor-apm-log / monitor-trace-log 各自内置了不同 patch 的 Dexie。
 * Dexie 用 globalThis[Symbol.for("Dexie")] 做单例，版本不一致会直接 throw。
 * 去掉 throw 后沿用其复用逻辑：后加载的 SDK 使用先注册的那份 Dexie 类。
 */
const DEXIE_VERSION_THROW_RE =
  /if \(dexie_min\.semVer !== Dexie\.semVer\) \{\s*throw new Error\(`Two different versions of Dexie loaded in the same app: \$\{dexie_min\.semVer\} and \$\{Dexie\.semVer\}`\);\s*\}/g;

module.exports = function dexieDedupeLoader(source) {
  this.cacheable?.();
  const code = typeof source === 'string' ? source : source.toString();
  return code.replace(DEXIE_VERSION_THROW_RE, '');
};
