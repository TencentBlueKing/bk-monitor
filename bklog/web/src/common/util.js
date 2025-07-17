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

/**
 * @file 通用方法
 * @author  <>
 */

import { set } from 'vue';

import dayjs from 'dayjs';
import JSONBigNumber from 'json-bignumber';

import store from '../store';
/**
 * 函数柯里化
 *
 * @example
 *     function add (a, b) {return a + b}
 *     curry(add)(1)(2)
 *
 * @param {Function} fn 要柯里化的函数
 *
 * @return {Function} 柯里化后的函数
 */
export function curry(fn) {
  const judge = (...args) => (args.length === fn.length ? fn(...args) : arg => judge(...args, arg));
  return judge;
}

/**
 * 判断是否是对象
 *
 * @param {Object} obj 待判断的
 *
 * @return {boolean} 判断结果
 */
export function isObject(obj) {
  return obj !== null && typeof obj === 'object';
}

/**
 * 规范化参数
 *
 * @param {Object|string} type vuex type
 * @param {Object} payload vuex payload
 * @param {Object} options vuex options
 *
 * @return {Object} 规范化后的参数
 */
export function unifyObjectStyle(type, payload, options) {
  if (isObject(type) && type.type) {
    options = payload;
    payload = type;
    type = type.type;
  }

  if (process.env.NODE_ENV !== 'production') {
    if (typeof type !== 'string') {
      console.warn(`expects string as the type, but found ${typeof type}.`);
    }
  }

  return { type, payload, options };
}

/**
 * 以 baseColor 为基础生成随机颜色
 *
 * @param {string} baseColor 基础颜色
 * @param {number} count 随机颜色个数
 *
 * @return {Array} 颜色数组
 */
export function randomColor(baseColor, count) {
  const segments = baseColor.match(/[\da-z]{2}/g);
  // 转换成 rgb 数字
  for (let i = 0; i < segments.length; i++) {
    segments[i] = parseInt(segments[i], 16);
  }
  const ret = [];
  // 生成 count 组颜色，色差 20 * Math.random
  for (let i = 0; i < count; i++) {
    ret[i] = `#${Math.floor(segments[0] + (Math.random() < 0.5 ? -1 : 1) * Math.random() * 20).toString(
      16,
    )}${Math.floor(segments[1] + (Math.random() < 0.5 ? -1 : 1) * Math.random() * 20).toString(
      16,
    )}${Math.floor(segments[2] + (Math.random() < 0.5 ? -1 : 1) * Math.random() * 20).toString(16)}`;
  }
  return ret;
}

/**
 * min max 之间的随机整数
 *
 * @param {number} min 最小值
 * @param {number} max 最大值
 *
 * @return {number} 随机数
 */
export function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1) + min);
}

/**
 * 异常处理
 *
 * @param {Object} err 错误对象
 * @param {Object} ctx 上下文对象，这里主要指当前的 Vue 组件
 */
export function catchErrorHandler(err, ctx) {
  const { data } = err;
  if (data) {
    if (!data.code || data.code === 404) {
      ctx.exceptionCode = {
        code: '404',
        msg: '当前访问的页面不存在',
      };
    } else if (data.code === 403) {
      ctx.exceptionCode = {
        code: '403',
        msg: 'Sorry，您的权限不足!',
      };
    } else {
      console.error(err);
      ctx.bkMessageInstance = ctx.$bkMessage({
        theme: 'error',
        message: err.message || err.data.msg || err.statusText,
      });
    }
  } else {
    console.error(err);
    ctx.bkMessageInstance = ctx.$bkMessage({
      theme: 'error',
      message: err.message || err.data.msg || err.statusText,
    });
  }
}

/**
 * 获取字符串长度，中文算两个，英文算一个
 *
 * @param {string} str 字符串
 *
 * @return {number} 结果
 */
export function getStringLen(str) {
  let len = 0;
  for (let i = 0; i < str.length; i++) {
    if (str.charCodeAt(i) > 127 || str.charCodeAt(i) === 94) {
      len += 2;
    } else {
      len = len + 1;
    }
  }
  return len;
}

