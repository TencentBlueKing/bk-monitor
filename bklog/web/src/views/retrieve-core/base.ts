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
import OptimizedHighlighter from './optimized-highlighter';
import { random } from '../../common/util';
import { getRGBAColors } from './colors';
import RetrieveEvent from './retrieve-events';

export default class {
  // 滚动条查询条件
  globalScrollSelector: string;

  // 搜索栏高度
  searchBarHeight: number;

  // 左侧字段设置宽度
  leftFieldSettingWidth: number;

  // 左侧字段设置是否展示
  leftFieldSettingShown: boolean = true;

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

  isSearching: boolean = false;

  constructor({}) {
    this.randomTrendGraphClassName = `random-${random(12)}`;
    this.events = new Map();
    this.logRowsContainerId = `result_container_key_${random(12)}`;
    this.RGBA_LIST = getRGBAColors(0.3);
  }

  on(fnName: RetrieveEvent | RetrieveEvent[], callbackFn: (...args) => void) {
    const targetEvents = Array.isArray(fnName) ? fnName : [fnName];
    targetEvents.forEach(event => {
      if (this.events.has(event)) {
        if (!this.events.get(event).includes(callbackFn)) {
          this.events.get(event)?.push(callbackFn);
        }
        return this;
      }

      this.events.set(event, [callbackFn]);
    });

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
      const index = this.events.get(eventName)?.findIndex(item => item === fn);
      if (index !== -1) {
        this.events.get(eventName)?.splice(index, 1);
      }
      return;
    }
    this.events.delete(eventName);
  }

  runEvent(event: RetrieveEvent, ...args) {
    this.events.get(event)?.forEach(item => {
      if (typeof item === 'function') {
        item(...args);
      }
    });
  }

  getRegExp(reg: string | RegExp | number | boolean): RegExp {
    // 如果已经是 RegExp 对象，直接返回
    if (reg instanceof RegExp) return reg;

    const regString = String(reg);

    // 如果是纯字符串（非 /pattern/flags 格式）
    if (!regString.startsWith('/')) {
      // 处理转义字符（如 \b → \\b）
      const escapedPattern = regString.replace(/([.*+?^${}()|[\]\\])/g, '\\$1');
      return new RegExp(escapedPattern);
    }

    // 处理标准正则格式 /pattern/flags
    const lastSlashIndex = regString.lastIndexOf('/');
    if (lastSlashIndex <= 0) {
      // 如果只有一个 /（如 "/pattern"），默认无 flags
      const pattern = regString.slice(1);
      return new RegExp(pattern);
    }

    // 提取 pattern 和 flags
    const pattern = regString.slice(1, lastSlashIndex);
    const flags = regString.slice(lastSlashIndex + 1);

    // 处理转义字符（如 \b → \\b）
    const normalizedPattern = pattern.replace(/\\(.)/g, (match, char) => {
      // 保留正则特殊字符的转义（如 \b, \d, \w）
      if (/[bdDfnrsStvwW0]/.test(char)) return match;
      // 其他情况去掉多余的转义（如 \/ → /）
      return char;
    });

    return new RegExp(normalizedPattern, flags);
  }
}
