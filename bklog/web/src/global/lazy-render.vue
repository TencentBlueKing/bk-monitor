<template>
  <div
    ref="lazyRenderCell"
    class="bklog-lazy-render-cell"
    :class="{ 'bklog-lazy-loading': !isVisible, 'is-intersecting': isIntersecting }"
  >
    <template v-if="isVisible">
      <!-- 实际内容 -->
      <slot></slot>
    </template>
  </div>
</template>

<script setup>
  import { ref, onMounted, onBeforeUnmount, computed, nextTick } from 'vue';

  const props = defineProps({
    delay: {
      type: Number,
      default: 0,
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
  // const cellWidth = ref('auto');
  // const cellHeight = ref('auto');
  const isIntersecting = ref(false);

  // const setCellDimensions = () => {
  //   if (lazyRenderCell.value) {
  //     cellWidth.value = `${lazyRenderCell.value.offsetWidth}px`;
  //     cellHeight.value = `${lazyRenderCell.value.offsetHeight}px`;
  //   }
  // };

  // const cellStyle = computed(() => {
  //   if (props.visibleOnly) {
  //     return {
  //       width: cellWidth.value,
  //       height: cellHeight.value,
  //     };
  //   }

  //   return {};
  // });

  const destroyObserver = () => {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  };

  const createObserver = () => {
    observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          isIntersecting.value = entry.isIntersecting;
          if (entry.isIntersecting) {
            setTimeout(() => {
              isVisible.value = true;
            });
          } else {
            if (props.visibleOnly) {
              // if (visibilityTimeout) {
              //   cancelAnimationFrame(visibilityTimeout);
              //   visibilityTimeout = null;
              // }
              // setCellDimensions();
              isVisible.value = false;
              return;
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
    box-sizing: border-box;
    display: flex;
    align-items: center;

    /* min-height: 40px; */

    /* visibility: hidden; */

    /*
    &.is-intersecting {
      visibility: visible;
    } */
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
    color: #ddd;
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
