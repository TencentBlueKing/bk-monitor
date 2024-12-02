import { onMounted, Ref, onUnmounted } from 'vue';
import { debounce } from 'lodash';

export default (target: Ref<HTMLElement>, callbackFn, options?) => {
  const debounceCallback = debounce(() => {
    callbackFn?.();
  }, 120);

  let resizeObserver = null;
  const createResizeObserve = () => {
    const cellElement = target?.value;

    if (cellElement) {
      // 创建一个 ResizeObserver 实例
      resizeObserver = new MutationObserver(() => {
        debounceCallback();
      });

      resizeObserver?.observe(cellElement, { subtree: true, childList: true, attributes: false, ...(options ?? {}) });
    }
  };

  onMounted(() => {
    createResizeObserve();
  });

  onUnmounted(() => {
    const cellElement = target?.value;

    if (cellElement) {
      resizeObserver?.unobserve(cellElement);
      resizeObserver?.disconnect();
      resizeObserver = null;
    }
  });
};
