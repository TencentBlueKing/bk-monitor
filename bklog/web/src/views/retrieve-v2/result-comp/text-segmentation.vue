<script setup>
  import { ref, watch, computed } from 'vue';
  import UseJsonFormatter from '@/hooks/use-json-formatter';
  import UseStore from '@/hooks/use-store';

  const emit = defineEmits(['menu-click']);

  const props = defineProps({
    field: { type: Object, required: true },
    data: { type: Object },
    content: { type: [String, Number, Boolean], required: true },
  });

  const refContent = ref();
  const store = UseStore();
  const isWrap = computed(() => store.state.tableLineIsWarp);
  const handleMenuClick = event => {
    emit('menu-click', event);
  };

  const instance = new UseJsonFormatter({
    target: refContent,
    fields: [props.field],
    jsonValue: props.content,
    onSegmentClick: handleMenuClick,
  });

  watch(
    () => [props.content],
    () => {
      setTimeout(() => {
        instance.initStringAsValue();
      });
    },
    {
      immediate: true,
    },
  );
</script>
<template>
  <div
    ref="refContent"
    :class="['bklog-text-segment', 'bklog-root-field', { 'is-wrap-line': isWrap, 'is-inline': !isWrap }]"
  >
    <span
      class="field-name black-mark"
      style="display: none"
      >{{ field.field_name }}</span
    >
    <span class="field-value">{{ content }}</span>
  </div>
</template>
<style lang="scss">
  .bklog-text-segment {
    &.is-inline {
      display: flex;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
</style>
