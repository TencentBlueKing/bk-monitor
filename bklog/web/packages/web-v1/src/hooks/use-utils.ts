import { computed } from 'vue';

import { formatTimeZoneString } from '@/global/utils/time';

import useStore from './use-store';

export default () => {
  const store = useStore();

  const timezone = computed(() => store.state.userMeta.time_zone);

  const formatTimeZone = (time: number | string) => {
    return formatTimeZoneString(time, timezone.value);
  };

  const defaultTimeFields = ['created_at', 'updated_at'];

  const formatResponseListTimeZoneString = (list: any[], appendValue: Record<string, any> | ((item: any) => any) = {}, timeFields?: string[]) => {
    const formatTimeFields = timeFields || defaultTimeFields;

    return list.map(item => {
      const formattedValue = {};

      formatTimeFields.forEach(field => {
        if (item[field]) {
          formattedValue[field] = formatTimeZone(item[field]);
        }
      });

      if (typeof appendValue === 'function') {
        Object.assign(formattedValue, appendValue(item) ?? {});
      } else {
        Object.assign(formattedValue, appendValue ?? {});
      }

      return Object.assign(item, formattedValue);
    });
  };

  return {
    timezone,
    formatTimeZone,
    formatResponseListTimeZoneString,
  };
};
