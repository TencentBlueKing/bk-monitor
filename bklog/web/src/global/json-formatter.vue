<template>
  <div
    :class="['bklog-json-formatter-root', { 'is-wrap-line': isWrap, 'is-inline': !isWrap, 'is-json': formatJson }]"
    ref="refJsonFormatterCell"
  >
    <template v-for="item in rootList">
      <span
        :key="item.name"
        class="bklog-root-field"
      >
        <span class="field-name"
          ><span
            class="black-mark"
            :data-field-name="item.name"
            >{{ getFieldName(item.name) }}</span
          ></span
        >
        <span
          class="field-value"
          :data-field-name="item.name"
          :ref="item.formatter.ref"
        ></span>
      </span>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch, onBeforeUnmount } from 'vue';
  import useJsonRoot from '../hooks/use-json-root';
  import useStore from '../hooks/use-store';
  //@ts-ignore
  import { parseTableRowData } from '@/common/util';
  import useFieldNameHook from '@/hooks/use-field-name';
  const emit = defineEmits(['menu-click']);
  const store = useStore();

  const props = defineProps({
    jsonValue: {
      type: [Object, String],
      default: () => ({}),
    },
    fields: {
      type: [Array, Object],
      default: () => [],
    },
    formatJson: {
      type: Boolean,
      default: true,
    },
  });

  const formatCounter = ref(0);
  const refJsonFormatterCell = ref();

  const isWrap = computed(() => store.state.tableLineIsWrap);
  const fieldList = computed(() => {
    if (Array.isArray(props.fields)) {
      return props.fields;
    }

    return [props.fields];
  });

  const onSegmentClick = args => {
    emit('menu-click', args);
  };
  const { updateRootFieldOperator, setExpand, setEditor, destroy } = useJsonRoot({
    fields: fieldList.value,
    onSegmentClick,
  });

  const convertToObject = val => {
    if (typeof val === 'string' && props.formatJson) {
      // const originValue = val.replace(/<\/?mark>/gim, '');
      if (/^(\{|\[)/.test(val)) {
        try {
          return JSON.parse(val);
        } catch (e) {
          return val;
        }
      }
    }

    return val;
  };

  const getFieldValue = field => {
    if (props.formatJson) {
      if (typeof props.jsonValue === 'string') {
        return convertToObject(props.jsonValue);
      }

      return convertToObject(parseTableRowData(props.jsonValue, field.field_name));
    }

    return typeof props.jsonValue === 'object' ? parseTableRowData(props.jsonValue, field.field_name) : props.jsonValue;
  };

  const getFieldFormatter = field => {
    const objValue = getFieldValue(field);

    return {
      ref: ref(),
      isJson: typeof objValue === 'object' && objValue !== undefined,
      value: objValue,
      field,
    };
  };
  const getFieldName = field => {
    const { getFieldName } = useFieldNameHook({ store });
    return getFieldName(field);
  };
  const rootList = computed(() => {
    formatCounter.value++;
    return fieldList.value.map((f: any) => ({
      name: f.field_name,
      type: f.field_type,
      formatter: getFieldFormatter(f),
    }));
  });

  const depth = computed(() => store.state.tableJsonFormatDepth);

  watch(
    () => [formatCounter.value],
    () => {
      updateRootFieldOperator(rootList.value, depth.value);
      setEditor(depth.value);
    },
    {
      immediate: true,
    },
  );

  watch(
    () => [depth.value],
    () => {
      setExpand(depth.value);
    },
  );

  onBeforeUnmount(() => {
    destroy();
  });
</script>
<style lang="scss">
  @import '../global/json-view/index.scss';

  .bklog-json-formatter-root {
    width: 100%;
    font-family: var(--table-fount-family);
    font-size: var(--table-fount-size);
    line-height: 20px;
    color: var(--table-fount-color);
    text-align: left;

    &:not(.is-json) {
      .bklog-root-field {
        .field-value {
          max-height: 50vh;
          overflow: auto;
          will-change: transform;
          transform: translateZ(0); /* 强制开启GPU加速 */
        }
      }
    }

    .bklog-scroll-box {
      max-height: 50vh;
      overflow: auto;
      will-change: transform;
      transform: translateZ(0); /* 强制开启GPU加速 */
    }

    .bklog-scroll-cell {
      word-break: break-all;
      span {
        content-visibility: auto;
        contain-intrinsic-size: 0 60px; /* 预估初始高度 */
      }
    }

    .bklog-root-field {
      margin-right: 4px;
      line-height: 20px;

      .bklog-json-view-row {
        word-break: break-all;
      }

      &:not(:first-child) {
        margin-top: 1px;
      }

      .field-name {
        min-width: max-content;

        .black-mark {
          width: max-content;
          padding: 0 2px;
          background: #e6e6e6;
          border-radius: 2px;
        }

        &::after {
          content: ':';
        }
      }

      .valid-text {
        :hover {
          color: #3a84ff;
          cursor: pointer;
        }
      }
    }

    .segment-content {
      font-family: var(--table-fount-family);
      font-size: var(--table-fount-size);
      line-height: 20px;

      span {
        width: max-content;
        min-width: 4px;
        font-family: var(--table-fount-family);
        font-size: var(--table-fount-size);
        color: var(--table-fount-color);
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

    &.is-inline {
      .bklog-root-field {
        word-break: break-all;
        display: inline-flex;

        .segment-content {
          word-break: break-all;
        }
      }
    }

    &.is-json {
      // display: inline-flex;
      width: 100%;
    }

    &.is-wrap-line {
      display: flex;
      flex-direction: column;

      .bklog-root-field {
        display: flex;

        .field-value {
          word-break: break-all;
        }
      }
    }

    mark {
      padding: 0 2px;
      border-radius: 2px;
    }
  }
</style>
<style lang="scss">
  .bklog-text-segment {
    .segment-content {
      font-family: var(--table-fount-family);
      font-size: var(--table-fount-size);
      line-height: 20px;

      .valid-text {
        cursor: pointer;

        &.focus-text,
        &:hover {
          color: #3a84ff;
        }
      }
    }
  }
</style>
