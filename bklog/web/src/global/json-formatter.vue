<template>
  <span :class="['bklog-json-formatter-root', { 'is-wrap-line': isWrap, 'is-inline': !isWrap }]">
    <template v-for="item in rootList">
      <template v-if="item.formatter.isJson">
        <div
          :ref="item.formatter.ref"
          :key="item.name"
          class="bklog-root-json bklog-json-formatter"
        ></div>
      </template>
      <template v-else>
        <div
          :ref="item.formatter.ref"
          :key="item.name"
          class="bklog-root-field"
        >
          <span class="field-name black-mark">{{ item.name }}</span>
          <span class="field-split">:</span>
          <span class="field-value">{{ item.formatter.value }}</span>
        </div>
      </template>
    </template>
  </span>
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
  const isWrap = computed(() => store.state.tableLineIsWarp);
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
    if (typeof props.jsonValue === 'string') {
      return convertToObject(props.jsonValue);
    }

    return convertToObject(props.jsonValue[field.field_name]);
  };

  const getFieldFormatter = field => {
    const objValue = getFieldValue(field);

    if (typeof objValue === 'object' && objValue !== undefined) {
      return {
        ref: ref(),
        isJson: true,
        value: {
          [field.field_name]: objValue,
        },
      };
    }

    return {
      ref: ref(),
      isJson: false,
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
  .bklog-json-formatter-root {
    font-family: var(--table-fount-family);
    font-size: var(--table-fount-size);
    color: var(--table-fount-color);

    &.is-inline {
      display: flex;
    }

    .bklog-root-field {
      display: flex;
      margin-right: 2px;

      &:not(:first-child) {
        margin-top: 1px;
      }

      .field-name.black-mark {
        padding: 0 2px;
        background: #e6e6e6;
        border-radius: 2px;
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

      color: var(--table-fount-color);
      word-break: break-all;
      white-space: pre-line;

      span {
        display: inline-block;
        width: max-content;
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

    mark {
      padding: 0 2px;
      border-radius: 2px;
    }
  }

  table {
    &.jsoneditor-tree {
      tbody {
        tr {
          // display: flex;
          // align-items: flex-start;

          td {
            height: auto;

            .jsoneditor-field {
              width: fit-content;
              min-width: max-content;
              background: #e6e6e6;
              border-radius: 2px;
            }

            .jsoneditor-field,
            .jsoneditor-value {
              padding: 0 2px;
              font-size: 13px;
              line-height: 20px;
              word-break: break-all;
              white-space: pre-line;
              border: none;
            }
          }
        }
      }
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

  .bklog-root-json.bklog-json-formatter {
    margin-left: -30px;

    > .jsoneditor {
      &.jsoneditor-mode-view {
        border: none;

        > .jsoneditor-outer {
          > .jsoneditor-tree {
            > .jsoneditor-tree-inner {
              > table.jsoneditor-tree {
                > tbody {
                  > tr.jsoneditor-expanded:first-child {
                    display: none;
                  }
                }
              }
            }
          }
        }

        .jsoneditor-tree {
          overflow: hidden;

          .jsoneditor-tree-inner {
            table.jsoneditor-tree {
              tbody {
                tr {
                  td {
                    border-bottom: none;
                  }
                }
              }
            }
          }
        }
      }
    }

    &.is-inline {
      > div.jsoneditor {
        &.jsoneditor-mode-view {
          > div.jsoneditor-outer {
            > div.jsoneditor-tree {
              > div.jsoneditor-tree-inner {
                > table.jsoneditor-tree {
                  tbody {
                    display: flex;
                    flex-wrap: wrap;
                  }
                }
              }
            }
          }
        }
      }
    }
  }
</style>
