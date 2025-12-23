import useStore from "./use-store";
import { computed } from "vue";
import { formatTimeZoneString } from "@/global/utils/time";


export default () => {
  const store = useStore();

  const timezone = computed(() => {
    return store.state.userMeta.time_zone;
  })

  /**
   * 格式化时间字符串
   * @param time 时间戳或时间字符串（支持 ISO 8601 格式，如 2024-11-01T08:56:24.274552Z）
   * @returns 格式化后的时间字符串，格式：2025-11-04 21:44:38+0800
   */
  const formatTimeZone = (time: number | string) => {
    return formatTimeZoneString(time, timezone.value);
  }

  const defaultTimeFields = ['created_at', 'updated_at'];

  /**
   * 格式化响应列表中的时间字符串
   * @param list 响应列表
   * @returns 格式化后的响应列表
   */
  const formatResponseListTimeZoneString = (list: any[], appendVlaue = {}, timeFields?: string[]) => {
    const formatTimeFields = timeFields || defaultTimeFields;
    return list.map(item => {

      const formattedValue = {};

      formatTimeFields.forEach(field => {
        if (item[field]) {
          formattedValue[field] = formatTimeZone(item[field]);
        }
      });

      if (typeof appendVlaue === 'function') {
        Object.assign(formattedValue, appendVlaue(item) ?? {});
      } else {
        Object.assign(formattedValue, appendVlaue ?? {});
      }

      return Object.assign(item, formattedValue);
    })
  }

  return {
    timezone,
    formatTimeZone,
    formatResponseListTimeZoneString,
  }
}
