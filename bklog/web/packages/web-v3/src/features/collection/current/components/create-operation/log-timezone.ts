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

import { computed, watch, type Ref } from 'vue';

export type TimeFormat = {
  id: string;
  name: string;
  description?: string;
};

export type TimeZoneOption = {
  id: number;
  name: string;
};

type LogTimeForm = {
  field_name: string;
  time_format: string;
  time_zone: number | string;
  log_reporting_time: boolean;
  etl_fields: { field_name?: string; value?: unknown }[];
};

type TimeField = {
  is_time?: boolean;
  option?: {
    time_format?: string;
    time_zone?: number | string;
    [key: string]: unknown;
  };
};

export function isTimestampFormat(format?: string): boolean {
  return format !== undefined && ['epoch_second', 'epoch_millis', 'epoch_micros'].includes(format);
}

/** 模板快照比较时忽略时间戳的时区差异，不修改原始配置。 */
export function normalizeTimestampTimeZones<T extends TimeField>(fields: T[]): T[] {
  return fields.map(field =>
    field.is_time && isTimestampFormat(field.option?.time_format)
      ? { ...field, option: { ...field.option, time_zone: 0 } }
      : field,
  );
}

export function hasTimeZone(format?: TimeFormat): boolean {
  const name = format?.name?.trim() ?? '';
  return /Z+$/i.test(name) || /^(ISO8601|rfc3339)$/i.test(name);
}

export function parseTimeZone(value: unknown, zones: TimeZoneOption[]): TimeZoneOption | null {
  if (typeof value !== 'string') return null;
  const matched = value.trim().match(/(?:Z|([+-])(\d{2}):?(\d{2}))$/i);
  if (!matched) return null;
  const hours = Number(matched[2] ?? 0);
  const minutes = Number(matched[3] ?? 0);
  if (hours > 23 || minutes > 59) return null;
  const offset = (hours + minutes / 60) * (matched[1] === '-' ? -1 : 1);
  return zones.find(item => item.id === offset) ?? null;
}

export function useLogTimeZone(
  form: Ref<LogTimeForm>,
  formats: Ref<TimeFormat[]>,
  zones: Ref<TimeZoneOption[]>,
  isTemplateBound: Ref<boolean>,
) {
  const isTimestamp = computed(() => isTimestampFormat(form.value.time_format));
  const formatHasTimeZone = computed(() => hasTimeZone(formats.value.find(item => item.id === form.value.time_format)));
  const sampleValue = computed(
    () => form.value.etl_fields.find(item => item.field_name === form.value.field_name)?.value,
  );
  const parsedTimeZone = computed(() =>
    !isTemplateBound.value && formatHasTimeZone.value ? parseTimeZone(sampleValue.value, zones.value) : null,
  );
  const isTimeZoneLocked = computed(() => !form.value.log_reporting_time && parsedTimeZone.value !== null);
  watch(
    [
      () => form.value.time_format,
      () => form.value.field_name,
      () => form.value.log_reporting_time,
      () => formats.value.find(item => item.id === form.value.time_format),
      () => form.value.etl_fields.find(item => item.field_name === form.value.field_name)?.value,
      () => zones.value,
      () => isTemplateBound.value,
      () => (parsedTimeZone.value ? form.value.time_zone : null),
    ],
    ([, , reportingTime, format, sample, options]) => {
      if (isTemplateBound.value || reportingTime || !hasTimeZone(format)) return;
      form.value.time_zone = parseTimeZone(sample, options)?.id ?? '';
    },
  );

  const changeTimeFormat = (format: string) => {
    if (format === form.value.time_format) return;
    form.value.time_zone = isTimestampFormat(format) ? 0 : '';
    form.value.time_format = format;
  };

  return {
    isTimestamp,
    formatHasTimeZone,
    parsedTimeZone,
    isTimeZoneLocked,
    changeTimeFormat,
  };
}
