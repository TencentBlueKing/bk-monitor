import { type ShallowRef, onBeforeUnmount, shallowRef } from 'vue';

/** 首批同步渲染条数：覆盖一屏，点击 / 进入即到位 */
const PROGRESSIVE_FIRST_BATCH = 30;
/** 后续每帧补齐条数 */
const PROGRESSIVE_BATCH_SIZE = 100;

type ProgressiveRender = {
  /** 已提交渲染的条数，0 表示尚未开始 */
  limit: ShallowRef<number>;
  /** 是否仍在后台补齐，用于展示渲染中提示 */
  rendering: ShallowRef<boolean>;
  /** 重置到未渲染状态 */
  reset: () => void;
  /** 从首批开始渲染，minCount 用于保证某条（如搜索命中）一定进入本次渲染 */
  start: (minCount?: number) => void;
};

/**
 * 分片渐进渲染：先同步渲染首批，再按帧补齐剩余条数。
 * 用于把「一次性创建上千行」拆成多帧，避免长任务阻塞首帧与交互。
 */
export function useProgressiveRender(total: () => number): ProgressiveRender {
  const limit = shallowRef(0);
  const rendering = shallowRef(false);
  let timer: null | number = null;

  const stop = () => {
    if (timer !== null) {
      cancelAnimationFrame(timer);
      timer = null;
    }
    rendering.value = false;
  };

  const step = () => {
    timer = null;
    const max = Math.max(0, total());
    limit.value = Math.min(max, limit.value + PROGRESSIVE_BATCH_SIZE);
    if (limit.value < max) {
      rendering.value = true;
      timer = requestAnimationFrame(step);
      return;
    }
    rendering.value = false;
  };

  const start = (minCount = 0) => {
    stop();
    const max = Math.max(0, total());
    // 取已有与目标较大者，避免搜索定位等场景把已渲染的条数裁回去造成闪动
    limit.value = Math.min(max, Math.max(limit.value, PROGRESSIVE_FIRST_BATCH, minCount));
    if (limit.value < max) {
      rendering.value = true;
      timer = requestAnimationFrame(step);
    }
  };

  const reset = () => {
    stop();
    limit.value = 0;
  };

  onBeforeUnmount(stop);

  return { limit, rendering, reset, start };
}
