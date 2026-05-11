/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions
 * of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { IMPACT_SCOPE_ID_FIELD_MAP } from '../constant';

import type { ImpactScope } from '../typing';
import type { IWhereItem } from 'trace/components/retrieval-filter/typing';

type TImpactScope = ImpactScope | Record<string, never>;

const IMPACT_SCOPE_KEY_PREFIX = 'impact_scope.';

/**
 * 将 conditions 中 key 为 impact_scope.xxx 的条件替换为实例的 alert_query_fields 展开结果
 *
 * @example
 * // 输入: [{ key: 'impact_scope.host', value: ['1234'], method: 'eq' }, ...]
 * // 输出: [{ key: 'event.bk_host_id', value: ['5678'], method: 'eq', condition: 'or' }, ...]
 */
export const conditionAlertQueryFieldReplace = (conditions: IWhereItem[], impactScope: TImpactScope): IWhereItem[] => {
  const result: IWhereItem[] = [];

  for (const c of conditions) {
    if (!c.key?.startsWith(IMPACT_SCOPE_KEY_PREFIX)) {
      result.push(c);
      continue;
    }

    const dimensionKey = c.key.slice(IMPACT_SCOPE_KEY_PREFIX.length);
    const idField = IMPACT_SCOPE_ID_FIELD_MAP[dimensionKey];
    const resource = impactScope[dimensionKey];

    if (!idField || !resource || !('instance_list' in resource) || !Array.isArray((resource as any).instance_list)) {
      result.push(c);
      continue;
    }

    const instanceList: Array<{
      [key: string]: unknown;
      alert_query_fields?: Array<{ condition: string; keys: string[]; value: string }>;
    }> = (resource as any).instance_list;

    // value 为空 → 保留原条件，不做替换
    const isAllInstances = !c.value?.length;
    if (isAllInstances) {
      result.push(c);
      continue;
    }

    // value 有值 → 查询单个指定实例
    const targetValue = String(c.value[0] ?? '');
    const targetInstance = instanceList.find(inst => String(inst[idField]) === targetValue);

    if (!targetInstance?.alert_query_fields?.length) {
      result.push(c);
      continue;
    }

    // 展开每个 alert_query_field group，同组内各 key 生成独立 condition
    const expanded = transformSingleInstanceFields(targetInstance.alert_query_fields, c.method);
    result.push(...expanded);
  }

  return mergeConditionsByUniqueKey(result);
};

/**
 * 对 result 中 key/condition/method 相同的 condition 进行合并，value 去重
 *
 * @example
 * 输入: [
 *   { key: 'event.bk_host_id', value: ['1234'], method: 'eq', condition: 'or' },
 *   { key: 'event.bk_host_id', value: ['5678'], method: 'eq', condition: 'or' },
 * ]
 * → [{ key: 'event.bk_host_id', value: ['1234', '5678'], method: 'eq', condition: 'or' }]
 */
function mergeConditionsByUniqueKey(result: IWhereItem[]): IWhereItem[] {
  const merged = new Map<string, { item: IWhereItem; value: Set<string> }>();

  for (const c of result) {
    // 仅 condition 为 or 的记录才参与合并，其他直接保留
    if (c.condition !== 'or') continue;

    // 用 key + method + condition 作为唯一标识
    const uniqueKey = `${c.key ?? ''}|${c.method ?? 'eq'}|${c.condition ?? 'or'}`;
    const existing = merged.get(uniqueKey);

    if (!existing) {
      merged.set(uniqueKey, { value: new Set(c.value?.map(v => String(v)) || []), item: c });
    } else {
      for (const v of c.value ?? []) {
        existing.value.add(String(v));
      }
    }
  }

  // 未合并的记录（condition 非 or）追加到结果末尾
  const unmerged = result.filter(c => c.condition !== 'or');
  return [
    ...Array.from(merged.values()).map(({ value, item }) => ({
      ...item,
      value: [...value],
    })),
    ...unmerged,
  ];
}

/**
 * 将单个实例的 alert_query_fields 转换为 IWhereItem[]
 * 每个 key 生成一条独立 condition，value 保持原值，method 默认 eq，condition 来自原字段组
 */
function transformSingleInstanceFields(
  fields?: Array<{ condition: string; keys: string[]; value: string }>,
  method?: string
): IWhereItem[] {
  if (!fields?.length) return [];

  return fields.flatMap(group =>
    group.keys.map(key => ({
      key,
      value: [group.value],
      method: method || 'eq',
      condition: group.condition as IWhereItem['condition'],
    }))
  );
}
