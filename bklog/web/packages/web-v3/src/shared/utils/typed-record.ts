/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
/** Preserve an existing lookup table's exact known entries and value union,
 * while allowing the dynamic string keys used by route/backend field names.
 * This is an identity operation: keys, values and object identity stay unchanged. */
export function asDictionary<T extends object>(value: T): T & Record<string, T[keyof T]> {
  return value as T & Record<string, T[keyof T]>;
}

/** Membership is meaningful for an unknown candidate; unlike assignment it
 * does not require that candidate to already belong to the array's value type.
 * Keep Array.includes' exact SameValueZero behavior (including NaN). */
export function includesValue<T>(values: readonly T[], candidate: unknown): boolean {
  return values.includes(candidate as T);
}
