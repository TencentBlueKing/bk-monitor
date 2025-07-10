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
import dayjs from 'dayjs';
import { LANGUAGE_COOKIE_KEY, docCookies } from 'monitor-common/utils';

import type { IOption } from '../pages/monitor-k8s/typings';
import type { IMetricDetail } from '../pages/strategy-config/strategy-config-set-new/typings';
/**
 * 生成一个随机字符串ID
 * @param len 随机ID的长度 默认8位字符
 */
export const getRandomId = (len = 8): string => {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const charsLen = chars.length;
  let id = '';
  for (let i = 0; i < len; i++) {
    id += chars.charAt(Math.floor(Math.random() * charsLen));
  }
  return id;
};

/**
 * 数据检索日期范围转换
 * @param {*} timeRange number | string | array
 */
export const handleTimeRange = (timeRange: number | string | string[]): { startTime: number; endTime: number } => {
  let startTime = null;
  let endTime = null;
  if (typeof timeRange === 'number') {
    endTime = dayjs.tz().unix();
    startTime = endTime - timeRange / 1000;
  } else {
    switch (timeRange) {
      case 'today': // 今天到现在为止
        startTime = dayjs.tz().format('YYYY-MM-DD 00:00:00');
        endTime = dayjs.tz().unix();
        break;
      case 'yesterday': // 昨天
        startTime = dayjs.tz().subtract(1, 'days').format('YYYY-MM-DD 00:00:00');
        endTime = dayjs.tz().subtract(1, 'days').format('YYYY-MM-DD 23:59:59');
        break;
      case 'beforeYesterday': // 前天
        startTime = dayjs.tz().subtract(2, 'days').format('YYYY-MM-DD 00:00:00');
        endTime = dayjs.tz().subtract(2, 'days').format('YYYY-MM-DD 23:59:59');
        break;
      case 'thisWeek': // 本周一到现在为止
        startTime = dayjs.tz().day(0).format('YYYY-MM-DD 00:00:00');
        endTime = dayjs.tz().unix();
        break;
      default:
        // 自定义时间段
        if (typeof timeRange === 'string') {
          const timeArr = timeRange.split('--');
          startTime = timeArr[0].trim();
          endTime = timeArr[1].trim();
        } else {
          startTime = timeRange[0];
          endTime = timeRange[1];
        }
        break;
    }
    endTime = typeof endTime === 'number' ? endTime : dayjs.tz(endTime).unix();
    startTime = typeof startTime === 'number' ? startTime : dayjs.tz(startTime).unix();
  }
  return {
    startTime,
    endTime,
  };
};
/**
 * 下载文件
 * @param url 资源地址
 * @param name 资源名称
 */
export const downFile = (url: string, name = ''): void => {
  const element = document.createElement('a');
  element.setAttribute('href', url.replace(/^https?:/gim, location.protocol));
  element.setAttribute('download', name);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
};

/**
 * 跳转自愈路由拼接
 * @param hash 路由的哈希
 */
export const ftaUrl = (hash: string): string => {
  let url = '';
  const isDev = process.env.NODE_ENV === 'development';
  const { hostname, protocol, search } = location;
  if (isDev) {
    url = `${protocol}//${hostname}:7002/${search}${hash}`;
  } else {
    const host = `${window.bk_paas_host}${window.site_url}fta/?bizId=${window.bk_biz_id}`;
    url = `${host}${hash}`;
  }
  return url;
};

/**
 * @description: 将job日志的a标签转换为可点击跳转
 * @param {string} str: job执行日志
 * @return {string} 转换后的字符串
 */
export const transformJobUrl = (str: string): string => {
  let newStr = '';
  try {
    newStr = str.replace(/<a.*?href="(.*?)".*?>(.*?)<\/a>/g, (...args) => {
      const { 0: aStr, 1: url } = args;
      const newUrl = /^http/.test(url) ? url : window.bk_job_url + url;
      return aStr.replace(url, newUrl);
    });
  } catch (error) {
    console.log(error);
  }
  return newStr || str;
};

/**
 * @description: 格式化时间显示
 * @param {number} time 毫秒 | 秒
 * @return {*}
 */
