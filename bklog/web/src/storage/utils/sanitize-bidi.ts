/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

/**
 * Bidi 控制字符单次扫描清洗（与 common/util.js 中逻辑保持一致，供 WebWorker 复用）
 */
export function sanitizeBidi(str: string) {
  if (!str) return str;
  let result: string | null = null;
  let lastIndex = 0;
  const len = str.length;
  for (let i = 0; i < len; i++) {
    const code = str.charCodeAt(i);
    if ((code >= 0x202A && code <= 0x202E) || (code >= 0x2066 && code <= 0x2069)) {
      if (result === null) result = '';
      result += str.slice(lastIndex, i);
      lastIndex = i + 1;
    }
  }
  return result === null ? str : result + str.slice(lastIndex);
}
