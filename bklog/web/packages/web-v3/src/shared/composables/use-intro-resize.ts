/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { onScopeDispose, ref } from 'vue';
import useStore from './use-store';
/** V2's right-hand introduction pane: dragging left expands the pane. */
export function useIntroResize(initialWidth = 400) {
  const store = useStore();
  const minIntroWidth = ref(300);
  const maxIntroWidth = ref(480);
  const introWidth = ref(initialWidth);
  const isDraging = ref(false);
  const currentTreeBoxWidth = ref<number | null>(null);
  const currentScreenX = ref<number | null>(null);
  function removeListeners() {
    window.removeEventListener('mousemove', dragMoving);
    window.removeEventListener('mouseup', dragStop);
  }
  function dragBegin(event: MouseEvent) {
    currentTreeBoxWidth.value = introWidth.value;
    currentScreenX.value = event.screenX;
    window.addEventListener('mousemove', dragMoving, { passive: true });
    window.addEventListener('mouseup', dragStop, { passive: true });
  }
  function dragMoving(event: MouseEvent) {
    if (currentTreeBoxWidth.value === null || currentScreenX.value === null) return;
    isDraging.value = true;
    const width = currentTreeBoxWidth.value - event.screenX + currentScreenX.value;
    introWidth.value =
      width < minIntroWidth.value ? minIntroWidth.value : width >= maxIntroWidth.value ? maxIntroWidth.value : width;
  }
  function dragStop() {
    isDraging.value = false;
    currentTreeBoxWidth.value = null;
    currentScreenX.value = null;
    removeListeners();
    store.commit('updateChartSize');
  }
  onScopeDispose(removeListeners);
  return {
    minIntroWidth,
    maxIntroWidth,
    introWidth,
    isDraging,
    currentTreeBoxWidth,
    currentScreenX,
    dragBegin,
    dragMoving,
    dragStop,
  };
}
