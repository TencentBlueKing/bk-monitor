<template>
  <div
    ref="lazyRenderCell"
    class="bklog-lazy-render-cell"
    :class="{
      'is-intersecting': isVisible,
      'is-not-intersecting': !isVisible,
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
  import { ref, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue';
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
    // 用于监听触发强制计算高度
    forceCounter: {
      type: Number,
      default: 0,
    },
    minHeight: {
      type: String,
      default: '40px',
    },
    root: {
      type: HTMLDivElement,
      default: null,
    },
  });

  const lazyRenderCell = ref(null);
  const isVisible = ref(false);
  let observer = null;
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

  useMutationObserver(lazyRenderCell, () => {
    nextTick(() => {
      updateCell();
    });
  });

  onMounted(() => {
    lazyTaskManager.addTask(props.index, (isInBuffer, dir) => {
      console.log('isInBuffer, dir', isInBuffer, dir)
      if (dir === 'up') {
        isVisible.value = isInBuffer;
      } else {
        if (isInBuffer) {
          isVisible.value = isInBuffer;
        }
      }

      if (isInBuffer) {
        updateCell();
      }
    });

    lazyTaskManager.observeElement(lazyRenderCell.value, props.index);
  });

  onBeforeUnmount(() => {
    lazyTaskManager.removeTask(props.index);
    lazyTaskManager.unobserveElement(lazyRenderCell.value);
  });

  watch(
    () => [props.forceCounter],
    () => {
      updateCell();
    },
  );
</script>

<style>
  .bklog-lazy-render-cell {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    height: 100%;
    min-height: 40px;
  }
</style>
