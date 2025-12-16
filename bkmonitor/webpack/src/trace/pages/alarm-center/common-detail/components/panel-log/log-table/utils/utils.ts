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

import dayjs from 'dayjs';

/**
 *
 * @param str
 * @param delimiterPattern
 * @param wordsplit 是否分词
 * @returns
 */
export const optimizedSplit = (str: string, delimiterPattern: string, wordsplit = true) => {
  if (!str) {
    return [];
  }

  const tokens: Record<string, any>[] = [];
  let processedLength = 0;
  const CHUNK_SIZE = 200;

  if (wordsplit) {
    const MAX_TOKENS = 500;
    // 转义特殊字符，并构建用于分割的正则表达式
    const regexPattern = delimiterPattern
      .split('')
      .map(delimiter => `\\${delimiter}`)
      .join('|');

    const DELIMITER_REGEX = new RegExp(`(${regexPattern})`);
    const MARK_REGEX = /<mark>(.*?)<\/mark>/gis;

    const segments = str.split(/(<mark>.*?<\/mark>)/gi);

    for (const segment of segments) {
      if (tokens.length >= MAX_TOKENS) {
        break;
      }
      const isMark = MARK_REGEX.test(segment);

      const segmengtSplitList = segment.replace(MARK_REGEX, '$1').split(DELIMITER_REGEX).filter(Boolean);
      const normalTokens = segmengtSplitList.slice(0, MAX_TOKENS - tokens.length);

      if (isMark) {
        processedLength += '<mark>'.length;

        if (normalTokens.length === segmengtSplitList.length) {
          processedLength += '</mark>'.length;
        }
      }

      for (const t of normalTokens) {
        processedLength += t.length;
        tokens.push({
          text: t,
          isMark,
          isCursorText: !DELIMITER_REGEX.test(t),
        });
      }
    }
  }

  if (processedLength < str.length) {
    const remaining = str.slice(processedLength);

    const segments = remaining.split(/(<mark>.*?<\/mark>)/gi);
    for (const segment of segments) {
      const MARK_REGEX = /<mark>(.*?)<\/mark>/gis;
      const isMark = MARK_REGEX.test(segment);
      const chunkCount = Math.ceil(segment.length / CHUNK_SIZE);

      if (isMark) {
        tokens.push({
          text: segment.replace(MARK_REGEX, '$1'),
          isMark: true,
          isCursorText: false,
          isBlobWord: false,
        });
      } else {
        for (let i = 0; i < chunkCount; i++) {
          tokens.push({
            text: segment.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE),
            isMark: false,
            isCursorText: false,
            isBlobWord: false,
          });
        }
      }
    }
  }

  return tokens;
};

export const isNestedField = (fieldKeys, obj) => {
  if (!obj) {
    return false;
  }

  if (fieldKeys.length > 1) {
    if (obj[fieldKeys[0]] !== undefined && obj[fieldKeys[0]] !== null) {
      if (typeof obj[fieldKeys[0]] === 'object') {
        if (Array.isArray(obj[fieldKeys[0]])) {
          return true;
        }

        return isNestedField(fieldKeys.slice(1), obj[fieldKeys[0]]);
      }

      return false;
    }

    if (obj[fieldKeys[0]] === undefined) {
      return isNestedField([`${fieldKeys[0]}.${fieldKeys[1]}`, ...fieldKeys.slice(2)], obj);
    }
  }

  return false;
};

/**
 * 返回日期格式 2020-04-13 09:15:14.123
 * @param {Number | String | Date} val
 * @return {String}
 */
export function formatDate(val, isTimzone = true, formatMilliseconds = false) {
  try {
    const date = new Date(val);
    if (Number.isNaN(date.getTime())) {
      console.warn('无效的时间');
      return '';
    }

    // 如果是 2024-04-09T13:02:11.502064896Z 格式，则需要 formatDateNanos 转换
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{9}Z$/.test(val)) {
      return formatDateNanos(val);
    }

    if (isTimzone) {
      let timestamp = val;

      if (/^\d+\.?\d*$/.test(val)) {
        // 将时间戳转换为毫秒级别，如果是10位时间戳则乘以1000
        if (val.toString().length === 10) {
          timestamp = Number(val) * 1000;
        }
      }

      // 获取毫秒部分的最后三位
      const milliseconds = timestamp % 1000;
      // 创建 dayjs 对象
      const date = dayjs.tz(timestamp);

      // 如果毫秒部分不为 000，展示毫秒精度的时间
      const formatStr = formatMilliseconds && milliseconds !== 0 ? 'YYYY-MM-DD HH:mm:ss.SSS' : 'YYYY-MM-DD HH:mm:ss';
      return date.format(formatStr);
    }

    const yyyy = date.getFullYear();
    const mm = `0${date.getMonth() + 1}`.slice(-2);
    const dd = `0${date.getDate()}`.slice(-2);
    const time = date.toTimeString().slice(0, 8);
    return `${yyyy}-${mm}-${dd} ${time}`;
  } catch (e) {
    console.warn(e);
    return val;
  }
}

