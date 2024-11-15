import { onMounted, Ref, onUnmounted } from 'vue';
import { debounce } from 'lodash';

export default (target: Ref<HTMLElement>, callbackFn) => {
  const debounceCallback = debounce(entry => {
    callbackFn?.(entry);
  }, 120);

  let resizeObserver = null;
  const createResizeObserve = () => {
    const cellElement = target?.value;

    if (cellElement) {
      // 创建一个 ResizeObserver 实例
      resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
          // 获取元素的新高度
          debounceCallback(entry);
        }
      });

      resizeObserver?.observe(cellElement);
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
