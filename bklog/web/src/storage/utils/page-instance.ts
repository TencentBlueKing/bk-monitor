/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

const createUniqueId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return [Date.now(), Math.random().toString(16)
    .slice(2)].join(':');
};

// Kept in memory: duplicated tabs can inherit sessionStorage.
export const PAGE_INSTANCE_ID = createUniqueId();

export const createRequestId = (prefix: string) => [prefix, createUniqueId()].join(':');
