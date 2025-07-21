<template>
  <div
    ref="lazyRenderCell"
    class="bklog-lazy-render-cell"
    :class="{
      'bklog-lazy-loading': !isVisible && delay,
      'is-intersecting': isIntersecting,
      'is-not-intersecting': !isIntersecting,
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
import { ref, computed, onBeforeUnmount } from 'vue';
import useIntersectionObserver from '@/hooks/use-intersection-observer';
import { isElement } from 'lodash';

const props = defineProps({
  delay: {
    type: Number,
    default: 0,
  },
  visibleOnly: {
    type: Boolean,
    default: false,
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
const localHeight = ref();
const isIntersecting = ref(false);

const cellStyle = computed(() => {
  return {
    minHeight: localHeight.value ?? props.minHeight,
  };
});

let resizeObserver = new ResizeObserver(() => {
  localHeight.value = `${lazyRenderCell.value?.firstElementChild?.offsetHeight ?? props.minHeight}px}`;
});

useIntersectionObserver(lazyRenderCell, entry => {
  if (entry.isIntersecting) {
    isVisible.value = true;
    if (lazyRenderCell.value?.firstElementChild && isElement(lazyRenderCell.value.firstElementChild)) {
      resizeObserver.observe(lazyRenderCell.value.firstElementChild);
    }
  } else {
    if (lazyRenderCell.value?.firstElementChild && isElement(lazyRenderCell.value.firstElementChild)) {
      resizeObserver.unobserve(lazyRenderCell.value.firstElementChild);
    }
    if (props.visibleOnly) {
      isVisible.value = false;
    }
  }
});

onBeforeUnmount(() => {
  resizeObserver.disconnect();
  resizeObserver = null;
});
</script>

<style>
  .bklog-lazy-render-cell {
    box-sizing: border-box;
    display: flex;
    align-items: flex-start;
    height: 100%;
    min-height: 40px;

    &.is-not-intersecting {
      opacity: 1;
      /* transition: opacity 1s; */
    }
  }

  .bklog-lazy-render-cell.bklog-lazy-loading::before {
    position: absolute;
    top: 50%;
    left: 42px;
    box-sizing: border-box;
    display: block;
    width: 12px;
    height: 12px;

    /* margin: 15px auto; */
    color: #f0f1f5;
    content: '';
    border-radius: 50%;
    transform: translateY(-50%);
    animation: lazyanimloader 4s linear infinite;
  }

  @keyframes lazyanimloader {
    0% {
      box-shadow:
        14px 0 0 -2px,
        38px 0 0 -2px,
        -14px 0 0 -2px,
        -38px 0 0 -2px;
    }

    25% {
      box-shadow:
        14px 0 0 -2px,
        38px 0 0 -2px,
        -14px 0 0 -2px,
        -38px 0 0 2px;
    }

    50% {
      box-shadow:
        14px 0 0 -2px,
        38px 0 0 -2px,
        -14px 0 0 2px,
        -38px 0 0 -2px;
    }

    75% {
      box-shadow:
        14px 0 0 2px,
        38px 0 0 -2px,
        -14px 0 0 -2px,
        -38px 0 0 -2px;
    }

    100% {
      box-shadow:
        14px 0 0 -2px,
        38px 0 0 2px,
        -14px 0 0 -2px,
        -38px 0 0 -2px;
    }
  }
</style>