export const formatTime = (time: number) => {
  let time2 = +time;
  if (Number.isNaN(time2)) return time2;
  time2 = `${time2}`.length === 10 ? time2 * 10 ** 3 : time2;
  const timeRes = dayjs.tz(time2).format('YYYY-MM-DD HH:mm:ss');
  return timeRes;
};

export interface ILogUrlParams {
  bizId: string;
  time_range?: 'customized'; // 带了时间start_time end_time必填
  keyword: string; // 搜索关键字
  addition: IAddition[]; // 搜索条件 即监控的汇聚条件
  start_time?: string; // 起始时间
  end_time?: string; // 终止时间
}
export interface IAddition {
  key: string;
  value: string[];
  method: string;
  condition?: 'and' | 'or';
}
/**
 * @description: 转换跳转日志平台所需的url参数
 * @param {ILogUrlParams} data
 * @return {*}
 */
export const transformLogUrlQuery = (data: ILogUrlParams): string => {
  const { keyword, addition, start_time, end_time, bizId, time_range } = data;
  let queryStr = '';
  const queryObj = {
    bizId,
    keyword,
    addition:
      addition?.map(set => ({
        field: set.key,
        operator: set.method,
        value: (set.value || []).join(','),
      })) || [],
    start_time: start_time || undefined,
    end_time: end_time || undefined,
    time_range,
  };
  queryStr = Object.keys(queryObj).reduce((str, key, i) => {
    const itemVal = queryObj[key];
    if (itemVal !== undefined) {
      const itemValStr = typeof itemVal === 'object' ? JSON.stringify(itemVal) : `${itemVal}`;
      return `${str}${i ? '&' : ''}${key}=${encodeURIComponent(itemValStr)}`;
    }
    return str;
  }, '?');
  return queryStr;
};

/**
 * 管理localStroage缓存
 * express 为缓存的生效时长(单位：ms), 超过express则缓存失效
 */
interface ILocalStroageItem {
  value: any;
  updateTime: number;
  express: number;
}
interface IStorage {
  set: (key: string, value: any, express: number) => void;
  get: (key: string) => any;
  remove: (key: string) => void;
}
export class Storage implements IStorage {
  /** 过期时长 */
  express: number = null;
  constructor(express?: number) {
    this.express = express;
  }
  /** 获取缓存 */
  get(key: string) {
    const dataStr = localStorage.getItem(key);
    if (!dataStr) return null;
    const data = JSON.parse(dataStr) as ILocalStroageItem;
    const nowTime = Date.now();
    if (data.express && data.express < nowTime - data.updateTime) {
      this.remove(key);
      return null;
    }
    return data.value;
  }
  /** 移除缓存 */
  remove(key: string) {
    localStorage.removeItem(key);
  }
  /** 设置缓存 */
  set(key: string, value: any, express: number = this.express) {
    const data: ILocalStroageItem = {
      value,
      updateTime: Date.now(),
      express,
    };
    localStorage.setItem(key, JSON.stringify(data));
  }
}

/**
 * 从目标数组右边查找数据
 * @param arr 目标数组
 * @param cb 匹配回调方法
 * @returns 返回目标item
 */
export const findRight = (arr: any[], cb: (item: any, i: number) => boolean) => {
  const leng = arr.length;
  if (!Array.isArray(arr) || !leng) return null;
  let i = leng - 1;
  while (i >= 0) {
    const item = arr[i];
    if (cb(item, i)) {
      return item;
    }
    i -= 1;
  }
  return null;
};

/**
 * 计算字符串展示所需要的长度 单位：px
 * @param lengPx 单字符长度 单位: px
 * @param lengPxDouble 双字符长度 单位: px
 */
export const getStrLengOfPx = (str: string, lengPx = 6, lengPxDouble = 13) => {
  const leng = str.toString().length;
  /** 双字节字符数量 */
  // biome-ignore lint/suspicious/noControlCharactersInRegex: <explanation>
  const count = str.toString().match(/[^\x00-\xff]/g)?.length || 0;
  return lengPx * (leng - count) + count * lengPxDouble;
};

