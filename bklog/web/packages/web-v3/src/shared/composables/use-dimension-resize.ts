/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { onScopeDispose, reactive, toRefs } from 'vue';
type DragType = 'dragX' | 'dragY';
/** Preserve the editor's axis-specific clamping and stop-at-minimum behavior. */
export function useDimensionResize() {
  const state = reactive({
    isChanging: false,
    currentBoxHeight: null as number | null,
    collectMinHeight: 160,
    collectMaxHeight: 600,
    collectHeight: 160,
    currentBoxWidth: null as number | null,
    collectMinWidth: 160,
    collectMaxWidth: 600,
    collectWidth: 160,
    currentScreenY: null as number | null,
    currentScreenX: null as number | null,
    currentDragType: 'dragX' as DragType,
  });
  function removeListeners() {
    window.removeEventListener('mousemove', dragMoving);
    window.removeEventListener('mouseup', dragStop);
  }
  function dragBegin(event: MouseEvent, type: DragType = 'dragX') {
    event.stopPropagation();
    state.currentDragType = type;
    state.isChanging = true;
    state.currentBoxHeight = state.collectHeight;
    state.currentBoxWidth = state.collectWidth;
    if (type === 'dragX') state.currentScreenX = event.screenX;
    if (type === 'dragY') state.currentScreenY = event.screenY;
    window.addEventListener('mousemove', dragMoving, { passive: true });
    window.addEventListener('mouseup', dragStop, { passive: true });
  }
  function dragMoving(event: MouseEvent) {
    if (state.currentDragType === 'dragX' && state.currentBoxWidth !== null && state.currentScreenX !== null) {
      const width = state.currentBoxWidth + event.screenX - state.currentScreenX;
      if (width < state.collectMinWidth) {
        state.collectWidth = state.collectMinWidth;
        dragStop();
      } else if (width >= state.collectMaxWidth) state.collectWidth = state.collectMaxWidth;
      else state.collectWidth = width;
    }
    if (state.currentDragType === 'dragY' && state.currentBoxHeight !== null && state.currentScreenY !== null) {
      const height = state.currentBoxHeight + event.screenY - state.currentScreenY;
      if (height < state.collectMinHeight) {
        state.collectHeight = state.collectMinHeight;
        dragStop();
      } else if (height >= state.collectMaxHeight) state.collectHeight = state.collectMaxHeight;
      else state.collectHeight = height;
    }
  }
  function dragStop() {
    state.isChanging = false;
    state.currentBoxHeight = null;
    state.currentScreenY = null;
    state.currentBoxWidth = null;
    state.currentScreenX = null;
    removeListeners();
  }
  onScopeDispose(removeListeners);
  return { ...toRefs(state), dragBegin, dragMoving, dragStop };
}
