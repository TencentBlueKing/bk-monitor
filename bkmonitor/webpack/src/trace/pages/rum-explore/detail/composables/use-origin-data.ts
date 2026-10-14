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
import { computed, shallowRef, unref } from 'vue';
import type { MaybeRef } from 'vue';

import dayjs from 'dayjs';

import { formatUnitValue } from '../../utils';
import { ORIGIN_NESTED_KEYS } from '../constants';

import type { IRumField } from '../../typings';
import type { IRumOriginBlockVM, IRumOriginRowVM } from '../typings';

/** datetime 字段合法的时间单位（小写比较，µs 为微秒在量纲表里的写法） */
const TIME_UNITS = new Set(['ns', 'us', 'µs', 'ms', 's']);

/** datetime 字段的时间展示格式，与详情侧 use-detail-formatter 保持一致 */
const DATETIME_FORMAT = 'YYYY-MM-DD HH:mm:ss';

/** 折叠时单行摘要里展示的键值对数量上限，超出由 CSS 省略 */
const SUMMARY_ITEM_LIMIT = 8;

/**
 * @description 原始数据面板：把 origin_data 拆成 Span / Attributes / Resource / Links / Events 五个折叠块
 *
 * Links 按 trace_id 分组，Events 按事件名分组（SENT / RECEIVED 等），Events 支持在块内按键或值搜索过滤。
 * @param originData 当前 span 的原始数据
 * @param fields 视图配置里的全量字段，originKey 命中字段 name 时按元信息格式化展示值
 */
export function useOriginData(
  originData: MaybeRef<Record<string, any> | undefined>,
  fields: MaybeRef<IRumField[]> = []
) {
  /** Events 块内的搜索关键字 */
  const eventKeyword = shallowRef('');

  const blocks = computed<IRumOriginBlockVM[]>(() => {
    const data = unref(originData);
    if (!data) return [];

    /** 字段名 → 字段元信息，originKey 命中字段 name 即可拿到单位与枚举 */
    const fieldMap = new Map(unref(fields).map(field => [field.name, field]));
    const getField = (originKey: string) => fieldMap.get(originKey);

    /** Span 块：顶层标量字段，嵌套字段各自有独立块 */
    const spanRows = Object.entries(data)
      .filter(([key]) => !ORIGIN_NESTED_KEYS.has(key))
      .map(([key, value]) => toRow(key, value, '', getField));
    const attributeRows = toRows(data.attributes, 'attributes', getField);
    const resourceRows = toRows(data.resource, 'resource', getField);

    /** 块内搜索关键字，只作用于 Events（Links 未开启 searchable） */
    const keyword = eventKeyword.value.trim().toLowerCase();
    /** Links 块：按链路分组，组名为 trace_id，组内为顶层字段 + attributes */
    const linkGroups = ((data.links || []) as Array<Record<string, any>>).map((link, index) => ({
      name: String(link.trace_id || `link_${index + 1}`),
      rows: [
        ...Object.entries(link)
          .filter(([key]) => key !== 'attributes')
          .map(([key, value]) => toRow(key, value, 'links', getField)),
        ...toRows(link.attributes, 'links.attributes', getField),
      ],
    }));
    /** Events 块：按事件名分组，组内为 timestamp + attributes；有关键字时只保留键或值命中的行 */
    const eventGroups = ((data.events || []) as Array<Record<string, any>>).map((event, index) => {
      const rows = [
        ...(event.timestamp === undefined ? [] : [toRow('timestamp', event.timestamp, 'events', getField)]),
        ...toRows(event.attributes, 'events.attributes', getField),
      ];
      return {
        name: String(event.name ?? `event_${index}`),
        rows: keyword
          ? rows.filter(row => row.key.toLowerCase().includes(keyword) || row.value.toLowerCase().includes(keyword))
          : rows,
      };
    });

    const result: IRumOriginBlockVM[] = [];
    if (spanRows.length) result.push({ key: 'span', title: 'Span', rows: spanRows, summary: toSummary(spanRows) });
    if (attributeRows.length) {
      result.push({ key: 'attributes', title: 'Attributes', rows: attributeRows, summary: toSummary(attributeRows) });
    }
    if (resourceRows.length) {
      result.push({ key: 'resource', title: 'Resource', rows: resourceRows, summary: toSummary(resourceRows) });
    }
    /** Links 块：不含搜索框，与 Events 共用分组渲染，靠 searchable 区分 */
    if (linkGroups.length) {
      result.push({
        key: 'links',
        title: `Links (${linkGroups.length})`,
        groups: linkGroups,
        summary: toSummary(linkGroups.flatMap(group => group.rows)),
      });
    }
    if (eventGroups.length) {
      result.push({
        key: 'events',
        title: `Events (${eventGroups.length})`,
        groups: eventGroups,
        searchable: true,
        summary: toSummary(eventGroups.flatMap(group => group.rows)),
      });
    }

    return result;
  });

  return { blocks, eventKeyword };
}

