<template>
  <div
    ref="lazyRenderCell"
    class="bklog-lazy-render-cell"
    :class="{
      'bklog-lazy-loading': !isVisible && delay,
      'is-intersecting': isIntersecting,
      'is-not-intersecting': !isIntersecting,
      'has-overflow-x': hasOverflowX,
    }"
    :style="cellStyle"
  >
    <template v-if="isVisible || !delay">
      <!-- 实际内容 -->
      <slot></slot>
    </template>
  </div>
</template>

<script setup>
  import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';
  import useIntersectionObserver from '@/hooks/use-intersection-observer';
  import useMutationObserver from '@/hooks/use-mutation-observer';
  import lazyTaskManager from './utils/lazy-task-manager';

  const props = defineProps({
    delay: {
      type: Number,
      default: 1,
    },
    visibleOnly: {
      type: Boolean,
      default: true,
    },
    root: {
      type: HTMLDivElement,
      default: null,
    },
    index: {
      type: Number,
      default: 0,
    },
  });

  const lazyRenderCell = ref(null);
  const isVisible = ref(false);
  let observer = null;
  const isIntersecting = ref(false);
  const localHeight = ref(0);
  const hasOverflowX = ref(false);

  const cellStyle = computed(() => {
    return {
      minHeight: `${localHeight.value}px`,
    };
  });

  const getChildNode = () => {
    return lazyRenderCell.value?.childNodes?.[0];
  };

  const updateCell = () => {
    const child = getChildNode();
    if (child) {
      localHeight.value = child?.offsetHeight ?? 42;
      hasOverflowX.value = child.scrollWidth > child.offsetWidth;
    }
  };

  useIntersectionObserver(lazyRenderCell, entry => {
    lazyTaskManager.updateVisibleIndexes(props.index, entry.isIntersecting);
  });

  useMutationObserver(lazyRenderCell, () => {
    nextTick(() => {
      updateCell();
    });
  });

  onMounted(() => {
    lazyTaskManager.addTask(props.index, isInBuffer => {
      isVisible.value = isInBuffer;
      if (isInBuffer) {
        updateCell();
      }
    });
  });

  onBeforeUnmount(() => {
    lazyTaskManager.removeTask(props.index);
  });
</script>

<style>
  .bklog-lazy-render-cell {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    min-height: 40px;

    &.is-not-intersecting {
      opacity: 1;
      transition: opacity 1s;
    }
  }
</style>
