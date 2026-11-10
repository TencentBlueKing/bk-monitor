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

/**
 * 将时间值转为 EventTable 所需的毫秒时间戳。
 * 参考事件检索侧滑：time.value / time.alias 均为 number。
 */
export const normalizeEventTimeValue = (raw: any) => {
  const value = typeof raw === 'object' && raw !== null ? raw.value : raw;
  if (typeof value === 'number' && !Number.isNaN(value)) {
    return value;
  }
  if (typeof value === 'string' && value) {
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? value : parsed;
  }
  return value ?? '';
};

/**
 * 将 source / target 统一为事件检索侧滑同款结构。
 * panel_detail 可能返回空字符串，需兜底为对象，避免表格解构报错。
 */
export const normalizeEventFieldObject = (raw: any, fallbackAlias = '-') => {
  if (raw && typeof raw === 'object') {
    return {
      ...raw,
      alias: raw.alias ?? raw.value ?? fallbackAlias,
      value: raw.value ?? '',
    };
  }
  if (typeof raw === 'string' && raw) {
    return { alias: raw, value: raw };
  }
  return { alias: fallbackAlias, value: '' };
};

/**
 * 内容 detail 统一为对象（事件检索侧滑用 Object.values(detail) 渲染）。
 */
export const normalizeEventContentDetail = (detail: any) => {
  if (!detail) {
    return {};
  }
  if (Array.isArray(detail)) {
    if (!detail.length) {
      return {};
    }
    return Object.fromEntries(detail.map((item, index) => [item?.label || String(index), item]));
  }
  if (typeof detail === 'object') {
    return detail;
  }
  return {};
};

/** 从字段对象或字符串中取出原始 value */
const pickRawValue = (field: any, fallback = '') => {
  if (field && typeof field === 'object') {
    return field.value ?? fallback;
  }
  if (typeof field === 'string') {
    return field;
  }
  return fallback;
};

/**
 * 取出展示用 alias。
 * panel_detail：alias 多为字段标签，展示文案取 value；事件检索侧滑：alias 即展示文案。
 */
const pickDisplayAlias = (field: any, isPanelDetailFormat: boolean, fallback = '-') => {
  if (field && typeof field === 'object') {
    if (isPanelDetailFormat) {
      return field.value ?? field.alias ?? fallback;
    }
    return field.alias ?? field.value ?? fallback;
  }
  if (typeof field === 'string' && field) {
    return field;
  }
  return fallback;
};

/**
 * 将 panel_detail 事件记录适配为 EventTable 同款结构（对齐事件检索侧滑入参）。
 * 关键差异：
 * 1) 字段名 event_content → event.content
 * 2) panel_detail 的 alias 多为字段标签（如「事件内容」），展示文案应取 value
 * 3) time 需为毫秒时间戳
 * origin_data 其余字段原样透传，仅将 time 转为毫秒时间戳。
 */
export const normalizeEventTableRow = (item: Record<string, any>, index: number) => {
  const timeValue = normalizeEventTimeValue(item.time);
  // 本函数仅消费 panel_detail：字段形如 { value: 实际值, alias: 字段标签 }。
  // 只要没有事件检索侧滑的 event.content，即按 panel_detail 处理（勿依赖 event_content 是否存在，
  // 否则仅有 event_name 时会把 alias「事件名」当成展示文案）。
  const isPanelDetailFormat = !item['event.content'];
  const eventContentRaw = item['event.content'] || item.event_content;
  const eventNameRaw = item.event_name;

  let eventContent: { alias: string; detail: Record<string, any>; value: string };
  if (eventContentRaw && typeof eventContentRaw === 'object') {
    const contentValue = String(pickRawValue(eventContentRaw, '-'));
    eventContent = {
      value: contentValue,
      alias: String(pickDisplayAlias(eventContentRaw, isPanelDetailFormat, contentValue)),
      detail: normalizeEventContentDetail(eventContentRaw.detail),
    };
  } else if (typeof eventContentRaw === 'string' && eventContentRaw) {
    eventContent = {
      value: eventContentRaw,
      alias: eventContentRaw,
      detail: {},
    };
  } else {
    eventContent = { value: '-', alias: '-', detail: {} };
  }

  const eventNameValue = String(pickRawValue(eventNameRaw, '-'));
  const eventName = {
    value: eventNameValue,
    alias: String(pickDisplayAlias(eventNameRaw, isPanelDetailFormat, eventNameValue)),
  };

  // origin_data 其余字段原样透传；仅将 time 转为毫秒时间戳，供 KV tab 的 formatTime 使用
  const originData = { ...(item.origin_data || {}) };
  if (originData.time !== undefined) {
    originData.time = normalizeEventTimeValue(originData.time);
  }

  return {
    ...item,
    key: item.key ?? item._meta?.__doc_id ?? `panel-detail-event-${index}`,
    time: {
      value: timeValue,
      alias: timeValue,
    },
    type: item.type && typeof item.type === 'object' ? item.type : { value: 'Default', alias: 'Default' },
    event_name: eventName,
    // EventTable 列 key 固定为 'event.content'
    'event.content': eventContent,
    target: normalizeEventFieldObject(item.target),
    source: normalizeEventFieldObject(item.source),
    _meta: item._meta || {},
    origin_data: originData,
  };
};

