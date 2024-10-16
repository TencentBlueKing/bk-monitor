<template>
  <div
    ref="refJsonEditor"
    class="bklog-json-formatter"
  ></div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import useJsonFormatter from '../hooks/use-json-formatter';

  const props = defineProps({
    jsonValue: {
      type: Object,
      default: '{}',
    },
    fields: {
      type: Array,
      default: () => [],
    },
  });

  const refJsonEditor = ref<HTMLElement | null>();
  const formatCounter = ref(0);
  const { setValue } = useJsonFormatter({ target: refJsonEditor, fields: props.fields });
  const formatValue = computed(() => {
    const stringValue = props.jsonValue;
    formatCounter.value++;
    return {
      stringValue,
    };
  });

  watch(
    () => formatCounter.value,
    () => {
      setValue(formatValue.value.stringValue);
    },
    {
      immediate: true,
    },
  );
</script>
<style lang="scss">
  .bklog-json-formatter {
    .jsoneditor {
      &.jsoneditor-mode-view {
        .jsoneditor-expandable {
          &.jsoneditor-expanded {
            display: none;
          }
        }

        .jsoneditor-value {
          .segment-content {
            line-height: 20px;
            white-space: normal;
          }

          .menu-list {
            position: absolute;
            display: none;
          }

          .valid-text {
            cursor: pointer;

            &.focus-text,
            &:hover {
              color: #3a84ff;
            }
          }

          .null-item {
            display: inline-block;
            min-width: 6px;
          }
        }
      }
    }
  }
</style>
