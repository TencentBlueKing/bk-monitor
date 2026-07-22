/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

/** 去掉路径中的数组下标，便于与 Fields 列表对齐：a.0.b → a.b */
export const normalizeArrayFieldPath = (path: string) => String(path ?? '').replace(/\.\d+(?=\.|$)/g, '');

export type FieldPathLookup = (_fieldName: string) => { field_name?: string } | undefined | null;

/**
 * 将 JSON 深路径收敛为 Fields 列表中真实存在的最长前缀。
 *
 * 例：字段列表含 `__ext_json.deployment.application`、`__ext_json.deployment.pod`
 * - `__ext_json.deployment.application` → `__ext_json.deployment.application`
 * - `__ext_json.deployment.pod.node` → `__ext_json.deployment.pod`（未声明子字段，向上回溯）
 * - `__ext_json` → `__ext_json`（虚拟 object 中间层也可作为字段）
 */
export const resolveMappedFieldPath = (
  path: string,
  resolveField: FieldPathLookup,
  fallback?: string,
): string => {
  const normalized = normalizeArrayFieldPath(path);
  if (!normalized) {
    return fallback ?? '';
  }

  const parts = normalized.split('.').filter(Boolean);
  for (let len = parts.length; len >= 1; len -= 1) {
    const candidate = parts.slice(0, len).join('.');
    const matched = resolveField(candidate);
    if (matched?.field_name) {
      return matched.field_name;
    }
  }

  return fallback ?? normalized;
};

/** 判断路径是否已是 Fields 列表中的字段（含数组下标归一） */
export const isMappedFieldPath = (path: string, resolveField: FieldPathLookup) => {
  const normalized = normalizeArrayFieldPath(path);
  if (!normalized) {
    return false;
  }
  return Boolean(resolveField(normalized)?.field_name || resolveField(path)?.field_name);
};