/** 日志侧滑默认优先展示的列（按 payload 中实际存在的字段过滤） */
const DEFAULT_LOG_DISPLAY_FIELD_PRIORITY = [
  'dtEventTimeStamp',
  'requested_at',
  'method',
  '_path',
  'path',
  'status_code',
  'host',
  'result',
  'code',
  'log',
];

/**
 * 根据字段名与样本值推断 LogTableNew 所需的 field_type
 */
const inferLogFieldType = (fieldName: string, sampleValue: unknown): string => {
  if (/time|date|timestamp/i.test(fieldName)) {
    return 'date';
  }
  if (typeof sampleValue === 'number') {
    return 'long';
  }
  if (typeof sampleValue === 'boolean') {
    return 'boolean';
  }
  if (sampleValue && typeof sampleValue === 'object') {
    return 'object';
  }
  return 'text';
};

/**
 * 统一日志侧滑 fields 结构。
 * 字段接口和 panel_detail 都可能返回数组或字段 map；故障侧滑只消费系统默认
 * display_fields，不读取告警/BKLog 的 user_custom_config。
 */
export const normalizeLogFieldsPayload = (payload: any) => {
  if (!payload || typeof payload !== 'object') {
    return { fields: [], display_fields: [] as string[] };
  }

  const rawFields = payload.fields;
  let fields: Array<{
    [key: string]: any;
    field_name: string;
    field_type: string;
    max_length?: number;
    query_alias: string;
  }> = [];

  if (Array.isArray(rawFields)) {
    fields = rawFields
      .filter(item => item && typeof item === 'object')
      .map(item => ({
        ...item,
        field_name: item.field_name || item.query_alias || item.field_alias || '',
        query_alias: item.query_alias || item.field_alias || item.field_name || '',
        field_type: item.field_type || 'text',
      }))
      .filter(item => item.field_name);
  } else if (rawFields && typeof rawFields === 'object') {
    const sampleRow = payload.list?.[0] || payload.origin_log_list?.[0] || {};
    fields = Object.entries(rawFields).map(([fieldName, meta]) => {
      const sampleValue = fieldName.includes('.') ? undefined : sampleRow[fieldName];
      const metaObj = meta && typeof meta === 'object' ? (meta as Record<string, any>) : {};
      return {
        ...metaObj,
        field_name: fieldName,
        query_alias: fieldName,
        field_type: inferLogFieldType(fieldName, sampleValue),
        max_length: metaObj.max_length,
      };
    });
  }

  const fieldNames = fields.map(item => item.field_name);
  const responseDisplayFields = Array.isArray(payload.display_fields)
    ? payload.display_fields.filter(field => fieldNames.includes(field))
    : [];
  const preferred = DEFAULT_LOG_DISPLAY_FIELD_PRIORITY.filter(name => fieldNames.includes(name));

  return {
    ...payload,
    fields,
    display_fields: responseDisplayFields.length
      ? responseDisplayFields
      : preferred.length
        ? preferred
        : fieldNames.slice(0, 8),
  };
};

/** 字段设置确认时，空选择恢复接口返回的默认展示字段。 */
export const resolveLogDisplayFields = (fields: string[], defaultFields: string[]) =>
  fields.length ? [...fields] : [...defaultFields];
