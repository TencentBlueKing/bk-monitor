export type LzayCacheItem = {
  // 当前行是否展开
  expand: boolean;

  // 当前行是否在可视区域或者在预渲染区域
  isInSection: boolean;

  // 当前行最小高度
  minHeight: string;
}
class LazyLogRowCache {
  lazyCache: Map<string, LzayCacheItem>;
  constructor() {}
  destroy() {}
}