/**
 * 按字段元信息格式化行的展示值：
 * 枚举命中 → 「别名(原始值)」（别名与原始值相同时只显示原始值）；
 * datetime 字段（type 为 long、field_display_type 为 datetime、field_unit 为时间单位）且值为数字 → 时间文本；
 * 有单位且值为数字 → 「自适应单位数值(原始值)」（换算失败或结果与原始值相同时保持原始值）；
 * 其余情况保持原始值。
 */
function resolveDisplayValue(
  field: IRumField | undefined,
  value: string,
  valueType: IRumOriginRowVM['valueType']
): string {
  if (!field) return value;
  const optionAlias = field.option_values?.find(option => `${option.value}` === `${value}`)?.alias;
  if (optionAlias) return optionAlias === value ? value : `${optionAlias}（${value}）`;
  if (
    field.type === 'long' &&
    field.field_display_type === 'datetime' &&
    TIME_UNITS.has(field.field_unit.toLowerCase()) &&
    valueType === 'number'
  ) {
    /** 时间戳位数不定（秒 / 毫秒 / 微秒），统一按毫秒对齐后交给 dayjs */
    const formatted = dayjs.tz(+value.slice(0, 13).padEnd(13, '0')).format(DATETIME_FORMAT);
    return formatted;
  }
  if (field.field_unit && valueType === 'number') {
    const formatted = formatUnitValue(value, field.field_unit);
    if (formatted && formatted !== value) return formatted;
  }
  return value;
}

/** 按值的运行时类型决定前置的数据类型图标 */
function resolveValueType(value: unknown): IRumOriginRowVM['valueType'] {
  if (typeof value === 'number') return 'number';
  if (typeof value === 'boolean') return 'boolean';
  if (value && typeof value === 'object') return 'object';
  return 'string';
}

/** 对象序列化为单行 JSON（冒号、逗号后带一个空格），原文模式下打平展示 */
function stringifyFlat(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stringifyFlat).join(', ')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.entries(value)
      .map(([itemKey, itemValue]) => `${JSON.stringify(itemKey)}: ${stringifyFlat(itemValue)}`)
      .join(', ')}}`;
  }
  return JSON.stringify(value);
}

/**
 * 把字段名拼成原始数据里的完整路径（如 attributes.view.id），检索条件按这个路径回传。
 * 数组类型的块（links / events）沿用后端扁平化的字段命名，不带数组下标。
 */
function toOriginKey(prefix: string, key: string): string {
  return prefix ? `${prefix}.${key}` : key;
}

/**
 * 构造一行键值
 * @param key 展示用字段名（数组块内为后端扁平化后的末级字段名）
 * @param prefix 所属块的路径前缀，仅用于拼 originKey；Span 顶层字段不传
 * @param getField 按 originKey 查字段元信息，命中时格式化 displayValue
 */
function toRow(
  key: string,
  value: unknown,
  prefix = '',
  getField?: (originKey: string) => IRumField | undefined
): IRumOriginRowVM {
  const valueType = resolveValueType(value);
  const originKey = toOriginKey(prefix, key);
  const valueText = valueType === 'object' ? stringifyFlat(value) : String(value ?? '');
  return {
    key,
    originKey,
    valueType,
    value: valueText,
    displayValue: resolveDisplayValue(getField?.(originKey), valueText, valueType),
  };
}

/** 把对象铺平成键值行，嵌套对象整体序列化（原始数据面板只做一层展开） */
function toRows(
  source: Record<string, unknown> | undefined,
  prefix = '',
  getField?: (originKey: string) => IRumField | undefined
): IRumOriginRowVM[] {
  if (!source) return [];
  return Object.entries(source).map(([key, value]) => toRow(key, value, prefix, getField));
}

function toSummary(rows: IRumOriginRowVM[]): string {
  return rows
    .slice(0, SUMMARY_ITEM_LIMIT)
    .map(row => `${row.key} = ${row.value}`)
    .join(' | ');
}