/**
 * 转义特殊字符
 *
 * @param {string} str 待转义字符串
 *
 * @return {string} 结果
 */
export const escape = str => String(str).replace(/([.*+?^=!:${}()|[\]/\\])/g, '\\$1');

/**
 * 对象转为 url query 字符串
 *
 * @param {*} param 要转的参数
 * @param {string} key key
 *
 * @return {string} url query 字符串
 */
export function json2Query(param, key) {
  const mappingOperator = '=';
  const separator = '&';
  let paramStr = '';

  if (
    param instanceof String ||
    typeof param === 'string' ||
    param instanceof Number ||
    typeof param === 'number' ||
    param instanceof Boolean ||
    typeof param === 'boolean'
  ) {
    paramStr += separator + key + mappingOperator + encodeURIComponent(param);
  } else {
    Object.keys(param).forEach(p => {
      const value = param[p];
      const k =
        key === null || key === '' || key === undefined ? p : key + (param instanceof Array ? `[${p}]` : `.${p}`);
      paramStr += separator + json2Query(value, k);
    });
  }
  return paramStr.substr(1);
}

/**
 * 字符串转换为驼峰写法
 *
 * @param {string} str 待转换字符串
 *
 * @return {string} 转换后字符串
 */
export function camelize(str) {
  return str.replace(/-(\w)/g, (strMatch, p1) => p1.toUpperCase());
}

/**
 * 获取元素的样式
 *
 * @param {Object} elem dom 元素
 * @param {string} prop 样式属性
 *
 * @return {string} 样式值
 */
export function getStyle(elem, prop) {
  if (!elem || !prop) {
    return false;
  }

  // 先获取是否有内联样式
  let value = elem.style[camelize(prop)];

  if (!value) {
    // 获取的所有计算样式
    let css = '';
    if (document.defaultView && document.defaultView.getComputedStyle) {
      css = document.defaultView.getComputedStyle(elem, null);
      value = css ? css.getPropertyValue(prop) : null;
    }
  }

  return String(value);
}

/**
 *  获取元素相对于页面的高度
 *
 *  @param {Object} node 指定的 DOM 元素
 */
export function getActualTop(node) {
  let actualTop = node.offsetTop;
  let current = node.offsetParent;

  while (current !== null) {
    actualTop += current.offsetTop;
    current = current.offsetParent;
  }

  return actualTop;
}

/**
 *  获取元素相对于页面左侧的宽度
 *
 *  @param {Object} node 指定的 DOM 元素
 */
export function getActualLeft(node) {
  let actualLeft = node.offsetLeft;
  let current = node.offsetParent;

  while (current !== null) {
    actualLeft += current.offsetLeft;
    current = current.offsetParent;
  }

  return actualLeft;
}

/**
 * document 总高度
 *
 * @return {number} 总高度
 */
export function getScrollHeight() {
  let scrollHeight = 0;
  let bodyScrollHeight = 0;
  let documentScrollHeight = 0;

  if (document.body) {
    bodyScrollHeight = document.body.scrollHeight;
  }

  if (document.documentElement) {
    documentScrollHeight = document.documentElement.scrollHeight;
  }

  scrollHeight = bodyScrollHeight - documentScrollHeight > 0 ? bodyScrollHeight : documentScrollHeight;

  return scrollHeight;
}

/**
 * 滚动条在 y 轴上的滚动距离
 *
 * @return {number} y 轴上的滚动距离
 */
export function getScrollTop() {
  let scrollTop = 0;
  let bodyScrollTop = 0;
  let documentScrollTop = 0;

  if (document.body) {
    bodyScrollTop = document.body.scrollTop;
  }

  if (document.documentElement) {
    documentScrollTop = document.documentElement.scrollTop;
  }

  scrollTop = bodyScrollTop - documentScrollTop > 0 ? bodyScrollTop : documentScrollTop;

  return scrollTop;
}

/**
 * 浏览器视口的高度
 *
 * @return {number} 浏览器视口的高度
 */
export function getWindowHeight() {
  const windowHeight =
    document.compatMode === 'CSS1Compat' ? document.documentElement.clientHeight : document.body.clientHeight;

  return windowHeight;
}

