<template>
  <span :class="['origin-content', { 'is-rending': true, 'is-rending-end': !isRendindg }]">
    <div
      ref="refJsonEditor"
      :class="['bklog-json-formatter', { 'is-wrap-line': isWrap }]"
    ></div>
  </span>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import useJsonFormatter from '../hooks/use-json-formatter';
  import useStore from '../hooks/use-store';

  const emit = defineEmits(['menu-click']);
  const store = useStore();
  const isRendindg = ref(false);

  const props = defineProps({
    jsonValue: {
      type: Object,
      default: () => ({}),
    },
    fields: {
      type: Array,
      default: () => [],
    },
  });

  const refJsonEditor = ref<HTMLElement | null>();
  const formatCounter = ref(0);
  const isWrap = computed(() => store.state.tableLineIsWarp);

  const onSegmentClick = args => {
    emit('menu-click', args);
  };
  const { setValue } = useJsonFormatter({
    target: refJsonEditor,
    fields: props.fields,
    jsonValue: props.jsonValue,
    onSegmentClick,
  });
  const formatValue = computed(() => {
    const stringValue = Object.keys(props.jsonValue)
      .filter(name => props.fields.some((f: any) => f.field_name === name))
      .reduce((r, k) => Object.assign(r, { [k]: props.jsonValue[k] }), {});

    formatCounter.value++;
    return {
      stringValue,
    };
  });

  const deep = computed(() => store.state.tableJsonFormatDeep);

  watch(
    () => [formatCounter.value, deep.value],
    () => {
      isRendindg.value = true;
      setValue(formatValue.value.stringValue, Number(deep.value));
      setTimeout(() => {
        isRendindg.value = false;
      });
    },
    {
      immediate: true,
    },
  );
</script>
<style lang="scss">
  .origin-content {
    font-family: var(--table-fount-family);
    font-size: var(--table-fount-size);
    color: var(--table-fount-color);



    .black-mark {
      margin-right: 2px;
      background: #e6e6e6;
      border-radius: 2px;
    }

    .origin-value {
      margin: 0 4px 0 2px;
      word-break: break-all;
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
          display: flex;
          align-items: flex-start;

          td {
            height: auto;

            .jsoneditor-field {
              background: #e6e6e6;
              border-radius: 2px;
            }

            .jsoneditor-field,
            .jsoneditor-value {
              padding: 0 2px;
              font-size: 13px;
              line-height: 20px;
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

  .bklog-json-formatter {
    .jsoneditor {
      &.jsoneditor-mode-view {
        border: none;

        .jsoneditor-tree {
          overflow: hidden;

          .jsoneditor-tree-inner {
            table {
              &.jsoneditor-tree {
                tbody {
                  tr {
                    td {
                      border-bottom: none;
                    }
                  }
                }
              }

              &.jsoneditor-values {
                margin-left: 0;

                td {
                  &.jsoneditor-tree {
                    .jsoneditor-button {
                      &.jsoneditor-invisible {
                        display: none;
                      }
                    }
                  }
                }
              }
            }
          }
        }

        .jsoneditor-expandable {
          &.jsoneditor-expanded {
            display: none;
          }
        }

        .jsoneditor-value {
          .segment-content {
            font-family: var(--table-fount-family);
            font-size: var(--table-fount-size);
            line-height: 20px;

            color: var(--table-fount-color);
            white-space: normal;

            span {
              font-family: var(--table-fount-family);
              font-size: var(--table-fount-size);
              color: var(--table-fount-color);
            }
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

    &:not(.is-wrap-line) {
      table {
        &.jsoneditor-tree {
          tbody {
            display: flex;
            flex-wrap: wrap;
          }
        }
      }
    }
  }
</style>
<style lang="scss">
  @import '@/scss/mixins/flex.scss';

  .tippy-box {
    &[data-theme='segment-light'] {
      color: #26323d;
      background-color: #fff;
      box-shadow: 0 0 6px 0 #dcdee5;

      .tippy-arrow {
        color: #fff;
        background-color: #fff;
        box-shadow: rgb(220, 222, 229) 0px -12px 12px 0px;
      }

      .tippy-content {
        padding: 0;

        .event-tippy-content {
          &.event-icons {
            flex-direction: column;

            @include flex-center();

            .event-box {
              display: flex;
              align-items: center;
              justify-content: flex-start;
              min-width: 240px;
              height: 32px;
              padding: 0 10px;
              font-size: 12px;
              cursor: pointer;

              &:hover {
                background: #eaf3ff;
              }
            }

            .new-link {
              flex: 1;
              justify-content: right;
              width: 24px;
              height: 24px;

              &:hover {
                color: #3a84ff;
              }
            }

            .event-btn {
              flex: none;
              flex: 1;
              align-items: center;

              &:hover {
                color: #3a84ff;
              }

              .new-link {
                transform: translateY(1px);
              }
            }

            .tippy-tooltip {
              padding: 6px 2px;
            }

            .icon {
              display: inline-block;
              font-size: 14px;
              cursor: pointer;
            }

            .icon-minus-circle,
            .icon-plus-circle {
              margin-right: 6px;
            }

            .bklog-copy {
              margin-left: -4px;
              font-size: 24px;
            }
          }
        }
      }
    }
  }
</style>
