<template>
  <div
    ref="lazyRenderCell"
    class="bklog-lazy-render-cell"
    :class="{ 'bklog-lazy-loading': !isVisible }"
    :style="cellStyle"
  >
    <div v-if="isVisible">
      <!-- 实际内容 -->
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
  import { ref, onMounted, onBeforeUnmount, computed } from 'vue';

  const props = defineProps({
    delay: {
      type: Number,
      default: 60,
    },
    visibleOnly: {
      type: Boolean,
      default: false,
    },
  });

  const lazyRenderCell = ref(null);
  const isVisible = ref(false);
  let observer = null;
  let visibilityTimeout = null;
  const cellWidth = ref('auto');
  const cellHeight = ref('auto');

  const setCellDimensions = () => {
    if (lazyRenderCell.value) {
      cellWidth.value = `${lazyRenderCell.value.offsetWidth}px`;
      cellHeight.value = `${lazyRenderCell.value.offsetHeight}px`;
    }
  };

  const cellStyle = computed(() => ({
    width: cellWidth.value,
    height: cellHeight.value,
  }));

  const createObserver = () => {
    observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            visibilityTimeout = setTimeout(() => {
              isVisible.value = true;
            }, props.delay);
          } else {
            if (props.visibleOnly) {
              if (visibilityTimeout) {
                clearTimeout(visibilityTimeout);
                visibilityTimeout = null;
              }
              setCellDimensions();
              isVisible.value = false;
            }
          }
        });
      },
      {
        root: null,
        threshold: 0.1,
      },
    );

    if (lazyRenderCell.value) {
      observer.observe(lazyRenderCell.value);
    }
  };

  const destroyObserver = () => {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  };

  onMounted(() => {
    createObserver();
  });

  onBeforeUnmount(() => {
    destroyObserver();
    if (visibilityTimeout) {
      clearTimeout(visibilityTimeout);
    }
  });
</script>

<style>
  .bklog-lazy-render-cell {
    position: relative;
    box-sizing: border-box;
    min-height: 62px;
    overflow: hidden;
  }

  .bklog-lazy-render-cell.bklog-lazy-loading::before {
    position: absolute;
    left: 42px;
    box-sizing: border-box;
    display: block;
    width: 12px;
    height: 12px;
    margin: 15px auto;
    color: #ddd;
    content: '';
    border-radius: 50%;
    animation: lazyanimloader 2s linear infinite;
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