export function projectManage(menuProject, projectName, childName) {
  let project = '';
  try {
    menuProject.forEach(res => {
      if (res.id === projectName && res.children) {
        res.children.forEach(item => {
          if (item.id === childName) {
            project = item.project_manage;
          }
        });
      }
    });
  } catch (e) {
    console.log(e);
  }
  return project;
}

export function projectManages(menuList, id) {
  for (const menu of menuList) {
    if (menu.id === id) {
      return menu.project_manage;
    }
    if (menu.children) {
      const recursiveResult = projectManages(menu.children, id);
      if (recursiveResult !== undefined) {
        return recursiveResult;
      }
    }
  }
  return undefined;
}

/**
 * 设置显示字段的最小宽度，此方法会修改第一个参数的数据
 * @param {Array} visibleFieldsList
 * @param {Object} fieldsWidthInfo
 * @param {Number} minWidth 固定最小宽度
 */
export function setFieldsWidth(visibleFieldsList, fieldsWidthInfo, minWidth = 1000) {
  // const totalUnit = visibleFieldsList.forEach(item => {
  //     const key = item.field_name
  //     const maxLength = fieldsWidthInfo[key].max_length || 0
  //     rowObj[key] = maxLength
  //     rowWidth.push(maxLength)
  // })
  const rowObj = {};
  const rowWidth = [];
  visibleFieldsList.forEach(item => {
    const key = item.field_name;

    const mlength = fieldsWidthInfo[key]?.max_length || 0;
    let maxLength = mlength;
    if (mlength._isBigNumber) {
      maxLength = mlength.toNumber() ?? 0;
    }
    rowObj[key] = maxLength;
    rowWidth.push(maxLength);
  });
  const rowNum = rowWidth.length;
  const allWidth = rowWidth.reduce((accumulator, currentValue) => accumulator + currentValue, 0);
  if (Math.ceil(allWidth * 6.5) <= minWidth - rowNum * 20) {
    visibleFieldsList.forEach(fieldInfo => {
      const key = fieldInfo.field_name;
      rowObj[key] = rowObj[key] < 9 ? 9 : rowObj[key];
      rowObj[key] = rowObj[key] > 30 ? rowObj[key] / 1.5 : rowObj[key];
      fieldInfo.minWidth = (rowObj[key] / allWidth) * (minWidth - rowNum * 20);
    });
  } else {
    const half = Math.ceil(rowNum / 2);
    const proportion = [];
    for (const key in rowObj) {
      const width = rowObj[key] * 6.5;
      if (width >= Math.floor((half / rowNum) * minWidth)) {
        proportion.push(half);
      } else if (width <= Math.floor((1 / rowNum) * minWidth)) {
        proportion.push(1);
      } else {
        proportion.push(Math.floor((width * rowNum) / minWidth));
      }
    }
    const proportionNum = proportion.reduce((accumulator, currentValue) => accumulator + currentValue, 0);
    visibleFieldsList.forEach((fieldInfo, index) => {
      fieldInfo.minWidth = minWidth * (proportion[index] / proportionNum);
    });
  }
}

/**
 * 返回日期格式 2020-04-13 09:15:14.123
 * @param {Number | String | Date} val
 * @return {String}
 */
export function formatDate(val, isTimzone = true, formatMilliseconds = false) {
  const date = new Date(val);

  if (isNaN(date.getTime())) {
    console.warn('无效的时间');
    return '';
  }

  if (isTimzone) {
    // 将时间戳转换为毫秒级别，如果是10位时间戳则乘以1000
    if (val.toString().length === 10) val *= 1000;
    // 获取毫秒部分的最后三位
    const milliseconds = val % 1000;
    // 创建 dayjs 对象
    const date = dayjs.tz(Number(val));

    // 如果毫秒部分不为 000，展示毫秒精度的时间
    const formatStr = formatMilliseconds && milliseconds !== 0 ? 'YYYY-MM-DD HH:mm:ss.SSS' : 'YYYY-MM-DD HH:mm:ss';
    return date.format(formatStr);
  }

  const yyyy = date.getFullYear();
  const mm = `0${date.getMonth() + 1}`.slice(-2);
  const dd = `0${date.getDate()}`.slice(-2);
  const time = date.toTimeString().slice(0, 8);
  return `${yyyy}-${mm}-${dd} ${time}`;
}

