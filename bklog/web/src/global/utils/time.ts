import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

// 确保时区插件已加载
dayjs.extend(utc);
dayjs.extend(timezone);

/**
 * 格式化时间字符串
 * @param time 时间戳或时间字符串（支持 ISO 8601 格式，如 2024-11-01T08:56:24.274552Z）
 * @param timezone timezone
 * @param format format
 * @param fixFormat 是否修复毫秒格式
 * @returns 格式化后的时间字符串，格式：2025-11-04 21:44:38+0800
 */
export const formatTimeZoneString = (
  time: number | string,
  timezone: string = 'Asia/Shanghai',
  format: string = 'YYYY-MM-DD HH:mm:ssZZ',
  fixFormat = true,
) => {
  let formatString = format || 'YYYY-MM-DD HH:mm:ssZZ';

  if (fixFormat && !/ZZ$/.test(formatString)) {
    formatString += 'ZZ';
  }

  // 如果是 ISO 8601 格式字符串（以 Z 结尾），先解析为 UTC，再转换到目标时区
  if (typeof time === 'string' && time.endsWith('Z')) {
    return dayjs.utc(time).tz(timezone)
      .format(formatString);
  }
  // 其他格式直接解析并转换时区
  return dayjs(time).tz(timezone)
    .format(formatString);
};

/**
 * 时间戳根据时区进行格式话
 * @param tiemstamp
 * @param timezone
 * @param format
 * @returns
 */
export const formatTimeStampZone = (timestamp: number, timezone: string, format?: string) => {
  let formatStr = format || 'YYYY-MM-DD HH:mm:ss';

  if (!format) {
    const milliseconds = `${timestamp}`.toString().split('.')[1]?.length ?? 0;
    if (milliseconds > 0) {
      formatStr = `YYYY-MM-DD HH:mm:ss.${'S'.repeat(milliseconds)}`;
    }
  }

  if (/^\d+(\.\d+)?$/.test(`${timestamp}`)) {
    return dayjs.utc(Number(timestamp)).tz(timezone)
      .format(formatStr);
  }

  return timestamp;
};
