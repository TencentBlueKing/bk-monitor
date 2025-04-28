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

import OptimizedHighlighter from './retrieve-core/optimized-highlighter';
import RetrieveEvent from './retrieve-core/retrieve-events';
import { type GradeSetting, type GradeConfiguration } from './retrieve-core/interface';
import RetrieveBase from './retrieve-core/base';

export enum STORAGE_KEY {
  STORAGE_KEY_FAVORITE_SHOW = 'STORAGE_KEY_FAVORITE_SHOW',
  STORAGE_KEY_FAVORITE_WIDTH = 'STORAGE_KEY_FAVORITE_WIDTH',
}

export { RetrieveEvent, GradeSetting, GradeConfiguration };
// 滚动条查询条件
const GLOBAL_SCROLL_SELECTOR = '.retrieve-v2-index.scroll-y';
class RetrieveHelper extends RetrieveBase {
  constructor({ isFavoriteShow = false, favoriteWidth = 0 }) {
    super({});
    this.globalScrollSelector = GLOBAL_SCROLL_SELECTOR;
    this.isFavoriteShown = isFavoriteShow;
    this.favoriteWidth = favoriteWidth;
  }

  /**
   * 设置查询状态
   * @param isSearching
   */
  setSearchingValue(isSearching: boolean) {
    this.isSearching = isSearching;
    this.runEvent(RetrieveEvent.SEARCHING_CHANGE, isSearching);
  }

  /**
   * 更新索引集id
   * @param id
   */
  setIndexsetId(idList: string[], type: string) {
    this.indexSetIdList = idList;
    this.indexSetType = type;
    this.runEvent(RetrieveEvent.INDEX_SET_ID_CHANGE, idList, type);
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
      (
        options?.settings ?? [
          { id: 'level_1', enable: true },
          { id: 'level_2', enable: true },
          { id: 'level_3', enable: true },
          { id: 'level_4', enable: true },
          { id: 'level_5', enable: true },
          { id: 'level_6', enable: true },
        ]
      ).forEach((item: GradeSetting) => {
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
      return PRIORITY_ORDER.find(level => levelSet.has(level)) || 'others';
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
    if (this.leftFieldSettingWidth !== width) {
      this.leftFieldSettingWidth = width;
      this.runEvent(RetrieveEvent.LEFT_FIELD_SETTING_WIDTH_CHANGE, width);
    }
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
}

const isFavoriteShow = localStorage.getItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_SHOW) === 'true';
const favoriteWidth = Number(localStorage.getItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_WIDTH) ?? 240);

export default new RetrieveHelper({ isFavoriteShow, favoriteWidth });
