// 滚动条查询条件
const GLOBAL_SCROLL_SELECTOR = '.retrieve-v2-index.scroll-y';
export enum RetrieveEvent {
  SEARCHBAR_HEIGHT_CHANGE = 'searchbar-height-change',
  LEFT_FIELD_SETTING_WIDTH_CHANGE = 'left-field-setting-width-change',
}

class RetrieveHelper {
  // 滚动条查询条件
  globalScrollSelector: string;

  // 搜索栏高度
  seachBarHeight: number;

  // 左侧字段设置宽度
  leftFieldSettingWidth: number;

  // 事件列表
  events: Map<string, { fn: (...args) => void }[]>;

  constructor() {
    this.globalScrollSelector = GLOBAL_SCROLL_SELECTOR;
    this.events = new Map();
  }

  on(fnName: RetrieveEvent, callbackFn: (...args) => void) {
    if (this.events.has(fnName)) {
      this.events.get(fnName)?.push({ fn: callbackFn });
      return;
    }

    this.events.set(fnName, [{ fn: callbackFn }]);
  }

  setSearchBarHeight(height: number) {
    this.seachBarHeight = height;
    this.events.get(RetrieveEvent.SEARCHBAR_HEIGHT_CHANGE)?.forEach(item => item?.fn?.(height));
  }

  setLeftFieldSettingWidth(width: number) {
    this.leftFieldSettingWidth = width;
    this.events.get(RetrieveEvent.LEFT_FIELD_SETTING_WIDTH_CHANGE)?.forEach(item => item?.fn?.(width));
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

  off(event: RetrieveEvent) {
    this.events.delete(event);
  }

  destroy() {
    this.events.clear();
  }
}

export default new RetrieveHelper();
