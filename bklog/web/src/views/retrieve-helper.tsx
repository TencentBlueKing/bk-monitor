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

import { parseTableRowData } from '@/common/util';

import RetrieveBase from './retrieve-core/base';
import { GradeFieldValueType, type GradeConfiguration, type GradeSetting } from './retrieve-core/interface';
import OptimizedHighlighter from './retrieve-core/optimized-highlighter';
import RetrieveEvent from './retrieve-core/retrieve-events';
import { RouteQueryTab } from './retrieve-v3/index.type';

export enum STORAGE_KEY {
  STORAGE_KEY_FAVORITE_SHOW = 'STORAGE_KEY_FAVORITE_SHOW',
  STORAGE_KEY_FAVORITE_VIEW_CURRENT_CHANGE = 'STORAGE_KEY_FAVORITE_VIEW_CURRENT_CHANGE',
  STORAGE_KEY_FAVORITE_WIDTH = 'STORAGE_KEY_FAVORITE_WIDTH',
}

export { GradeConfiguration, GradeSetting, RetrieveEvent };
// 滚动条查询条件
const GLOBAL_SCROLL_SELECTOR = '.retrieve-v2-index.scroll-y';
class RetrieveHelper extends RetrieveBase {
  scrollEventAdded = false;
  mousedownEvent = null;

  constructor({ isFavoriteShow = false, isViewCurrentIndex = true, favoriteWidth = 0 }) {
    super();
    this.globalScrollSelector = GLOBAL_SCROLL_SELECTOR;
    this.isFavoriteShown = isFavoriteShow;
    this.isViewCurrentIndex = isViewCurrentIndex;
    this.favoriteWidth = favoriteWidth;
    this.mousedownEvent = null;
  }

  /**
   * 设置鼠标按下事件
   * @param e 鼠标事件
   */
  setMousedownEvent(e?: MouseEvent) {
    this.mousedownEvent = e ?? null;
  }

  /**
   * 判断当前鼠标Mouseup事件是否在鼠标按下事件的偏移量内
   * @param e 鼠标事件
   * @param offset 偏移量，默认为4，如果 > 0，点击位置在偏移量内也判定为点击在选择区域内
   * @returns
   */
  isMouseSelectionUpEvent(e: MouseEvent, offset = 4) {
    if (!this.mousedownEvent) {
      return false;
    }

    const diffX = Math.abs(e.clientX - this.mousedownEvent.clientX);
    const diffY = Math.abs(e.clientY - this.mousedownEvent.clientY);

    return diffX > offset || diffY > offset;
  }

