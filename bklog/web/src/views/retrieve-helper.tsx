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

import { Ref } from 'vue';
import { random } from '../common/util';

import OptimizedHighlighter from './optimized-highlighter';
import { getRgbaColors } from './colors';

// 滚动条查询条件
const GLOBAL_SCROLL_SELECTOR = '.retrieve-v2-index.scroll-y';

export interface GradeSetting {
  id: string;
  color: string;
  name: string;
  regExp: string;
  enable: boolean;
}

interface GradeConfiguration {
  disabled: boolean;
  type: 'custom' | 'normal';
  field: string; // 'field' is null, but we can define it as any unless more specific information is available
  settings: GradeSetting[];
}

export enum STORAGE_KEY {
  STORAGE_KEY_FAVORITE_SHOW = 'STORAGE_KEY_FAVORITE_SHOW',
  STORAGE_KEY_FAVORITE_WIDTH = 'STORAGE_KEY_FAVORITE_WIDTH',
}

export enum RetrieveEvent {
  /**
   * 展示收藏内容
   */
  FAVORITE_ACTIVE_CHANGE = 'favorite-active-change',

  /**
   * 收藏栏是否展示
   */
  FAVORITE_SHOWN_CHANGE = 'favorite-shown-change',

  /**
   * 收藏栏宽度变化
   */
  FAVORITE_WIDTH_CHANGE = 'favorite-width-change',

  /**
   * 左侧字段信息初始化
   */
  LEFT_FIELD_INFO_UPDATE = 'left-field-info-update',

  /**
   * 左侧字段设置宽度变化
   */
  LEFT_FIELD_SETTING_WIDTH_CHANGE = 'left-field-setting-width-change',

  /**
   * 左侧字段设置是否展示
   */
  LEFT_FIELD_SETTING_SHOWN_CHANGE = 'left-field-setting-shown-change',

  /**
   * 搜索栏高度变化
   */
  SEARCHBAR_HEIGHT_CHANGE = 'searchbar-height-change',

  /**
   * 趋势图高度变化
   */
  TREND_GRAPH_HEIGHT_CHANGE = 'trend-graph-height-change',

  /**
   * 趋势图搜索
   */
  TREND_GRAPH_SEARCH = 'trend-graph-search',

  /**
   * localStorage 变化
   */
  STORAGE_CHANGE = 'storage-change',

  /**
   * 打开索引配置
   */
  INDEX_CONFIG_OPEN = 'index-config-open',

  /**
   * 触发高亮设置
   */
  HILIGHT_TRIGGER = 'hilight-trigger',

  /**
   * 搜索条件改变
   */
  SEARCH_VALUE_CHANGE = 'search-value-change',

  /**
   * 搜索时间变化
   */
  SEARCH_TIME_CHANGE = 'search-time-change',

  /**
   * 全局滚动
   */
  GLOBAL_SCROLL = 'global-scroll',
}

class RetrieveHelper {
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

  // 趋势图添加随机类名
  // 用于监听趋势图高度变化
  randomTrendGraphClassName: string;

  // 趋势图高度
  trendGraphHeight: number;

  // 事件列表
  events: Map<string, ((...args) => void)[]>;

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

