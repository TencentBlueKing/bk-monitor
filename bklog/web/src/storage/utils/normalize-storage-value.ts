/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

const isPlainObject = (value: unknown) => Object.prototype.toString.call(value) === '[object Object]';

export const isBigNumberValue = (value: any) => !!value?._isBigNumber && typeof value.toString === 'function';

/**
 * Convert json-bignumber values to IndexedDB-safe primitives.
 *
 * Values within the frontend safe integer range are stored as number; values beyond
 * Number.MAX_SAFE_INTEGER / Number.MIN_SAFE_INTEGER are stored as string to avoid
 * precision loss and BigNumber object persistence.
 */
export const normalizeBigNumberForStorage = (value: any): number | string => {
  const stringValue = value.toString();
  const numberValue = Number(stringValue);

  if (!Number.isFinite(numberValue)) {
    return stringValue;
  }

  const isWithinSafeRange = typeof value.isLessThanOrEqualTo === 'function'
    && typeof value.isGreaterThanOrEqualTo === 'function'
    ? value.isLessThanOrEqualTo(Number.MAX_SAFE_INTEGER) && value.isGreaterThanOrEqualTo(Number.MIN_SAFE_INTEGER)
    : Math.abs(numberValue) <= Number.MAX_SAFE_INTEGER;
  const canBeRepresentedAsNumber = typeof value.isEqualTo === 'function'
    ? value.isEqualTo(numberValue)
    : String(numberValue) === stringValue;

  return isWithinSafeRange && canBeRepresentedAsNumber ? numberValue : stringValue;
};

/** Recursively normalize BigNumber fields before data is written to IndexedDB. */
export const normalizeStorageValue = <T = any>(value: T): T => {
  if (isBigNumberValue(value)) {
    return normalizeBigNumberForStorage(value) as T;
  }

  if (Array.isArray(value)) {
    let changed = false;
    const output = value.map((item) => {
      const normalizedItem = normalizeStorageValue(item);
      changed = changed || normalizedItem !== item;
      return normalizedItem;
    });
    return (changed ? output : value) as T;
  }

  if (!isPlainObject(value)) {
    return value;
  }

  const source = value as Record<string, any>;
  let changed = false;
  const output = Object.keys(source).reduce(
    (result, key) => {
      const normalizedValue = normalizeStorageValue(source[key]);
      result[key] = normalizedValue;
      changed = changed || normalizedValue !== source[key];
      return result;
    },
    {} as Record<string, any>,
  );

  return (changed ? output : value) as T;
};
