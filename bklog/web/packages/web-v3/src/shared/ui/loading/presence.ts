import { onScopeDispose, ref, watch, type Ref } from 'vue';

/** Visual lifetime only. Business readiness and request state never wait for this clock. */
export const SKELETON_EXIT_MS = 180;
export const skeletonExitDuration = () =>
  typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : SKELETON_EXIT_MS;

export function createSkeletonPresence(publish: (visible: boolean, leaving: boolean) => void,
  duration = skeletonExitDuration, schedule = setTimeout, cancel = clearTimeout) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let visible = false;
  let disposed = false;
  const clear = () => { if (timer !== undefined) cancel(timer); timer = undefined; };
  return {
    update(pending: boolean) {
      if (disposed) return;
      clear();
      if (pending) { visible = true; publish(true, false); return; }
      const ms = duration();
      if (!visible || !ms) { visible = false; publish(false, false); return; }
      publish(true, true);
      timer = schedule(() => { timer = undefined; visible = false; publish(false, false); }, ms);
    },
    dispose() { disposed = true; clear(); },
  };
}

export function useSkeletonPresence(pending: Readonly<Ref<boolean>>) {
  const visible = ref(false), leaving = ref(false);
  const controller = createSkeletonPresence((shown, exiting) => { visible.value = shown; leaving.value = exiting; });
  watch(pending, value => controller.update(value), { immediate: true, flush: 'sync' });
  onScopeDispose(controller.dispose);
  return { visible, leaving };
}

/** HTML boot layer has no Vue owner. Reuse the same visual clock and cleanup policy. */
export function dissolveSkeleton(element: HTMLElement, complete: () => void) {
  element.style.pointerEvents = 'none';
  const ms = skeletonExitDuration();
  if (!ms) { complete(); return () => {}; }
  element.style.transition = `opacity ${ms}ms ease-out`;
  element.style.opacity = '0';
  const timer = setTimeout(complete, ms);
  return () => clearTimeout(timer);
}
