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

import { random } from '../common/util';

// 滚动条查询条件
const GLOBAL_SCROLL_SELECTOR = '.retrieve-v2-index.scroll-y';

export enum STORAGE_KEY {
  STORAGE_KEY_FAVORITE_SHOW = 'STORAGE_KEY_FAVORITE_SHOW',
  STORAGE_KEY_FAVORITE_WIDTH = 'STORAGE_KEY_FAVORITE_WIDTH',
}

export enum RetrieveEvent {
  // 展示收藏内容
  FAVORITE_ACTIVE_CHANGE = 'favorite-active-change',
  // 收藏栏是否展示
  FAVORITE_SHOWN_CHANGE = 'favorite-shown-change',

  // 收藏栏宽度变化
  FAVORITE_WIDTH_CHANGE = 'favorite-width-change',

  // 左侧字段设置宽度变化
  LEFT_FIELD_SETTING_WIDTH_CHANGE = 'left-field-setting-width-change',

  // 搜索栏高度变化
  SEARCHBAR_HEIGHT_CHANGE = 'searchbar-height-change',

  // 趋势图高度变化
  TREND_GRAPH_HEIGHT_CHANGE = 'trend-graph-height-change',
}

class RetrieveHelper {
  // 滚动条查询条件
  globalScrollSelector: string;

  // 搜索栏高度
  searchBarHeight: number;

  // 左侧字段设置宽度
  leftFieldSettingWidth: number;

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

  constructor({ isFavoriteShow = false, favoriteWidth = 0 }) {
    this.globalScrollSelector = GLOBAL_SCROLL_SELECTOR;
    this.isFavoriteShown = isFavoriteShow;
    this.favoriteWidth = favoriteWidth;
    this.randomTrendGraphClassName = `random-${random(12)}`;
    this.events = new Map();
  }

  on(fnName: RetrieveEvent, callbackFn: (...args) => void) {
    if (this.events.has(fnName)) {
      if (!this.events.get(fnName).includes(callbackFn)) {
        this.events.get(fnName)?.push(callbackFn);
      }
      return;
    }

    this.events.set(fnName, [callbackFn]);
    return this;
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

  getScrollSelector() {
    return this.globalScrollSelector;
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

  destroy() {
    this.events.clear();
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