/**
 * 将ISO 8601格式 2024-04-09T13:02:11.502064896Z 转换成 普通日期格式 2024-04-09 13:02:11.502064896
 */
export function formatDateNanos(val) {
  const strVal = `${val}`;
  if (/^\d+$/.test(strVal)) {
    return formatDate(Number(val), true, `${val}`.length > 10);
  }

  if (/null|undefined/.test(strVal) || strVal === '') {
    return '--';
  }

  // dayjs不支持纳秒 从符串中提取毫秒之后的纳秒部分
  // 查找小数点位置，提取小数点后的所有数字
  const dotIndex = strVal.indexOf('.');
  let nanoseconds = '';

  if (dotIndex !== -1) {
    // 提取小数点后的部分
    const afterDot = strVal.slice(dotIndex + 1);
    // 移除时区标识符Z和非数字字符（如果存在），只保留数字
    const digitsOnly = afterDot.replace(/[^0-9]/g, '');
    // 提取毫秒（前3位）之后的部分作为纳秒
    nanoseconds = digitsOnly.length > 3 ? digitsOnly.slice(3) : '';
  }

  // 使用dayjs解析字符串到毫秒 包含时区处理
  const dateTimeToMilliseconds = dayjs(val).tz(window.timezone).format('YYYY-MM-DD HH:mm:ss.SSS');
  // 获取微秒并且判断是否是000，也就是纳秒部分的最后三位
  const nanosecondsNum = nanoseconds ? parseInt(nanoseconds, 10) : 0;
  const microseconds = nanosecondsNum % 1000;
  // 如果纳秒部分的最后三位（微秒部分）是000，只保留前3位；否则保留全部
  const newNanoseconds =
    microseconds !== 0 ? nanoseconds : nanoseconds.length > 3 ? nanoseconds.slice(0, 3) : nanoseconds;

  // 组合dayjs格式化的日期时间到毫秒和独立处理的纳秒部分
  const formattedDateTimeWithNanoseconds = `${dateTimeToMilliseconds}${newNanoseconds}`;

  return formattedDateTimeWithNanoseconds;
}

/**
 * 获取 row[key] 内容
 * @example return row.a.b || row['a.b']
 * @param {Object} row
 * @param {String} key
 * @param {String} fieldType
 * @param {Boolean} isFormatDate
 * @param {String} emptyCharacter
 * @return {String|Number}
 */
export const parseTableRowData = (row, key, fieldType = undefined, isFormatDate = false, emptyCharacter = '--') => {
  const keyArr = key.split('.');
  let data = null;

  try {
    if (keyArr.length === 1) {
      data = row[key];
    } else {
      for (let index = 0; index < keyArr.length; index++) {
        const item = keyArr[index];

        if (index === 0) {
          data = row[item];
          continue;
        }

        if (data === undefined) {
          break;
        }

        // 这里用于处理nested field
        if (Array.isArray(data)) {
          data = data
            .map(item =>
              parseTableRowData(item, keyArr.slice(index).join('.'), fieldType, isFormatDate, emptyCharacter)
            )
            .filter(item => item !== emptyCharacter);
          break;
        }

        if (data[item]) {
          data = data[item];
        } else {
          // 如果 x.y 不存在 返回 x['y.z'] x['y.z.z.z'] ...
          const validKey = keyArr.splice(index, keyArr.length - index).join('.');
          data = data[validKey];
          break;
        }
      }
    }
  } catch (e) {
    console.warn('List data analyses error：', e);
    data = emptyCharacter;
  }

  if (isFormatDate && ['date', 'date_nanos'].includes(fieldType)) {
    let formatData = data;
    let formatValue = data;
    let isMark = false;

    if (`${data}`.startsWith('<mark>')) {
      formatData = `${data}`.replace(/^<mark>/i, '').replace(/<\/mark>$/i, '');
      isMark = true;
    }

    if (fieldType === 'date' && /^\d+$/.test(formatData)) {
      formatValue = formatDate(Number(formatData)) || data || emptyCharacter;
    }

    // 处理纳秒精度的UTC时间格式
    if (fieldType === 'date_nanos') {
      formatValue = formatDateNanos(formatData) || emptyCharacter;
    }

    if (isMark) {
      return `<mark>${formatValue}</mark>`;
    }

    return formatValue;
  }

  if (Array.isArray(data) && !data.length) {
    return emptyCharacter;
  }

  if (typeof data === 'object' && data !== null) {
    return JSON.stringify(data);
  }

  return data === null || data === undefined || data === '' ? emptyCharacter : data;
};