/**
 * 将ISO 8601格式 2024-04-09T13:02:11.502064896Z 转换成 普通日期格式 2024-04-09 13:02:11.502064896
 */
export function formatDateNanos(val) {
  if (/^\d+$/.test(`${val}`)) {
    return formatDate(Number(val), true, `${val}`.length > 10);
  }

  // dayjs不支持纳秒 从符串中提取毫秒之后的纳秒部分
  const nanoseconds = `${val}`.slice(23, -1);

  // 使用dayjs解析字符串到毫秒 包含时区处理
  const dateTimeToMilliseconds = dayjs(val).tz(window.timezone).format('YYYY-MM-DD HH:mm:ss.SSS');
  // 获取微秒并且判断是否是000，也就是纳秒部分的最后三位
  const microseconds = nanoseconds % 1000;
  const newNanoseconds = microseconds !== 0 ? nanoseconds : nanoseconds.slice(0, 3);

  // 组合dayjs格式化的日期时间到毫秒和独立处理的纳秒部分
  const formattedDateTimeWithNanoseconds = `${dateTimeToMilliseconds}${newNanoseconds}`;

  return formattedDateTimeWithNanoseconds;
}

/**
 * 格式化文件大小
 * @param {Number | String} size
 * @param {boolean} dropFractionIfInteger - 如果为 true，整数不保留小数
 * @return {String}
 */
export function formatFileSize(size, dropFractionIfInteger = false) {
  const value = Number(size);
  if (size && !isNaN(value)) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB', 'BB'];
    let index = 0;
    let k = value;
    if (value >= 1024) {
      while (k > 1024) {
        k = k / 1024;
        index = index + 1;
      }
    }
    const formattedSize = dropFractionIfInteger && k % 1 === 0 ? k.toFixed(0) : k.toFixed(2);
    return `${formattedSize}${units[index]}`;
  }
  return '0';
}

/**
 * 读取Blob格式返回数据
 * @param {*} response
 */
export function readBlobResponse(response) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = function () {
      resolve(reader.result);
    };

    reader.onerror = function () {
      reject(reader.error);
    };

    reader.readAsText(response);
  });
}

/**
 * 读取Blob格式返回Json数据
 * @param {*} resp
 */
export function readBlobRespToJson(resp) {
  return readBlobResponse(resp).then(resText => Promise.resolve(JSONBigNumber.parse(resText)));
}
export function bigNumberToString(value) {
  // eslint-disable-next-line @typescript-eslint/prefer-optional-chain
  return (value || {})._isBigNumber ? (value.toString().length < 16 ? Number(value) : value.toString()) : value;
}

export function formatBigNumListValue(value) {
  if (Object.prototype.toString.call(value) === '[object Object]' && value !== null && !value._isBigNumber) {
    const obj = {};
    if (value instanceof Array) {
      return (obj[value] = parseBigNumberList(value));
    }
    Object.keys(value).forEach(opt => {
      obj[opt] =
        Object.prototype.toString.call(obj[opt]) === '[object Object]' && obj[opt] !== null && !obj[opt]._isBigNumber
          ? formatBigNumListValue(obj[opt])
          : bigNumberToString(value[opt] ?? '');
    });
    return obj;
  }
  return bigNumberToString(value ?? '');
}

export function parseBigNumberList(lsit) {
  return (lsit || []).map(item =>
    Object.keys(item || {}).reduce((output, key) => {
      return {
        ...output,
        [key]: formatBigNumListValue(item[key]),
      };
    }, {}),
  );
}

/**
 * 生成随机数
 * @param {Number} n
 * @param str,默认26位字母及数字
 */
export const random = (n, str = 'abcdefghijklmnopqrstuvwxyz0123456789') => {
  // 生成n位长度的字符串
  // const str = 'abcdefghijklmnopqrstuvwxyz0123456789' // 可以作为常量放到random外面
  let result = '';
  for (let i = 0; i < n; i++) {
    result += str[parseInt(Math.random() * str.length, 10)];
  }
  return result;
};

