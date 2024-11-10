import { debounce } from 'lodash';
import { onMounted, onUnmounted, ref } from 'vue';

export default (onLoadingCallbak, onScrollFn) => {
  const isRunning = ref(false);
  const debounceCallback = debounce(() => {
    if (!isRunning.value) {
      isRunning.value = true;
      onLoadingCallbak?.()?.then?.(() => {
        isRunning.value = false;
      });
    }
  }, 120);

  const debounceScrollFn = debounce((scrollTop) => {
    onScrollFn?.(scrollTop);
  })

  let lastPosition = 0;
  const handleScroll = (event: MouseEvent) => {
    const target = event.target as HTMLDivElement;
    const scrollDiff = target.scrollHeight - (target.scrollTop + target.offsetHeight);
    if (target.scrollTop > lastPosition && scrollDiff < 20) {
      debounceCallback(target.scrollTop);
    }

    debounceScrollFn(target.scrollTop);
    lastPosition = target.scrollTop;
  };

  const scrollToTop = () => {
    const target = document.body.querySelector('.search-result-content.scroll-y');
    if (target) {
      target.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
    }
  }

  onMounted(() => {
    const target = document.body.querySelector('.search-result-content.scroll-y');
    if (target) {
      target.addEventListener('scroll', handleScroll);
    }
  });

  onUnmounted(() => {
    const target = document.body.querySelector('.search-result-content.scroll-y');
    if (target) {
      target.removeEventListener('scroll', handleScroll);
    }
  });

  return { scrollToTop };
};
