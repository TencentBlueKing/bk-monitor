/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

import { isBigNumberValue, normalizeBigNumberForStorage } from './normalize-storage-value';

const bigNumberToCloneable = (value: any): any => {
  if (isBigNumberValue(value)) {
    return normalizeBigNumberForStorage(value);
  }
  return value;
};

/** 将搜索 meta 转为可结构化克隆的纯对象，用于 Worker postMessage */
export const cloneSearchMeta = (value: any): any => {
  const normalized = bigNumberToCloneable(value);
  if (normalized !== value) return normalized;
  if (Array.isArray(value)) return value.map(item => cloneSearchMeta(item));
  if (value && Object.prototype.toString.call(value) === '[object Object]') {
    return Object.keys(value).reduce((output, key) => {
      output[key] = cloneSearchMeta(value[key]);
      return output;
    }, {} as Record<string, any>);
  }
  return value;
};
