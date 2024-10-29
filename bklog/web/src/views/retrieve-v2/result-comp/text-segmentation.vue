<script setup>
  import { ref, watch, computed, nextTick, onMounted, onUnmounted } from 'vue';
  import UseJsonFormatter from '@/hooks/use-json-formatter';
  import UseStore from '@/hooks/use-store';
  import useTruncateText from '../../../hooks/use-truncate-text';

  const emit = defineEmits(['menu-click']);

  const props = defineProps({
    field: { type: Object, required: true },
    data: { type: Object },
    content: { type: [String, Number, Boolean], required: true },
  });

  const refContent = ref();
  const store = UseStore();
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
    font: '12px Arial, Helvetica, sans-serif',
    showAll: isLimitExpandView.value || showAll.value,
  }));

  const { truncatedText, showMore } = useTruncateText(textTruncateOption);

  watch(
    () => [props.content],
    () => {
      textTruncateOption.value.text = props.content;
    },
    {
      immediate: true,
    },
  );

  watch(
    () => [truncatedText.value],
    () => {
      nextTick(() => {
        instance.config.jsonValue = truncatedText.value;
        instance.destroy?.();
        instance.initStringAsValue();
      });
    },
  );

  const handleClickMore = () => {
    showAll.value = true;
  };

  onMounted(() => {
    const cellElement = refContent.value.parentElement.closest('.bklog-lazy-render-cell');
    const elementMaxWidth = cellElement.offsetWidth * 2.6;
    maxWidth.value = elementMaxWidth;
  });

  onUnmounted(() => {
    instance?.destroy?.();
  });
</script>
<template>
  <div
    ref="refContent"
    :class="['bklog-text-segment', 'bklog-root-field', { 'is-wrap-line': isWrap, 'is-inline': !isWrap }]"
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
      >{{ truncatedText }}</span
    >
    <template v-if="showMore">
      <span
        class="btn-more-action"
        @click="handleClickMore"
        >更多</span
      >
    </template>
  </div>
</template>
<style lang="scss">
  .bklog-text-segment {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 12px;
    white-space: pre-line;

    .btn-more-action {
      position: absolute;
      right: 0;
      bottom: 0;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }
    }

    &.is-inline {
      display: flex;
    }
  }
</style>
