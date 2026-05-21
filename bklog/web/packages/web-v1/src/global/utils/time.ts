import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);
dayjs.extend(timezone);

const extractSubMilliseconds = (time: string, precision: number): string => {
  const dotIndex = time.indexOf('.');

  if (dotIndex === -1) {
    return '0'.repeat(precision - 3);
  }

  const afterDot = time.slice(dotIndex + 1);
  const digitsOnly = afterDot.replace(/[^0-9]/g, '');
  return digitsOnly.padEnd(precision, '0').slice(3, precision);
};

export const formatTimeZoneString = (
  time: number | string,
  timezoneValue = 'Asia/Shanghai',
  format = 'YYYY-MM-DD HH:mm:ssZZ',
  fixFormat = true,
) => {
  let formatString = format || 'YYYY-MM-DD HH:mm:ssZZ';

  if (fixFormat && !/ZZ$/.test(formatString)) {
    formatString += 'ZZ';
  }

  const subMillisecondMatch = formatString.match(/S{4,}/);

  if (subMillisecondMatch && typeof time === 'string') {
    const maxPrecision = subMillisecondMatch[0].length;
    const extraDigits = extractSubMilliseconds(time, maxPrecision);
    const matchIndex = formatString.indexOf(subMillisecondMatch[0]);
    const prefixFormat = `${formatString.slice(0, matchIndex)}SSS`;
    const suffixFormat = formatString.slice(matchIndex + subMillisecondMatch[0].length);
    const dayjsInstance = time.endsWith('Z')
      ? dayjs.utc(time).tz(timezoneValue)
      : dayjs(time).tz(timezoneValue);

    return `${dayjsInstance.format(prefixFormat)}${extraDigits}${suffixFormat ? dayjsInstance.format(suffixFormat) : ''}`;
  }

  if (typeof time === 'string' && time.endsWith('Z')) {
    return dayjs.utc(time).tz(timezoneValue).format(formatString);
  }

  return dayjs(time).tz(timezoneValue).format(formatString);
};
