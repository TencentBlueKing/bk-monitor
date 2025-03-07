// 滚动条查询条件
const GLOBAL_SCROLL_SELECTOR = '.retrieve-v2-index.scroll-y';

class RetrieveHelper {
  globalScrollSelector: string;
  constructor() {
    this.globalScrollSelector = GLOBAL_SCROLL_SELECTOR;
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
}

export default new RetrieveHelper();
