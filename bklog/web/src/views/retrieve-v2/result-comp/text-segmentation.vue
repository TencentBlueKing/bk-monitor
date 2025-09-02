<script setup>
  import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';
  import UseJsonFormatter from '@/hooks/use-json-formatter';
  import useTruncateText from '@/hooks/use-truncate-text';
  import useIntersectionObserver from '@/hooks/use-intersection-observer';
  import { BK_LOG_STORAGE } from '../../../store/store.type';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { debounce } from 'lodash-es';

  const emit = defineEmits(['menu-click']);

  const props = defineProps({
    field: { type: Object, required: true },
    data: { type: Object },
    content: { type: [String, Number, Boolean], required: true },
  });

  const refContent = ref();
  const refFieldValue = ref();
  const store = useStore();
  const { $t } = useLocale();
  const isWrap = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_LINE_IS_WRAP]);
  const isLimitExpandView = computed(() => store.state.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW]);
  const showAll = ref(false);
  const maxWidth = ref(0);
  const isIntersecting = ref(false);
  const isSegmentTagInit = ref(false);

  const textTruncateOption = computed(() => ({
    fontSize: 12,
    text: props.content,
    maxWidth: maxWidth.value,
    font: '12px Menlo,Monaco,Consolas,Courier,"PingFang SC","Microsoft Yahei",monospace',
    showAll: isLimitExpandView.value || showAll.value,
  }));

  const { truncatedText, showMore } = useTruncateText(textTruncateOption);
  const handleMenuClick = event => {
    if (showMore.value && refFieldValue.value.querySelectorAll('.valid-text').length === 1) {
      event.option.value = props.content;
    }
    emit('menu-click', event);
  };

  const instance = new UseJsonFormatter({
    target: refContent,
    fields: [props.field],
    jsonValue: props.content,
    onSegmentClick: handleMenuClick,
  });

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

  const debounceSetSegmentTag = debounce(() => {
    if (!isIntersecting.value || (isSegmentTagInit.value && instance.config.jsonValue === renderText.value)) {
      return;
    }

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

  watch(
    () => [renderText.value],
    () => {
      nextTick(() => {
        debounceSetSegmentTag();
      });
    },
  );

  const getCellElement = () => {
    return refContent.value?.parentElement?.closest?.('.bklog-lazy-render-cell');
  };

  const debounceUpdateSegmentTag = debounce(() => {
    const cellElement = getCellElement();
    if (cellElement) {
      const elementMaxWidth = cellElement.offsetWidth * 3;
      maxWidth.value = elementMaxWidth;
      nextTick(() => debounceSetSegmentTag());
    }
  });

  const createResizeObserve = () => {
    const cellElement = getCellElement();
    const elementMaxWidth = cellElement.offsetWidth * 3;
    maxWidth.value = elementMaxWidth;

    // 创建一个 ResizeObserver 实例
    resizeObserver = new ResizeObserver(() => {
      // 获取元素的新高度
      debounceUpdateSegmentTag();
    });

    // 开始监听元素
    resizeObserver.observe(getCellElement());
  };

  useIntersectionObserver(refContent, entry => {
    isIntersecting.value = entry.isIntersecting;
    if (entry.isIntersecting) {
      // 进入可视区域重新计算宽度
      debounceUpdateSegmentTag();
    }
  });

  onMounted(() => {
    createResizeObserve();
    debounceUpdateSegmentTag();
  });

  onBeforeUnmount(() => {
    instance?.destroy?.();
    resizeObserver?.disconnect();
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
      ref="refFieldValue"
      :data-field-name="field.field_name"
      v-html="$xss(renderText)"
    ></span>
  </div>
</template>
<style lang="scss">
  .bklog-text-segment {
    max-height: 60px;
    overflow: hidden;
    font-size: 12px;
    white-space: pre-wrap;

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
      line-height: 22px;

      &.segment-content {
        span {
          font: var(--bklog-v3-row-ctx-font);
          white-space: pre-wrap;
        }

        .btn-more-action {
          position: absolute;
          right: 16px;
          bottom: 10px;
          padding-left: 18px;
          color: #3a84ff;
          cursor: pointer;
          background-color: #fff;

          &.show-all {
            &::before {
              position: absolute;
              top: 50%;
              left: 4px;
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
