<script setup>
  import { ref, watch, computed, nextTick, onMounted, onUnmounted } from 'vue';
  import UseJsonFormatter from '@/hooks/use-json-formatter';
  import useTruncateText from '@/hooks/use-truncate-text';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  const emit = defineEmits(['menu-click']);

  const props = defineProps({
    field: { type: Object, required: true },
    data: { type: Object },
    content: { type: [String, Number, Boolean], required: true },
  });

  const refContent = ref();
  const store = useStore();
  const { $t } = useLocale();
  const isWrap = computed(() => store.state.tableLineIsWrap);
  const isLimitExpandView = computed(() => store.state.isLimitExpandView);
  const showAll = ref(false);
  const maxWidth = ref(0);

  const handleMenuClick = event => {
    emit('menu-click', event);
  };

  const instance = new UseJsonFormatter({
    target: refContent,
    fields: [props.field],
    jsonValue: props.content,
    onSegmentClick: handleMenuClick,
  });

  const textTruncateOption = computed(() => ({
    fontSize: 12,
    text: props.content,
    maxWidth: maxWidth.value,
    font: '12px Menlo,Monaco,Consolas,Courier,"PingFang SC","Microsoft Yahei",monospace',
    showAll: isLimitExpandView.value || showAll.value,
  }));

  const { truncatedText, showMore } = useTruncateText(textTruncateOption);
  const renderText = computed(() => {
    if (showAll.value || isLimitExpandView.value) {
      return props.content;
    }

    return truncatedText.value;
  });

  const btnText = computed(() => {
    if (showAll.value) {
      return $t('收起');
    }

    return $t('更多');
  });

  let resizeObserver = null;

  watch(
    () => [props.content],
    () => {
      textTruncateOption.value.text = props.content;
    },
    {
      immediate: true,
    },
  );

  const handleClickMore = e => {
    e.stopPropagation();
    e.preventDefault();
    e.stopImmediatePropagation();

    showAll.value = !showAll.value;
  };
  watch(
    () => [renderText.value],
    () => {
      nextTick(() => {
        instance.config.jsonValue = renderText.value;
        instance.destroy?.();

        const appendText =
          showMore.value && !isLimitExpandView.value
            ? {
                text: btnText.value,
                onClick: handleClickMore,
                attributes: {
                  class: `btn-more-action ${!showAll.value ? 'show-all' : ''}`,
                },
              }
            : undefined;
        instance.initStringAsValue(renderText.value, appendText);
      });
    },
    { immediate: true },
  );

  onMounted(() => {
    const cellElement = refContent.value.parentElement.closest('.bklog-lazy-render-cell');
    const offsetWidth = cellElement.offsetWidth;
    const elementMaxWidth = cellElement.offsetWidth * 3;
    maxWidth.value = elementMaxWidth;

    // 创建一个 ResizeObserver 实例
    resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        // 获取元素的新高度
        const newWidth = entry.contentRect.width * 3;

        if (newWidth !== maxWidth.value) {
          maxWidth.value = newWidth;
        }
      }
    });

    // 开始监听元素
    resizeObserver.observe(cellElement);
  });

  onUnmounted(() => {
    instance?.destroy?.();
    resizeObserver.disconnect();
    resizeObserver = null;
  });
</script>
<template>
  <div
    ref="refContent"
    :class="[
      'bklog-text-segment',
      'bklog-root-field',
      { 'is-wrap-line': isWrap, 'is-inline': !isWrap, 'is-show-long': isLimitExpandView, 'is-expand-all': showAll },
    ]"
  >
    <span
      class="field-name"
      style="display: none"
      ><span
        class="black-mark"
        :data-field-name="field.field_name"
      >
        {{ field.field_name }}
      </span></span
    >
    <span
      class="field-value"
      :data-field-name="field.field_name"
      >{{ renderText }}</span
    >
  </div>
</template>
<style lang="scss">
  .bklog-text-segment {
    max-height: 60px;
    overflow: hidden;
    font-size: 12px;
    white-space: pre-line;

    &.is-expand-all {
      max-height: max-content;
    }

    &.is-show-long {
      max-height: max-content;

      .btn-more-action {
        display: none;
      }
    }

    span {
      &.segment-content {
        span {
          font-size: 12px;
        }

        .btn-more-action {
          position: absolute;
          right: 16px;
          bottom: 10px;
          padding-left: 22px;
          color: #3a84ff;
          cursor: pointer;
          background-color: #fff;

          &.show-all {
            &::before {
              position: absolute;
              top: 50%;
              left: 0;
              content: '...';
              transform: translateY(-50%);
            }
          }
        }
      }
    }

    &.is-inline {
      display: flex;
    }
  }

  .bk-table-row {
    &.hover-row {
      .bklog-text-segment {
        .btn-more-action {
          background-color: #f5f7fa;
        }
      }
    }
  }
</style>
