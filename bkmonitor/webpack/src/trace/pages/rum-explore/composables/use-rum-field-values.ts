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
import { type Ref, shallowRef, watch } from 'vue';

import { byteConvert } from 'monitor-common/utils';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useRumExploreStore } from '../../../store/modules/rum-explore';
import { getFieldsOptionValues } from '../services/rum-search';

import type { IGetValueFnParams, IWhereValueOptionsItem } from '../../../components/retrieval-filter/typing';
import type { IRumField } from '../typings';

const BOOLEAN_OPTIONS = [
  { id: 'true', name: 'true' },
  { id: 'false', name: 'false' },
];

/** 非负数字（byteConvert 仅支持非负字节数，负数会算出 NaN） */
const NON_NEGATIVE_NUMBER_REG = /^\d+(\.\d+)?$/;

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

  /**
   * 字段名 -> { unit, values } 的索引表，供已选条件 tag 的展示格式化使用。
   *
   * 数据全部来自 view_config 的字段元信息（field_unit / option_values），
   * 只在字段列表变化时重建；格式化函数是同步读取，因此用 shallowRef 即可。
   */
  const fieldOptionsMap = shallowRef<
    Map<
      string,
      {
        unit: string;
        values: Array<{ id: string; name: string }>;
      }
    >
  >(new Map());

  /** 登记单个字段的单位与枚举别名（key 为字段名） */
  function setFieldOptionsMap(key: string, unit: string, values: Array<{ id: string; name: string }>) {
    fieldOptionsMap.value.set(key, { unit, values });
  }

  function getCacheKey(field: string) {
    return `${store.appName}__${store.mode}__${field}`;
  }

  function withNullOption(list: Array<{ id: string; name: string }>, _isKeyword: boolean) {
    // return isKeyword ? [{ id: NULL_VALUE_ID, name: NULL_VALUE_NAME }, ...list] : list;
    // 暂时不需要空选项
    return list;
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

  // 字段列表随应用 / 模式 / span 类型变化，需同步刷新索引表；
  // immediate 保证首屏渲染时已存在的条件 tag 就能按单位与别名展示
  watch(
    () => fields.value,
    () => {
      if (fields.value.length) {
        for (const field of fields.value) {
          setFieldOptionsMap(
            field.name,
            field?.field_unit || '',
            field?.option_values?.map(v => ({
              id: v.value,
              name: v.alias,
            })) || []
          );
        }
      }
    },
    { immediate: true }
  );

  /**
   * 已选条件 tag 中 value 的展示格式化，按以下顺序处理：
   *
   * 1. 悬浮提示（isTips）直接透传原始值，避免提示里混入单位影响阅读与复制；
   * 2. 字段已登记进索引表时，先把取值换成枚举 alias（查不到就回退到取值本身），
   *    让用户看到可读名称而非存储值；
   * 3. 字段带单位时拼接单位，其中 bytes 走 byteConvert 换算（如 1048576 -> 1 MB）；
   * 4. 字段未登记进索引表（取值来自接口动态返回）时原样返回 val。
   */
  function tagValueDisplayFormatter(val, { value, key, isTips }) {
    if (isTips) {
      return val;
    }
    const fieldOptions = fieldOptionsMap.value.get(key);
    if (fieldOptions) {
      // 枚举里查不到时（用户手输、或候选值来自接口）回退到原始取值
      const name = fieldOptions.values.find(v => v.id === value.id)?.name || value.id;
      // 字节数直接展示原始值不直观，按 1024 进制换算成 KB/MB/...（转换结果自带单位，无需再拼接）
      if (fieldOptions.unit === 'bytes' && NON_NEGATIVE_NUMBER_REG.test(name)) {
        return byteConvert(Number(name));
      }
      if (fieldOptions.unit) {
        return `${name}${fieldOptions.unit}`;
      }
      return name;
    }
    return val;
  }

  return { getFieldValues, tagValueDisplayFormatter };
}
