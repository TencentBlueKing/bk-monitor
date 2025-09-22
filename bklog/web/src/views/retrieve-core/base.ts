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
import { formatDate, formatDateNanos, random } from '../../common/util';
import { getRGBAColors } from './colors';
import JsonFormatter from './json-formatter';
import StaticUtil from './static.util';

import type OptimizedHighlighter from './optimized-highlighter';
import type RetrieveEvent from './retrieve-events';

export default class {
  // 滚动条查询条件
  globalScrollSelector: string;

  // 搜索栏高度
  searchBarHeight: number;

  // 左侧字段设置宽度
  leftFieldSettingWidth: number;

  // 左侧字段设置是否展示
  leftFieldSettingShown = true;

  // 收藏栏宽度
  favoriteWidth: number;

  // 收藏栏是否展示
  isFavoriteShown: boolean;

  // 收藏栏是否仅查看当前索引集
  isViewCurrentIndex: boolean;

  // 趋势图添加随机类名
  // 用于监听趋势图高度变化
  randomTrendGraphClassName: string;

  // 趋势图高度
  trendGraphHeight: number;

  // 事件列表
  events: Map<string, ((...args) => void)[]>;

  // 索引集id列表
  indexSetIdList: string[];

  // 索引集类型
  indexSetType: string;

  markInstance: OptimizedHighlighter = undefined;

  // JSON格式化辅助
  jsonFormatter: JsonFormatter;

  // 正则表达式提取日志级别
  logLevelRegex = {
    level_1: '(?<FATAL>\\b(?:FATAL|CRITICAL|EMERGENCY)\\b)',
    level_2: '(?<ERROR>\\b(?:ERROR|ERRORCODE|ERR|FAIL(?:ED|URE)?)\\b)',
    level_3: '(?<WARNING>\\b(?:WARNING|WARN|ALERT|NOTICE)\\b)',
    level_4: '(?<INFO>\\b(?:INFO|INFORMATION|LOG|STATUS)\\b)',
    level_5: '(?<DEBUG>\\b(?:DEBUG|DIAGNOSTIC)\\b)',
    level_6: '(?<TRACE>\\b(?:TRACE|TRACING|VERBOSE|DETAIL)\\b)',
  };

  logRowsContainerId: string;

  RGBA_LIST: string[];

  isSearching = false;

  constructor() {
    this.randomTrendGraphClassName = `random-${random(12)}`;
    this.events = new Map();
    this.logRowsContainerId = `result_container_key_${random(12)}`;
    this.RGBA_LIST = getRGBAColors(0.3);
    this.jsonFormatter = new JsonFormatter();
  }

  formatDateValue(data: string, field_type: string) {
    const formatFn = {
      date: formatDate,
      date_nanos: formatDateNanos,
    };

    if (formatFn[field_type]) {
      if (`${data}`.startsWith('<mark>')) {
        const value = `${data}`.replace(/^<mark>/i, '').replace(/<\/mark>$/i, '');

        if (/^\d+$/.test(value)) {
          return `<mark>${formatFn[field_type](Number(value))}</mark>`;
        }
        return `<mark>${formatFn[field_type](value)}</mark>`;
      }

      if (/^\d+$/.test(data)) {
        return formatFn[field_type](Number(data)) || data || '--';
      }

      return formatFn[field_type](data) || data || '--';
    }
    return data;
  }

  on(fnName: RetrieveEvent | RetrieveEvent[], callbackFn: (...args) => void) {
    const targetEvents = Array.isArray(fnName) ? fnName : [fnName];
    for (const event of targetEvents) {
      if (!this.events.has(event)) {
        this.events.set(event, [callbackFn]);
      }

      if (this.events.has(event) && !this.events.get(event)?.includes(callbackFn)) {
        this.events.get(event)?.push(callbackFn);
      }
    }

    return this;
  }

  /**
   * 触发指定事件
   * 功能相当于 event bus
   * @param eventName
   * @param args
   */
  fire(eventName: RetrieveEvent, ...args) {
    this.runEvent(eventName, ...args);
  }

  /**
   * 移除事件
   * @param eventName
   * @param fn
   */
  off(eventName: RetrieveEvent, fn?: (...args) => void) {
    if (typeof fn === 'function') {
      const index = this.events.get(eventName)?.indexOf(fn);
      if (index !== -1) {
        this.events.get(eventName)?.splice(index, 1);
      }
      return;
    }
    this.events.delete(eventName);
  }

  /**
   * 批量移除事件
   * @param eventNames
   * @param fn
   */
  batchOff(eventNames: RetrieveEvent[], fn?: (...args) => void) {
    for (const eventName of eventNames) {
      this.off(eventName, fn);
    }
  }

  runEvent(event: RetrieveEvent, ...args) {
    for (const item of this.events.get(event) || []) {
      if (typeof item === 'function') {
        item(...args);
      }
    }
  }

  getRegExp(reg: RegExp | boolean | number | string, flgs?: string, fullMatch = false, formatRegStr = true): RegExp {
    return StaticUtil.getRegExp(reg, flgs, fullMatch, formatRegStr);
  }
}
