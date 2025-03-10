// 滚动条查询条件
const GLOBAL_SCROLL_SELECTOR = '.retrieve-v2-index.scroll-y';

export enum STORAGE_KEY {
  STORAGE_KEY_FAVORITE_WIDTH = 'STORAGE_KEY_FAVORITE_WIDTH',
  STORAGE_KEY_FAVORITE_SHOW = 'STORAGE_KEY_FAVORITE_SHOW',
}

export enum RetrieveEvent {
  // 搜索栏高度变化
  SEARCHBAR_HEIGHT_CHANGE = 'searchbar-height-change',
  // 左侧字段设置宽度变化
  LEFT_FIELD_SETTING_WIDTH_CHANGE = 'left-field-setting-width-change',
  // 收藏栏宽度变化
  FAVORITE_WIDTH_CHANGE = 'favorite-width-change',

  // 收藏栏是否展示
  FAVORITE_SHOWN_CHANGE = 'favorite-shown-change',
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

  // 事件列表
  events: Map<string, ((...args) => void)[]>;

  constructor({ isFavoriteShow = false, favoriteWidth = 0 }) {
    this.globalScrollSelector = GLOBAL_SCROLL_SELECTOR;
    this.isFavoriteShown = isFavoriteShow;
    this.favoriteWidth = favoriteWidth;
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
