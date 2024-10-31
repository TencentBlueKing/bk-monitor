<template>
  <div :class="['bklog-json-formatter-root', { 'is-wrap-line': isWrap, 'is-inline': !isWrap, 'is-json': formatJson }]">
    <template v-for="item in rootList">
      <span
        :key="item.name"
        class="bklog-root-field"
      >
        <span class="field-name"
          ><span
            class="black-mark"
            :data-field-name="item.name"
            >{{ item.name }}</span
          ></span
        >
        <span class="field-split">:</span>
        <span
          class="field-value"
          :data-field-name="item.name"
          :ref="item.formatter.ref"
          >{{ item.formatter.isJson ? '' : item.formatter.value }}</span
        >
      </span>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import useJsonRoot from '../hooks/use-json-root';
  import useStore from '../hooks/use-store';
  //@ts-ignore
  import { parseTableRowData } from '@/common/util';


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
  const { updateRootFieldOperator, setExpand } = useJsonRoot({
    fields: fieldList.value,
    onSegmentClick,
  });

  const convertToObject = val => {
    if (typeof val === 'string' && props.formatJson) {
      const originValue = val.replace(/<\/?mark>/gim, '');
      if (/^(\{|\[)/.test(originValue)) {
        try {
          return JSON.parse(originValue);
        } catch (e) {
          console.error(e);
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

    return typeof props.jsonValue === 'object' ? parseTableRowData(props.jsonValue,field.field_name) : props.jsonValue;
  };

  const getFieldFormatter = field => {
    const objValue = getFieldValue(field);

    return {
      ref: ref(),
      isJson: typeof objValue === 'object' && objValue !== undefined,
      value: objValue,
    };
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
</script>
<style lang="scss">
  @import '../global/json-view/index.scss';

  .bklog-json-formatter-root {
    width: 100%;
    font-family: var(--table-fount-family);
    font-size: var(--table-fount-size);
    line-height: 20px;
    color: var(--table-fount-color);

    .bklog-root-field {
      margin-right: 2px;
      line-height: 20px;

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

        .segment-content {
          word-break: break-all;
        }
      }
    }

    &.is-json {
      display: inline-block;
      width: 100%;

      .bklog-root-field {
        display: inline-flex;
      }
    }

    &.is-wrap-line {
      display: flex;
      flex-direction: column;

      .bklog-root-field {
        display: flex;
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
