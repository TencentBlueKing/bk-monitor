import { onMounted, onUnmounted, ref } from 'vue';
import { throttle, debounce } from 'lodash';
import { random } from '../common/util';
// 滚动条查询条件
const GLOBAL_SCROLL_SELECTOR = '.retrieve-v2-index.scroll-y';
const SEARCH_BAR_SELECTOR = '.search-bar-container';

export default ({ loadMoreFn, scrollCallbackFn }) => {
  const isRunning = ref(false);
  const searchBarHeight = ref(0);
  let scrollElementOffset = 0;
  let isComputingCalcOffset = false;

  const containerId = ref(`container_${random(8)}`);
  const container = `#${containerId.value}`;

  const getScrollElement = () => {
    return document.body.querySelector(GLOBAL_SCROLL_SELECTOR);
  };

  const debounceStopComputing = debounce(() => {
    isComputingCalcOffset = false;
  }, 500);

  const calculateOffsetTop = () => {
    if (!isComputingCalcOffset) {
      isComputingCalcOffset = true;
      let currentElement = document.querySelector(container) as HTMLElement;
      const relativeTo = getScrollElement();
      let offsetTop = 0;
      while (currentElement && currentElement !== relativeTo) {
        offsetTop += currentElement.offsetTop;
        currentElement = currentElement.offsetParent as HTMLElement;
      }
      scrollElementOffset = offsetTop;
      searchBarHeight.value = (document.querySelector(SEARCH_BAR_SELECTOR) as HTMLElement)?.offsetHeight ?? 0;
      debounceStopComputing();
    }
  };

  const debounceCallback = () => {
    if (!isRunning.value) {
      isRunning.value = true;
      loadMoreFn?.()?.then?.(() => {
        isRunning.value = false;
      });
    }
  };

  let lastPosition = 0;
  const handleScrollEvent = throttle((event: MouseEvent) => {
    calculateOffsetTop();
    const target = event.target as HTMLDivElement;
    const scrollDiff = target.scrollHeight - (target.scrollTop + target.offsetHeight);
    if (target.scrollTop > lastPosition && scrollDiff < 20) {
      debounceCallback();
    }

    scrollCallbackFn?.(target.scrollTop, scrollElementOffset);
    lastPosition = target.scrollTop;
  });

  const scrollToTop = () => {
    getScrollElement().scrollTo({ left: 0, top: 0, behavior: 'smooth' });
  };

  const hasScrollX = () => {
    const target = getScrollElement() as HTMLDivElement;
    return target.scrollWidth > target.offsetWidth;
  };

  onMounted(() => {
    getScrollElement()?.addEventListener('scroll', handleScrollEvent);
    calculateOffsetTop();
  });

  onUnmounted(() => {
    getScrollElement()?.removeEventListener('scroll', handleScrollEvent);
  });

  return {
    scrollToTop,
    hasScrollX,
    searchBarHeight,
    containerId,
  };
};