  constructor({ isFavoriteShow = false, favoriteWidth = 0 }) {
    this.globalScrollSelector = GLOBAL_SCROLL_SELECTOR;
    this.isFavoriteShown = isFavoriteShow;
    this.favoriteWidth = favoriteWidth;
    this.randomTrendGraphClassName = `random-${random(12)}`;
    this.events = new Map();
    this.logRowsContainerId = `result_container_key_${random(12)}`;
    this.RGBA_LIST = getRgbaColors(0.3);
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
   * // 初始化 Mark.js 实例
   * @param target
   */
  setMarkInstance(target?: (() => HTMLElement) | HTMLElement | Ref<HTMLElement> | string, root?: HTMLElement) {
    this.markInstance = new OptimizedHighlighter({
      target: target ?? (() => document.getElementById(this.logRowsContainerId)),
      chunkStrategy: 'fixed',
    });
  }

  highlightElement(target) {
    this.markInstance.highlightElement(target);
  }

  highLightKeywords(keywords?: string[], reset = true) {
    if (!this.markInstance) {
      return;
    }

    this.markInstance.setObserverConfig({ root: document.getElementById(this.logRowsContainerId) });
    this.markInstance.unmark();
    this.markInstance.highlight(
      (keywords ?? []).map((keyword, index) => {
        return {
          text: keyword,
          className: `highlight-${index}`,
          backgroundColor: this.RGBA_LIST[index % this.RGBA_LIST.length],
          textReg: new RegExp(`^${keyword}$`),
        };
      }),
      reset,
    );
  }

  updateMarkElement() {
    this.markInstance.incrementalUpdate();
  }

  /**
   * 解析日志级别
   * @param str
   * @returns
   */
  getLogLevel(field: any, options: GradeConfiguration) {
    if (options?.disabled) {
      return null;
    }

    if ((options?.type ?? 'normal') === 'normal') {
      const str = field?.log ?? '';

      if (!str?.trim()) return null;

      const levelRegExpList = [];
      (options?.settings ?? []).forEach((item: GradeSetting) => {
        if (item.enable && this.logLevelRegex[item.id]) {
          levelRegExpList.push(this.logLevelRegex[item.id]);
        }
      });

      const levelRegExStr = `/${levelRegExpList.join('|')}/`;
      const levelRegExp = new RegExp(levelRegExStr, 'gi');

      // 截取前1000字符避免性能问题
      const logSegment = str.slice(0, 1000);
      const matches = logSegment.matchAll(levelRegExp);
      const levelSet = new Set<string>();

      // 收集所有匹配的日志级别
      for (const match of matches) {
        const groups = match.groups || {};
        Object.keys(groups).forEach(level => {
          if (groups[level]) levelSet.add(level.toUpperCase());
        });
      }

      // 按优先级顺序查找最高级别
      const PRIORITY_ORDER = ['FATAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'TRACE'];
      return PRIORITY_ORDER.find(level => levelSet.has(level)) || null;
    }

    if (options.type === 'custom' && field[options.field]) {
      const target = `${field[options.field]}`;
      const levels = [];
      // 截取前1000字符避免性能问题
      const logSegment = target.slice(0, 1000);
      options.settings.forEach((item: GradeSetting) => {
        if (item.enable && item.id !== 'others') {
          new RegExp(item.regExp).test(logSegment) && levels.push(item.id);
        }
      });

      return levels[0] ?? 'others';
    }

    return null;
  }

  /**
   * 设置趋势图高度
   * 检索结果在滚动时需要依赖趋势图高度进行定位
   * @param height 可选值，如果不设置，则会默认尝试通过 randomTrendGraphClassName 获取高度
   */
  setTrendGraphHeight(height?: number) {
    if (!height) {
      const trendGraph = document.querySelector(`.${this.randomTrendGraphClassName}`) as HTMLElement;
      if (trendGraph) {
        height = trendGraph.offsetHeight;
      }
    }
    this.trendGraphHeight = height;
    this.runEvent(RetrieveEvent.TREND_GRAPH_HEIGHT_CHANGE, height);
  }

  /**
   * 设置检索栏高度
   * 检索栏会根据检索条件的变化自动调整高度
   * 这里需要更新检索栏高度的值，方便在滚动时计算字段统计的位置
   * @param height
   */
  setSearchBarHeight(height: number) {
    this.searchBarHeight = height;
    this.runEvent(RetrieveEvent.SEARCHBAR_HEIGHT_CHANGE, height);
  }

  setStorage(key: string, value: any) {
    localStorage.setItem(key, value);
  }

  /**
   * 更新字段设置宽度
   * 字段设置在用户手动调整宽度时，需要更新宽度
   * 在实现吸顶操作时， 设置字段设置占位预留宽度需要用到
   * @param width
   */
  setLeftFieldSettingWidth(width: number) {
    this.leftFieldSettingWidth = width;
    this.runEvent(RetrieveEvent.LEFT_FIELD_SETTING_WIDTH_CHANGE, width);
  }

  /**
   * 检索值变化
   * @param type 检索类型：ui/sql/filter
   * @param value
   */
  searchValueChange(type: 'ui' | 'sql' | 'filter', value: string | Array<any>) {
    this.runEvent(RetrieveEvent.SEARCH_VALUE_CHANGE, { type, value });
  }

  /**
   * 更新字段设置收否收起
   * 收起时表头位置计算逻辑需要更新
   * @param isShown
   */
  setLeftFieldIsShown(isShown: boolean) {
    this.leftFieldSettingShown = isShown;
    this.runEvent(RetrieveEvent.LEFT_FIELD_SETTING_SHOWN_CHANGE, isShown);
  }

  /**
   * 更新收藏栏宽度
   * 收藏栏在用户手动调整宽度时，需要更新宽度
   * 在实现吸顶操作时, 计算字段统计 left 位置需要用到
   * @param width
   */
  setFavoriteWidth(width: number) {
    this.favoriteWidth = width;
    localStorage.setItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_WIDTH, `${width}`);
    this.runEvent(RetrieveEvent.FAVORITE_WIDTH_CHANGE, width);
  }

  /**
   * 更新收藏栏是否展示
   * @param show
   */
  setFavoriteShown(show: boolean) {
    this.isFavoriteShown = show;
    localStorage.setItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_SHOW, `${show}`);
    this.runEvent(RetrieveEvent.FAVORITE_SHOWN_CHANGE, show);
  }

  /**
   * 更新滚动条查询条件
   * @param selector
   */
  setScrollSelector(selector?: string) {
    this.globalScrollSelector = selector ?? GLOBAL_SCROLL_SELECTOR;
  }

  /**
   * 更新收藏栏选中项
   * @param favorite
   */
  setFavoriteActive(favorite: any) {
    this.runEvent(RetrieveEvent.FAVORITE_ACTIVE_CHANGE, favorite);
  }

  /**
   * 打开索引配置
   * @param show
   */
  setIndexConfigOpen(show: boolean) {
    this.runEvent(RetrieveEvent.INDEX_CONFIG_OPEN, show);
  }

  getScrollSelector() {
    return this.globalScrollSelector;
  }

  /**
   * 获取当前浏览器操作系统为 window还是 macos
   */
  getOs() {
    const userAgent = navigator.userAgent;
    const isMac = userAgent.includes('Macintosh');
    const isWin = userAgent.includes('Windows');
    return isMac ? 'macos' : isWin ? 'windows' : 'unknown';
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

  private handleScroll = (e: MouseEvent) => {
    this.fire(RetrieveEvent.GLOBAL_SCROLL, e);
  };

  onMounted() {
    document.querySelector(this.globalScrollSelector)?.addEventListener('scroll', this.handleScroll);
  }

  destroy() {
    this.events.clear();
    document.querySelector(this.globalScrollSelector)?.removeEventListener('scroll', this.handleScroll);
  }

  private runEvent(event: RetrieveEvent, ...args) {
    this.events.get(event)?.forEach(item => {
      if (typeof item === 'function') {
        item(...args);
      }
    });
  }
}

const isFavoriteShow = localStorage.getItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_SHOW) === 'true';
const favoriteWidth = Number(localStorage.getItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_WIDTH) ?? 240);

export default new RetrieveHelper({ isFavoriteShow, favoriteWidth });
