import { onMounted, onUnmounted, ref } from 'vue';
import { debounce } from 'lodash';

export default ({ loadMoreFn, scrollCallbackFn }) => {
  const isRunning = ref(false);

  const getScrollElement = () => {
    return document.body.querySelector('.search-result-content.scroll-y');
  };

  const debounceCallback = debounce(() => {
    if (!isRunning.value) {
      isRunning.value = true;
      loadMoreFn?.()?.then?.(() => {
        isRunning.value = false;
      });
    }
  }, 120);

  const debounceScrollFn = debounce(scrollTop => {
    scrollCallbackFn?.(scrollTop);
  });

  let lastPosition = 0;
  const handleScrollEvent = (event: MouseEvent) => {
    const target = event.target as HTMLDivElement;
    const scrollDiff = target.scrollHeight - (target.scrollTop + target.offsetHeight);
    if (target.scrollTop > lastPosition && scrollDiff < 20) {
      debounceCallback(target.scrollTop);
    }

    debounceScrollFn(target.scrollTop);
    lastPosition = target.scrollTop;
  };

  const scrollToTop = () => {
    getScrollElement().scrollTo({ left: 0, top: 0, behavior: 'smooth' });
  };

  onMounted(() => {
    getScrollElement()?.addEventListener('scroll', handleScrollEvent);
  });

  onUnmounted(() => {
    getScrollElement()?.removeEventListener('scroll', handleScrollEvent);
  });

  return {
    scrollToTop,
  };
};
