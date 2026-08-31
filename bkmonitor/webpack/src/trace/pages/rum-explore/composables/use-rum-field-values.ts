import type { Ref } from 'vue';

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { NULL_VALUE_ID, NULL_VALUE_NAME } from '../../../components/retrieval-filter/utils';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useRumExploreStore } from '../../../store/modules/rum-explore';
import { getFieldsOptionValues } from '../services/rum-search';

import type { IGetValueFnParams, IWhereValueOptionsItem } from '../../../components/retrieval-filter/typing';
import type { IRumField } from '../typings';

const BOOLEAN_OPTIONS = [
  { id: 'true', name: 'true' },
  { id: 'false', name: 'false' },
];

/**
 * 检索条件区的候选值获取。
 *
 * 同一时刻只缓存一个字段的候选项：接口返回条数小于 limit 说明已经取全，
 * 之后用户继续输入就在前端过滤，避免每敲一个字符都打一次接口。
 */
export function useRumFieldValues(fields: Ref<IRumField[]>) {
  const store = useRumExploreStore();

  let cache: null | { key: string; values: Array<{ id: string; name: string }> } = null;
  let abortController = new AbortController();

  function getCacheKey(field: string) {
    return `${store.appName}__${store.mode}__${field}`;
  }

  function withNullOption(list: Array<{ id: string; name: string }>, isKeyword: boolean) {
    return isKeyword ? [{ id: NULL_VALUE_ID, name: NULL_VALUE_NAME }, ...list] : list;
  }

  async function getFieldValues(params: IGetValueFnParams): Promise<IWhereValueOptionsItem> {
    const field = params?.fields?.[0] || '';
    const viewConfigFieldInfo = fields.value.find(item => item.name === field);
    const fieldType = viewConfigFieldInfo?.type || '';
    const isKeyword = fieldType === 'keyword';
    const search = String(params?.where?.[0]?.value?.[0] ?? '').toLocaleLowerCase();

    if (fieldType === 'boolean') {
      const list = BOOLEAN_OPTIONS.filter(item => item.name.includes(search));
      return { count: list.length, list };
    }

    // 聚焦或重新查询时（isInit__）丢弃缓存，保证拿到与当前查询条件匹配的候选项
    if (params?.isInit__) {
      cache = null;
    }

    const cacheKey = getCacheKey(field);
    if (cache?.key === cacheKey && !params?.queryString) {
      const list = search
        ? cache.values.filter(
            item => `${item.id}`.toLocaleLowerCase().includes(search) || item.name.toLocaleLowerCase().includes(search)
          )
        : cache.values.slice(0, params?.limit || 200);
      return { count: list.length, list: withNullOption(list, isKeyword) };
    }

    abortController.abort();
    abortController = new AbortController();

    const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
    const limit = params?.limit || 200;
    // view_config 已声明该字段的枚举值时直接取用，无需再打接口（如 span_type 等固定取值字段）
    const optionValues = viewConfigFieldInfo?.option_values || [];
    let res = {};
    if (!optionValues.length) {
      res = await getFieldsOptionValues(
        {
          app_name: store.appName,
          mode: store.mode,
          start_time: startTime,
          end_time: endTime,
          fields: [field],
          limit,
          query_string: params?.queryString || '',
          filters: (params?.where || []).map(item => ({
            key: item.key,
            operator: 'like',
            value: item.value || [],
          })),
        },
        { signal: abortController.signal }
      );
    }
    // 枚举值用 alias 展示、value 作为实际取值；接口返回的只有纯值，id 与 name 相同
    const values = optionValues.length
      ? optionValues.map(item => ({
          id: `${item.value}`,
          name: `${item.alias}`,
        }))
      : (res?.[field] || []).filter(Boolean).map(value => ({ id: `${value}`, name: `${value}` }));
    cache = !search && values.length < limit ? { key: cacheKey, values } : null;

    return { count: values.length, list: withNullOption(values, isKeyword) };
  }

  return { getFieldValues };
}
