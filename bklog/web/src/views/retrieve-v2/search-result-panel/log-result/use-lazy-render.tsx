import { onMounted, onUnmounted, ref } from 'vue';
import { throttle } from 'lodash';
import { GLOBAL_SCROLL_SELECTOR } from './log-row-attributes';

export default ({ loadMoreFn, scrollCallbackFn }) => {
  const isRunning = ref(false);

  const getScrollElement = () => {
    return document.body.querySelector(GLOBAL_SCROLL_SELECTOR);
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
    const target = event.target as HTMLDivElement;
    const scrollDiff = target.scrollHeight - (target.scrollTop + target.offsetHeight);
    if (target.scrollTop > lastPosition && scrollDiff < 20) {
      debounceCallback();
    }

    scrollCallbackFn?.(target.scrollTop);
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
  });

  onUnmounted(() => {
    getScrollElement()?.removeEventListener('scroll', handleScrollEvent);
  });

  return {
    scrollToTop,
    hasScrollX,
  };
};