  /**
   * 判断当前鼠标点击位置是否在选中的文本区域
   * 需要根据当前鼠标点击位置和当前选中文本区域进行对比
   * 考虑文本换行，选择区域范围折行的区域需要进行详细判定
   * @param e 鼠标事件
   * @param lineSpacing 行间距，默认为0，如果 > 0，点击位置在行间距内也判定为点击在选择区域内
   */
  isClickOnSelection(e: MouseEvent, lineSpacing = 0) {
    const selection = window.getSelection();

    // 如果没有选中文本，直接返回 false
    if (!selection || selection.isCollapsed) {
      return false;
    }

    const rangeCount = selection.rangeCount;
    if (rangeCount === 0) {
      return false;
    }

    // 获取鼠标点击位置
    const clickPoint = {
      x: e.clientX,
      y: e.clientY,
    };

    // 遍历所有选中的范围
    for (const range of Array.from({ length: rangeCount }, (_, i) => selection.getRangeAt(i))) {
      // 获取范围的边界矩形
      const rects = range.getClientRects();

      // 检查鼠标点击位置是否在任何一个矩形内
      for (let j = 0; j < rects.length; j++) {
        const rect = rects[j];

        // 检查点击位置是否在矩形范围内（包含行间距）
        const expandedTop = rect.top - lineSpacing;
        const expandedBottom = rect.bottom + lineSpacing;

        if (
          clickPoint.x >= rect.left &&
          clickPoint.x <= rect.right &&
          clickPoint.y >= expandedTop &&
          clickPoint.y <= expandedBottom
        ) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * 阻止事件传播
   * @param e 鼠标事件
   */
  stopEventPropagation(e: MouseEvent) {
    e.preventDefault();
    e.stopImmediatePropagation();
    e.stopPropagation();
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
  setIndexsetId(idList: string[], type: string, fireEvent = true) {
    this.indexSetIdList = idList;
    this.indexSetType = type;
    if (fireEvent) {
      this.runEvent(RetrieveEvent.INDEX_SET_ID_CHANGE, idList, type);
    }
  }

  /**
   * // 初始化 Mark.js 实例
   * @param target
   */
  setMarkInstance(target?: (() => HTMLElement) | HTMLElement | Ref<HTMLElement> | string) {
    this.markInstance = new OptimizedHighlighter({
      target: target ?? (() => document.getElementById(this.logRowsContainerId)),
      chunkStrategy: 'fixed',
    });
  }

  destroyMarkInstance() {
    this.markInstance?.destroy();
  }

  highlightElement(target) {
    this.markInstance?.highlightElement(target);
  }

  /**
   * 高亮关键词
   * @param keywords 关键词
   * @param reset 是否重置
   * @param _afterMarkFn 高亮后回调
   */
  highLightKeywords(keywords?: string[], reset = true, _afterMarkFn?: () => void) {
    if (!this.markInstance) {
      return;
    }

    const { caseSensitive, regExpMark, accuracy } = this.markInstance.getMarkOptions();
    this.markInstance.setObserverConfig({ root: document.getElementById(this.logRowsContainerId) });
    this.markInstance.unmark();
    const formatRegStr = !regExpMark;
    this.markInstance.highlight(
      (keywords ?? []).map((keyword, index) => {
        return {
          text: keyword,
          className: `highlight-${index}`,
          backgroundColor: this.RGBA_LIST[index % this.RGBA_LIST.length],
          textReg: this.getRegExp(keyword, caseSensitive ? '' : 'i', accuracy === 'exactly', formatRegStr),
        };
      }),
      reset,
    );
  }

  updateMarkElement() {
    this.markInstance.incrementalUpdate();
  }

  isMatchedGroup(group, fieldValue, isGradeMatchValue) {
    if (isGradeMatchValue) {
      return group.fieldValue?.includes(fieldValue) ?? false;
    }

    const regExp = this.getRegExp(group.regExp);
    return regExp.test(fieldValue);
  }

  /**
   * 键盘按下事件拦截
   * 拦截键盘按下事件，如果按下的键是斜杠 "/"，需要判定当前是否在输入框内部
   * 如果不在输入框内部，则调用 callback 函数
   * @param event 键盘按下事件
   * @param callback 回调函数
   */
  beforeSlashKeyKeyDown(event: KeyboardEvent, callback: () => void) {
    const target = event.target as HTMLElement;
    // 检查按下的键是否是斜杠 "/"（需兼容不同键盘布局）
    const isSlashKey = event.key === '/' || event.keyCode === 191;

    if ((isSlashKey && target.tagName === 'INPUT') || target.tagName === 'TEXTAREA') {
      return;
    }

    callback();
  }

  /**
   * 解析日志级别
   * @param field
   * @param options
   * @returns
   */
  getLogLevel(field: any, options: GradeConfiguration) {
    if (options?.disabled) {
      return null;
    }

    if ((options?.type ?? 'normal') === 'normal') {
      const str = this.convertToMatchableString(field?.log);

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

    const fieldValue = parseTableRowData(field, options.field, options.fieldType);

    if (options.type === 'custom' && fieldValue) {
      const target = this.convertToMatchableString(fieldValue);

      if (!target) {
        return null;
      }

      const levels = [];
      // 截取前1000字符避免性能问题
      const logSegment = target.slice(0, 1000);
      options.settings.forEach((item: GradeSetting) => {
        if (item.enable && item.id !== 'others') {
          this.isMatchedGroup(item, logSegment, options.valueType === GradeFieldValueType.VALUE) &&
            levels.push(item.id);
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
  searchValueChange(type: 'filter' | 'sql' | 'ui', value: Array<any> | string) {
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
   * 收藏栏是否仅查看当前索引集
   * @param show
   */
  setViewCurrentIndexn(show: boolean) {
    this.isViewCurrentIndex = show;
    localStorage.setItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_VIEW_CURRENT_CHANGE, `${show}`);
    this.runEvent(RetrieveEvent.FAVORITE_VIEW_CURRENT_CHANGE, show);
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

  /**
   * 打开别名配置
   * @param show
   */
  setAliasConfigOpen(show: boolean) {
    this.runEvent(RetrieveEvent.ALIAS_CONFIG_OPEN, show);
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
   * 修复路由参数中的 tab 值
   * @param indexSetItem
   * @param tabValue
   * @returns
   */
  routeQueryTabValueFix(indexSetItem, tabValue?: string | string[], isUnionSearch = false) {
    const isclusteringEnable = () => {
      return (
        (indexSetItem?.scenario_id === 'log' && indexSetItem.collector_config_id !== null) ||
        indexSetItem?.scenario_id === 'bkdata'
      );
    };

    const isChartEnable = () => indexSetItem?.support_doris && !isUnionSearch;

    if (indexSetItem) {
      if (tabValue === RouteQueryTab.CLUSTERING) {
        if (!isclusteringEnable()) {
          return { tab: RouteQueryTab.ORIGIN };
        }
      }

      if (tabValue === RouteQueryTab.GRAPH_ANALYSIS) {
        if (!isChartEnable()) {
          return { tab: RouteQueryTab.ORIGIN };
        }
      }
    }

    if (tabValue) {
      return { tab: tabValue };
    }

    return {};
  }

  onMounted() {
    this.setContentScroll();
  }

  destroy() {
    this.events.clear();
    document.querySelector(this.globalScrollSelector)?.removeEventListener('scroll', this.handleScroll);
    this.scrollEventAdded = false;
  }

  /**
   * 添加滚动监听
   */
  private setContentScroll() {
    if (!this.scrollEventAdded) {
      const target = document.querySelector(this.globalScrollSelector);
      if (target) {
        target.addEventListener('scroll', e => this.handleScroll(e));
        this.scrollEventAdded = true;
      }
    }
  }

  /**
   * 将值转换为可匹配的字符串
   * @param value 待转换的值
   * @returns 转换后的字符串或null
   */
  private convertToMatchableString(value: any): null | string {
    // 如果值为 null 或 undefined，返回 null
    if (value == null) {
      return null;
    }

    // 如果值为 Object（但不是 null），返回 null
    if (typeof value === 'object') {
      return null;
    }

    // 如果是 string, number, boolean，转换为 string
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }

    // 其他情况返回 null
    return null;
  }

  private handleScroll = (e: Event) => {
    this.fire(RetrieveEvent.GLOBAL_SCROLL, e);
  };
}

const isFavoriteShow = localStorage.getItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_SHOW) === 'true';
const isViewCurrentIndex = localStorage.getItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_VIEW_CURRENT_CHANGE) === 'true';
const favoriteWidth = Number(localStorage.getItem(STORAGE_KEY.STORAGE_KEY_FAVORITE_WIDTH) ?? 240);

export default new RetrieveHelper({ isFavoriteShow, favoriteWidth, isViewCurrentIndex });