/** 动态计算弹层宽度 单位: px
 * @param options 可选项数据
 * @param padding padding量 单位: px
 * @param min 最小值 单位: px
 * @return number 宽度值 单位: px
 */
export const getPopoverWidth = (options: IMetricDetail[] | IOption[], padding = 32, min?: number) => {
  const width = options.reduce((width, item) => {
    const curWidth = getStrLengOfPx(item.name as string, 6, 13) + padding;
    return Math.max(curWidth, width);
  }, 0);
  return min ? Math.max(width, min) : width;
};

/* 获取event事件的父级列表（新的浏览器版本无path属性） */
/**
 * 不传targetStr参数时: 获取event事件的父级列表
 * 传入targetStr参数时: 查找targetStr
 * @param event 事件对象
 * @param targetStr 目标节点
 * @returns event事件的父集列表 或者 targetStr
 */
export const getEventPaths = (event: any | Event, targetStr = ''): (any | Event)[] => {
  if (event.path) {
    return targetStr ? event.path : event.path.filter(dom => hasTargetCondition(dom, targetStr));
  }
  const path = [];
  let target = event.target;
  while (target) {
    if (targetStr) {
      if (hasTargetCondition(target, targetStr)) {
        path.push(target);
        return path;
      }
    } else {
      path.push(target);
    }
    target = target.parentNode;
  }
  return path;
};

/**
 * @description 查找targetNode是否含有指定名称为targetStr className | id | tagName
 * @param targetNode DOM节点
 * @param targetStr className | id | tagName
 * @returns
 */
export const hasTargetCondition = (targetNode: HTMLElement, targetStr: string): boolean => {
  const [prefix, ...args] = targetStr.split('');
  const content = args.join('');
  return (
    (prefix === '.' && targetNode.className?.includes(content)) ||
    (prefix === '#' && targetNode.id?.includes(content)) ||
    targetStr.toLocaleUpperCase() === targetNode.nodeName
  );
};

/* 删除字符串末尾的空格或指定的字符 */
export const rstrip = (str: string, char: string): string => {
  if (char === undefined) {
    return str.replace(/\s+$/, '');
  }
  const reg = new RegExp(`${char}$`);
  return str.replace(reg, '');
};

const idMap = new Map();
/**
 * 创建唯一ID
 * @param len id长度
 * @param keywords 关键字
 * @returns 唯一ID
 */
export const createOnlyId = (len = 6, keywords = 'abcdefghijklmnopqrstuvwxyz123456789') => {
  const fn = (len: number) => {
    const arr = [];
    for (let i = 0; i < len; i++) {
      const random = Math.floor(Math.random() * keywords.length);
      arr.push(keywords[random]);
    }
    return arr.join('');
  };

  let onlyId = fn(len);
  while (idMap.has(onlyId)) {
    onlyId = fn(len);
  }
  idMap.set(onlyId, onlyId);
  return onlyId;
};

export const isEnFn = () => docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';

/**
 * @description 是否包含emoji
 * @param value
 * @returns
 */
export function emojiRegex(value: string) {
  return /(\ud83c[\udf00-\udfff])|(\ud83d[\udc00-\ude4f\ude80-\udeff])|[\u2600-\u2B55]/g.test(value);
}

/**
 * @description 是否为连续空格
 * @param value
 * @returns
 */
export function allSpaceRegex(value: string) {
  return /^\s*$/.test(value);
}

/**
 * 验证表达式是否符合规范并返回验证结果
 * @param expression 表达式
 * @returns
 */
export function validateExpression(expression: string) {
  // 使用正则表达式验证表达式结构是否合法
  const structureCheck =
    /^([A-Za-z0-9]+|\(\s*[A-Za-z0-9+\-*/%^]+\s*\))([\+\-*/%^]\s*([A-Za-z0-9]+|\(\s*[A-Za-z0-9+\-*/%^]+\s*\)))*$/.test(
      expression
    );
  if (!structureCheck) {
    return { isValid: false, variables: [] };
  }

  // 提取所有英文变量
  const variables = [...new Set(expression.match(/[A-Za-z]+/g) || [])];
  return { isValid: true, variables };
}