/**
 * @desc: 计算字符串像素长度
 * @param {String} str 字符串
 * @param {String} fontSize 像素大小 默认12px
 * @param {String} fontFamily 字体样式
 * @returns {Number} 两个对象是否相同
 */
export const getTextPxWidth = (str, fontSize = '12px', fontFamily = null) => {
  let result = 10;
  const ele = document.createElement('span');
  // 字符串中带有换行符时，会被自动转换成<br/>标签，若需要考虑这种情况，可以替换成空格，以获取正确的宽度
  // str = str.replace(/\\n/g,' ').replace(/\\r/g,' ');
  ele.innerText = str;
  if (fontFamily) ele.style.fontFamily = fontFamily;
  // 不同的大小和不同的字体都会导致渲染出来的字符串宽度变化，可以传入尽可能完备的样式信息
  ele.style.fontSize = fontSize;
  // 由于父节点的样式会影响子节点，这里可按需添加到指定节点上
  document.body.append(ele);
  result = ele.offsetWidth;
  document.body.removeChild(ele);

  return result;
};

/** 表格内字体样式 */
export const TABLE_FOUNT_FAMILY = 'Menlo, Monaco, Consolas, Courier, PingFang SC, Microsoft Yahei, monospace';
/**
 * @desc: 计算
 * @param {String} str 字符串
 * @param {String} fontSize 像素大小 默认12px
 * @returns {Number} 长度
 */
export const calculateTableColsWidth = (field, list) => {
  // 取首屏前10条日志数据未计算模板
  const firstLoadList = list.slice(0, 10);
  // 通过排序获取最大的字段值
  firstLoadList.sort((a, b) => {
    return (
      (parseTableRowData(b, field.field_name, field.field_type)?.length ?? 0) -
      (parseTableRowData(a, field.field_name, field.field_type)?.length ?? 0)
    );
  });

  // 字段名长度 需保证字段名完全显示
  const fieldNameLen = getTextPxWidth(field.field_name, '12px', TABLE_FOUNT_FAMILY);
  const minWidth = fieldNameLen + 80;
  if (firstLoadList[0]) {
    if (['ip', 'serverIp'].includes(field.field_name)) return [124, minWidth];
    if (field.field_name === 'dtEventTimeStamp') return [256, minWidth];
    if (/time/i.test(field.field_name)) return [256, minWidth];
    if ('date' === field.field_type) return [256, minWidth];

    // 去掉高亮标签 保证不影响实际展示长度计算
    const fieldValue = String(parseTableRowData(firstLoadList[0], field.field_name, field.field_type))
      .replace(/<mark>/g, '')
      .replace(/<\/mark>/g, '');
    // 表格内字体如果用12px在windows系统下表格字体会显得很细，所以用13px来加粗
    // 实际字段值长度
    const fieldValueLen = getTextPxWidth(fieldValue, '12px', TABLE_FOUNT_FAMILY);

    if (field.field_type === 'text') {
      // 800为默认自适应最大宽度
      if (fieldValueLen > 800) return [800, minWidth];
    }

    if (fieldValueLen > 480) return [480, minWidth];

    // 当内容长度小于字段名长度 要保证表头字段名显示完整 80为 padding、排序icon、隐藏列icon
    if (fieldValueLen < minWidth) return [minWidth, minWidth];

    // 默认计算长度 40为padding
    return [fieldValueLen + 40, minWidth];
  }

  return [field.width, minWidth];
};
