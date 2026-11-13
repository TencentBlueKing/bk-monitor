import { ref, watch, type WatchSource } from 'vue';
import { Z_INDEX_LAYERS, zIndexManager } from './z-index-manager.js';

export type OverlayLayer = 'DROPDOWN' | 'DRAWER' | 'DIALOG';

/** Use the shared counter, including Tippy/SDK allocations. A layer is a floor,
 * never a fixed value: reopening and nested overlays must exceed older ones. */
export function allocateOverlayZIndex(layer: OverlayLayer = 'DIALOG'): number {
  const floor = Z_INDEX_LAYERS[layer];
  if (!zIndexManager) return floor;
  zIndexManager.nextZIndex(floor);
  return zIndexManager.nextZIndex();
}

/** Does not register Escape/outside handlers: visibility remains business-owned.
 * Vue stops the watcher with its component scope. Only closed -> open allocates. */
export function useOverlayZIndex(visible: WatchSource<boolean>, layer: OverlayLayer = 'DIALOG') {
  const zIndex = ref<number>(Z_INDEX_LAYERS[layer]);
  watch(visible, open => {
    if (open) zIndex.value = allocateOverlayZIndex(layer);
  }, { immediate: true, flush: 'sync' });
  return zIndex;
}
