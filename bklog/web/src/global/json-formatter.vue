<template>
  <div :class="['bklog-json-formatter-root', { 'is-wrap-line': isWrap, 'is-inline': !isWrap }]">
    <template v-for="item in rootList">
      <div
        :key="item.name"
        class="bklog-root-field"
      >
        <span class="field-name"
          ><span class="black-mark" :data-field-name="item.name">{{ item.name }}</span></span
        >
        <span class="field-split">:</span>
        <span
          class="field-value"
          :data-field-name="item.name"
          :ref="item.formatter.ref"
          >{{ item.formatter.isJson ? '' : item.formatter.value }}</span
        >
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import useJsonRoot from '../hooks/use-json-root';
  import useStore from '../hooks/use-store';

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

      return convertToObject(props.jsonValue[field.field_name]);
    }

    return typeof props.jsonValue === 'object'
      ? props.jsonValue[field.field_name]
      : props.jsonValue;
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
    font-family: var(--table-fount-family);
    font-size: var(--table-fount-size);
    color: var(--table-fount-color);

    &.is-inline {
      display: flex;
      .bklog-root-field {
        display: inline-flex;

        .segment-content {
          display: inline-flex;
        }
      }
    }

    &.is-wrap-line {
      display: flex;
      flex-direction: column;
    }

    .bklog-root-field {
      display: flex;
      margin-right: 2px;
      width: max-content;

      &:not(:first-child) {
        margin-top: 1px;
      }

      .field-name {
        .black-mark {
          padding: 0 2px;
          background: #e6e6e6;
          border-radius: 2px;
          width: max-content;
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
        display: inline-block;
        width: max-content;
        font-family: var(--table-fount-family);
        font-size: var(--table-fount-size);
        color: var(--table-fount-color);
        min-width: 4px;
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

    mark {
      padding: 0 2px;
      border-radius: 2px;
    }
  }

  .bk-table-row {
    &.hover-row {
      tbody,
      tr,
      td {
        background-color: #f5f7fa;
      }
    }
  }

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
