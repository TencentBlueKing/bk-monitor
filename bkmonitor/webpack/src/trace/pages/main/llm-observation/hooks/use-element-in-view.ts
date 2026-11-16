import { type ShallowRef, onBeforeUnmount, onMounted, shallowRef } from 'vue';

/** 视口外预渲染边距：提前一屏挂载重组件，减少快速滚动时简化态到完整态的切换感 */
const DEFAULT_ROOT_MARGIN = '600px 0px';

/**
 * 元素是否已接近 / 进入视口，用于把行内重组件（KV 测量、Popover 实例）延迟到接近可见时再挂载。
 * 一旦可见即常驻 true，不随元素滚出视口回退，避免重组件反复挂载卸载。
 * `enabled` 为 false 时恒为 true，调用方无需拆分渲染分支。
 */
export function useElementInView(target: ShallowRef<HTMLElement | undefined>, enabled = true) {
  const inView = shallowRef(!enabled);
  let observer: IntersectionObserver | null = null;

  const disconnect = () => {
    observer?.disconnect();
    observer = null;
  };

  onMounted(() => {
    if (!enabled) return;
    const el = target.value;
    if (!el) return;
    // IntersectionObserver 首次回调在下一帧，首屏可见元素先同步判定，避免完整预览延迟一帧出现
    if (isWithinMargin(el, DEFAULT_ROOT_MARGIN)) {
      inView.value = true;
      return;
    }
    observer = new IntersectionObserver(
      entries => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            inView.value = true;
            disconnect();
            return;
          }
        }
      },
      { rootMargin: DEFAULT_ROOT_MARGIN }
    );
    observer.observe(el);
  });

  onBeforeUnmount(disconnect);

  return { inView };
}

/** 按 rootMargin 的上下左右边距做一次同步命中判断 */
function isWithinMargin(el: HTMLElement, rootMargin: string) {
  const [top = 0, right = 0, bottom = 0, left = 0] = rootMargin
    .split(/\s+/)
    .map(value => Number.parseFloat(value) || 0);
  const rect = el.getBoundingClientRect();
  // 元素尚未参与布局（如被 content-visibility 跳过的屏外行）时矩形全为 0，
  // 直接按边距比较会误判为「在视口内」，此时交给 IntersectionObserver 判定
  if (!rect.width && !rect.height) return false;
  const viewWidth = document.documentElement.clientWidth;
  const viewHeight = document.documentElement.clientHeight;
  return (
    rect.bottom + bottom >= 0 &&
    rect.top - top <= viewHeight &&
    rect.right + right >= 0 &&
    rect.left - left <= viewWidth
  );
}