/**
 * @desc: 复制文本
 * @param {*} val 文本
 * @param {*} alertMsg 弹窗文案
 */
export const copyMessage = (val, alertMsg = undefined) => {
  try {
    const input = document.createElement('input');
    input.setAttribute('value', val);
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    document.body.removeChild(input);
    window.mainComponent.messageSuccess(
      alertMsg ? alertMsg ?? window.mainComponent.$t('复制失败') : window.mainComponent.$t('复制成功'),
    );
  } catch (e) {
    console.warn(e);
  }
};

/**
 * @desc: 字符串转base64
 * @param { String } str
 */
export const base64Encode = str => {
  return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (match, p1) => String.fromCharCode(`0x${p1}`)));
};

/**
 * @desc: base64转字符串
 * @param { String } str
 */
export const base64Decode = str => {
  return decodeURIComponent(
    atob(str)
      .split('')
      .map(c => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
      .join(''),
  );
};

export const makeMessage = (message, traceId) => {
  const id = (traceId ?? '').split('-')[1] ?? '';

  const resMsg = `
    ${id || '--'} ：
    ${message}
  `;
  message &&
    console.log(`
  ------------------【日志】------------------
  【TraceID】：${id}
  【Message】：${message}
  ----------------------------------------------
  `);
  return resMsg;
};

export class Storage {
  /** 过期时长 */
  express = null;
  constructor(express) {
    this.express = express;
  }
  /** 设置缓存 */
  set(key, value, express = this.express) {
    const data = {
      value,
      updateTime: Date.now(),
      express,
    };
    localStorage.setItem(key, JSON.stringify(data));
  }
  /** 获取缓存 */
  get(key) {
    const dataStr = localStorage.getItem(key);
    if (!dataStr) return null;
    const data = JSON.parse(dataStr);
    const nowTime = Date.now();
    if (data.express && data.express < nowTime - data.updateTime) {
      this.remove(key);
      return null;
    }
    return data.value;
  }
  /** 移除缓存 */
  remove(key) {
    localStorage.removeItem(key);
  }
}

/**
 * 深拷贝
 * @param {Object} obj
 * @param {Map} hash
 */
export const deepClone = (obj, hash = new WeakMap()) => {
  if (Object(obj) !== obj) return obj;
  if (obj instanceof Set) return new Set(obj);
  if (hash.has(obj)) return hash.get(obj);
  const result =
    obj instanceof Date
      ? new Date(obj)
      : obj instanceof RegExp
        ? new RegExp(obj.source, obj.flags)
        : obj.constructor
          ? new obj.constructor()
          : Object.create(null);
  hash.set(obj, result);
  if (obj instanceof Map) {
    Array.from(obj, ([key, val]) => result.set(key, deepClone(val, hash)));
  }
  return Object.assign(result, ...Object.keys(obj).map(key => ({ [key]: deepClone(obj[key], hash) })));
};

/**
 * @desc: 清空bk-table表头的过滤条件
 * @param {HTMLElement} refInstance ref实例
 */
export const clearTableFilter = refInstance => {
  if (refInstance.$refs.tableHeader.filterPanels) {
    const { filterPanels } = refInstance.$refs.tableHeader;
    for (const key in filterPanels) {
      filterPanels[key].handleReset();
    }
  }
};

/**
 * @desc: 适合未作处理的bk-table表头添加tips
 */
export const renderHeader = (h, { column }) => {
  return h('p', { directives: [{ name: 'bk-overflow-tips' }], class: 'title-overflow' }, [column.label]);
};

/**
 * @desc: 对象深度对比
 * @param {Object} object1 对比对象A
 * @param {Object} object2 对比对象B
 * @param {Array<string>} ignoreArr 不对比的键名
 * @returns {Boolean} 两个对象是否相同
 */
export const deepEqual = (object1, object2, ignoreArr = []) => {
  if (object1 === object2) return true;
  const keys1Arr = Object.keys(object1);
  const keys2Arr = Object.keys(object2);
  if (keys1Arr.length !== keys2Arr.length) return false;

  for (const key1 of keys1Arr) {
    const val1 = object1[key1];
    let val2;
    if (keys2Arr.includes(key1)) {
      val2 = object2[key1];
      if (ignoreArr.includes(key1)) continue;
    } else {
      return false;
    }
    const areObjects = isObject(val1) && isObject(val2);
    if ((areObjects && !deepEqual(val1, val2, ignoreArr)) || (!areObjects && val1 !== val2)) return false;
  }
  return true;
};

// 是否是ipv6
export const isIPv6 = (str = '') => {
  return /^\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*$/.test(
    str,
  );
};

/** 是否强制更新现有的表格缓存显示字段 每次需要强制更新只需取反即可 */
const TABLE_FORCE = true;

// 列表设置刷新本地缓存
export const getDefaultSettingSelectFiled = (key, filed) => {
  const tableForceStr = localStorage.getItem('TABLE_FORCE');
  const parseForce = JSON.parse(tableForceStr);
  const selectObj = JSON.parse(localStorage.getItem('TABLE_SELECT_FILED'));
  const assignObj = {};
  if (!selectObj || !tableForceStr || parseForce !== TABLE_FORCE) {
    assignObj[key] = filed;
  } else {
    Object.assign(assignObj, selectObj);
    assignObj[key] = selectObj[key] ?? filed;
  }
  localStorage.setItem('TABLE_SELECT_FILED', JSON.stringify(assignObj));
  localStorage.setItem('TABLE_FORCE', JSON.stringify(TABLE_FORCE));
  return assignObj[key];
};

// 列表设置刷新本地缓存重置
export const setDefaultSettingSelectFiled = (key, filed) => {
  const selectObj = JSON.parse(localStorage.getItem('TABLE_SELECT_FILED'));
  selectObj[key] = filed;
  localStorage.setItem('TABLE_SELECT_FILED', JSON.stringify(selectObj));
};

/**
 * 防抖装饰器
 * @param delay
 */
export const Debounce =
  (delay = 200) =>
  (target, key, descriptor) => {
    const originFunction = descriptor.value;
    const getNewFunction = () => {
      let timer;
      const newFunction = function (...args) {
        if (timer) window.clearTimeout(timer);
        timer = setTimeout(() => {
          originFunction.call(this, ...args);
        }, delay);
      };
      return newFunction;
    };
    descriptor.value = getNewFunction();
    return descriptor;
  };

export const formatDateTimeField = (data, fieldType) => {
  if (fieldType === 'date') {
    return formatDate(Number(data)) || data || emptyCharacter;
  }

  // 处理纳秒精度的UTC时间格式
  if (fieldType === 'date_nanos') {
    return formatDateNanos(data) || emptyCharacter;
  }

  return data;
};

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
export const parseTableRowData = (
  row,
  key,
  fieldType = undefined,
  isFormatDate = store.state.isFormatDate,
  emptyCharacter = '--',
) => {
  const keyArr = key.split('.');
  let data;

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
              parseTableRowData(item, keyArr.slice(index).join('.'), fieldType, isFormatDate, emptyCharacter),
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

/** 表格内字体样式 */
export const TABLE_FOUNT_FAMILY = 'Menlo, Monaco, Consolas, Courier, PingFang SC, Microsoft Yahei, monospace';

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
      parseTableRowData(b, field.field_name, field.field_type).length -
      parseTableRowData(a, field.field_name, field.field_type).length
    );
  });

  // 字段名长度 需保证字段名完全显示
  const fieldNameLen = getTextPxWidth(field.field_name, '12px', TABLE_FOUNT_FAMILY);
  const minWidth = fieldNameLen + 80;
  if (firstLoadList[0]) {
    if (['ip', 'serverIp'].includes(field.field_name)) return [124, minWidth];
    if (field.field_name === 'dtEventTimeStamp') return [256, minWidth];
    if (/time/i.test(field.field_name)) return [256, minWidth];
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

/**
 * @desc: 扁平化对象
 * @param {Object} currentObject  递归的对象
 * @param {String} returnType 返回的值 对象key数组 对象value数组 重新扁平化的对象
 * @param {String} previousKeyName 递归的初始名字
 * @returns {Array | Object}
 */
export const getFlatObjValues = (currentObject, previousKeyName = '') => {
  const newFlatObj = {
    newKeyStrList: [],
    newValueList: [],
    newObject: {},
  };
  flatObjTypeFiledKeys(currentObject, newFlatObj, previousKeyName);
  return newFlatObj;
};

/**
 * @desc: 扁平化对象的key
 * @param {Object} currentObject 对象
 * @param {Object} newFlatObj 手机对象扁平化key的列表
 * @param {String} previousKeyName 递归的初始名字
 */
export const flatObjTypeFiledKeys = (currentObject = {}, newFlatObj, previousKeyName = '') => {
  for (const key in currentObject) {
    const value = currentObject[key];
    if (value === null) {
      newFlatObj.newKeyStrList.push(key);
      newFlatObj.newValueList.push('');
      newFlatObj.newObject[key] = '';
      continue;
    }
    if (value.constructor !== Object) {
      if (previousKeyName === null || previousKeyName === '') {
        newFlatObj.newKeyStrList.push(key);
        newFlatObj.newValueList.push(value);
        newFlatObj.newObject[key] = value;
      } else {
        if (key === null || key === '') {
          newFlatObj.newKeyStrList.push(previousKeyName);
          newFlatObj.newValueList.push(value);
          newFlatObj.newObject[previousKeyName] = value;
        } else {
          newFlatObj.newKeyStrList.push(`${previousKeyName}.${key}`);
          newFlatObj.newValueList.push(value);
          newFlatObj.newObject[`${previousKeyName}.${key}`] = value;
        }
      }
    } else {
      if (previousKeyName === null || previousKeyName === '') {
        flatObjTypeFiledKeys(value, newFlatObj, key);
      } else {
        flatObjTypeFiledKeys(value, newFlatObj, `${previousKeyName}.${key}`);
      }
    }
  }
};

export const TABLE_LOG_FIELDS_SORT_REGULAR = /^[_]{1,2}|[_]{1,2}/g;

export const utcFormatDate = val => {
  const date = new Date(val);

  if (isNaN(date.getTime())) {
    console.warn('无效的时间');
    return val;
  }

  return formatDate(date.getTime());
};

// 首次加载设置表格默认宽度自适应
export const setDefaultTableWidth = (visibleFields, tableData, catchFieldsWidthObj = null, staticWidth = 50) => {
  try {
    if (tableData.length && visibleFields.length) {
      visibleFields.forEach(field => {
        const [fieldWidth, minWidth] = calculateTableColsWidth(field, tableData);
        let width = fieldWidth < minWidth ? minWidth : fieldWidth;
        if (catchFieldsWidthObj) {
          const catchWidth = catchFieldsWidthObj[field.field_name];
          width = catchWidth ?? fieldWidth;
        }

        set(field, 'width', width);
        set(field, 'minWidth', minWidth);
      });
      const columnsWidth = visibleFields.reduce((prev, next) => prev + next.width, 0);
      const tableElem = document.querySelector('.original-log-panel');
      // 如果当前表格所有列总和小于表格实际宽度 则对小于800（最大宽度）的列赋值 defalut 使其自适应
      const availableWidth = tableElem.clientWidth - staticWidth;
      if (tableElem && columnsWidth && columnsWidth < availableWidth) {
        const longFiels = visibleFields.filter(item => item.width >= 800);
        if (longFiels.length) {
          const addWidth = (availableWidth - columnsWidth) / longFiels.length;
          longFiels.forEach(item => {
            set(item, 'width', item.width + Math.ceil(addWidth));
          });
        } else {
          const addWidth = (availableWidth - columnsWidth) / visibleFields.length;
          visibleFields.forEach(field => {
            set(field, 'width', field.width + Math.ceil(addWidth));
          });
        }
      }
    }

    return true;
  } catch (error) {
    return false;
  }
};

/**
 * @desc: 下载blob类型的文件
 * @param {Any} data 数据源
 * @param {String} fileName 文件名
 * @param {String} type 文件类型
 */
export const blobDownload = (data, fileName = 'default', type = 'text/plain') => {
  const blob = new Blob([data], { type });
  const downloadElement = document.createElement('a');
  const href = window.URL.createObjectURL(blob); // 创建下载的链接
  downloadElement.href = href;
  downloadElement.download = fileName; // 下载后文件名
  document.body.appendChild(downloadElement);
  downloadElement.click(); // 点击下载
  document.body.removeChild(downloadElement);
  window.URL.revokeObjectURL(href); // 释放掉blob对象
};

export const xssFilter = str => {
  return (
    str?.replace?.(/[&<>"]/gi, function (match) {
      switch (match) {
        case '&':
          return '&amp;';
        case '<':
          return '&lt;';
        case '>':
          return '&gt;';
        case '"':
          return '&quot;';
      }
    }) || str
  );
};
/** 数字千分位处理 */
export const formatNumberWithRegex = number => {
  var parts = number.toString().split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return parts.join('.');
};
/** 上下文，实时日志高亮颜色 */
// eslint-disable-next-line @typescript-eslint/naming-convention
export const contextHighlightColor = [
  {
    dark: '#FFB401',
    light: '#FFF6E1',
  },
  {
    dark: '#1CAB88',
    light: '#E8FFF5',
  },
  {
    dark: '#3A84FF',
    light: '#F0F5FF',
  },
  {
    dark: '#FF5656',
    light: '#FFEEEE',
  },
  {
    dark: '#00CBCB',
    light: '#E1FCFD',
  },
];

export const getOperatorKey = operator => `operator:${operator}`;

/**
 * 获取字符长度，汉字两个字节
 * @param str 需要计算长度的字符
 * @returns 字符长度
 */
export const getCharLength = str => {
  const len = str.length;
  let bitLen = 0;

  for (let i = 0; i < len; i++) {
    if ((str.charCodeAt(i) & 0xff00) !== 0) {
      bitLen += 1;
    }
    bitLen += 1;
  }

  return bitLen;
};

export const getRegExp = (searchValue, flags = 'ig') => {
  return new RegExp(`${searchValue}`.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&'), flags);
};

/** url中没有索引集indexID时候，拿浏览器存储的最后一次选中的索引集进行初始化 */
export const getStorageIndexItem = indexList => {
  const catchIndexSetStr = localStorage.getItem('CATCH_INDEX_SET_ID_LIST');
  if (catchIndexSetStr) {
    const catchIndexSetList = JSON.parse(catchIndexSetStr);
    const spaceUid = store.state.spaceUid;
    if (catchIndexSetList[spaceUid] && indexList.some(item => item.index_set_id === catchIndexSetList[spaceUid])) {
      return catchIndexSetList[spaceUid];
    }
  }
  return getHaveValueIndexItem(indexList);
};

/** 获取非无数据的索引集 */
export const getHaveValueIndexItem = indexList => {
  return (
    indexList.find(item => !item.tags.map(item => item.tag_id).includes(4))?.index_set_id || indexList[0].index_set_id
  );
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
 * 下载文件
 * @param url 资源地址
 * @param name 资源名称
 */
export const downFile = (url, name = '') => {
  const element = document.createElement('a');
  element.setAttribute('class', 'bklog-v3-popover-tag');
  element.setAttribute('href', url.replace(/^https?:/gim, location.protocol));
  element.setAttribute('download', name);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
};

/**
 * 根据json字符串下载json文件
 * @param jsonStr json字符串
 */
export const downJsonFile = (jsonStr, name = 'json-file.json') => {
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const href = window.URL.createObjectURL(blob);
  downFile(href, name);
};

/**
 * 获取当前操作系统
 */
export const getOs = () => {
  const userAgent = navigator.userAgent;
  const isMac = userAgent.includes('Macintosh');
  const isWin = userAgent.includes('Windows');
  return isMac ? 'macos' : isWin ? 'windows' : 'unknown';
};

/**
 * 获取当前操作系统的控制键盘文案
 */
export const getOsCommandLabel = () => {
  return getOs() === 'macos' ? 'Cmd' : 'Ctrl';
};
