/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

/** 将检索 total（BigNumber / ES7 value 对象 / 数字）归一化为有限数字 */
export const normalizeSearchTotal = (total: unknown): number => {
  if (total == null) return 0;
  if (typeof total === 'number') {
    return Number.isFinite(total) ? total : 0;
  }
  const totalLike = total as { toNumber?: () => number; value?: unknown };
  if (typeof totalLike.toNumber === 'function') {
    const value = totalLike.toNumber();
    return Number.isFinite(value) ? value : 0;
  }
  if (typeof total === 'object' && totalLike.value != null) {
    return normalizeSearchTotal(totalLike.value);
  }
  const parsed = Number(total);
  return Number.isFinite(parsed) ? parsed : 0;
};

/** 优先 searchTotal，其次 stream meta 写入的 indexSetQueryResult.total */
export const getEffectiveSearchTotal = (state: {
  searchTotal?: unknown;
  indexSetQueryResult?: { total?: unknown };
}) => {
  const fromSearchTotal = normalizeSearchTotal(state.searchTotal);
  if (fromSearchTotal > 0) return fromSearchTotal;
  return normalizeSearchTotal(state.indexSetQueryResult?.total);
};
