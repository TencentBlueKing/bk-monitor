import { onMounted, onUnmounted } from 'vue';
import { throttle } from 'lodash';
import { getTargetElement } from './hooks-helper';

export default (target, callback: (e: MouseEvent) => void) => {
  const getScrollElement = () => {
    return getTargetElement(target);
  };

  const handleScrollEvent = throttle((event: MouseEvent) => {
    callback?.(event);
  });

  const scrollToTop = (smooth = true) => {
    getScrollElement().scrollTo({ left: 0, top: 0, behavior: smooth ? 'smooth' : 'instant' });
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
