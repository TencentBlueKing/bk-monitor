import { computed, watch, type Ref } from 'vue';

type TimeFormat = {
  id: string;
  name: string;
};

type TimeZoneOption = {
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
  return ['epoch_second', 'epoch_millis', 'epoch_micros'].includes(format);
}

export function getSubmitTimeZone(format: string, zone: number | string): number | string {
  return isTimestampFormat(format) ? 0 : zone;
}

/** 时间戳的时区仅作为接口兼容值提交，不修改表单或接口回填的配置。 */
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
    form.value.time_zone = '';
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
