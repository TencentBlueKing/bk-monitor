<script setup>
  import { ref, nextTick, onMounted, watch } from 'vue';

  import SqlQueryOptions from './sql-query-options';
  import useFocusInput from './use-focus-input';
  import CreateLuceneEditor from './codemirror-lucene';

  const props = defineProps({
    value: {
      type: String,
      required: true,
      default: '*',
    },
  });

  const emit = defineEmits(['retrieve', 'input', 'change', 'height-change']);
  const handleHeightChange = height => {
    emit('height-change', height);
  };

  const placeholderText = 'Query Syntax: log：error  AND "name=bklog"';
  const refSqlQueryOption = ref(null);
  const refEditorParent = ref(null);

  // SQL查询提示选中可选项索引
  const sqlActiveParamsIndex = ref(null);

  let editorInstance = null;

  const formatModelValueItem = item => {
    return item.replace(/^\s*\*\s*$/, '');
  };

  const { modelValue, delayShowInstance, getTippyInstance, handleContainerClick } = useFocusInput(props, {
    onHeightChange: handleHeightChange,
    formatModelValueItem,
    refContent: refSqlQueryOption,
    arrow: false,
    newInstance: false,
    addInputListener: false,
    tippyOptions: {
      maxWidth: 'none',
    },
    onShowFn: instance => {
      if (refSqlQueryOption.value?.beforeShowndFn?.()) {
        instance.popper?.style.setProperty('width', '100%');
        return true;
      }

      return false;
    },
    onHiddenFn: () => {
      refSqlQueryOption.value?.beforeHideFn?.();
    },
  });

  const setEditorContext = val => {
    editorInstance.setValue(val);
  };

  const onEditorContextChange = doc => {
    emit('input', doc.text.join(''));
    if (!(getTippyInstance()?.state?.isShown ?? false)) {
      delayShowInstance(refEditorParent.value);
    }
  };

  const debounceRetrieve = () => {
    emit('retrieve', modelValue.value);
  };

  watch(modelValue, () => {
    setEditorContext(modelValue.value);
  });

  const createEditorInstance = () => {
    editorInstance = CreateLuceneEditor({
      value: modelValue.value,
      target: refEditorParent.value,
      onChange: e => onEditorContextChange(e),
      onKeyEnter: () => {
        // 键盘enter事件，如果当前没有选中任何可选项 或者当前没有联想提示
        // 此时执行查询操作，如果有联想提示，关闭提示弹出
        if (!(getTippyInstance()?.state?.isShown ?? false) || sqlActiveParamsIndex.value === null) {
          getTippyInstance()?.hide();
          debounceRetrieve();
        }
      },
      onFocusChange: isFocusing => {
        if (isFocusing) {
          delayShowInstance(refEditorParent.value);
          return;
        }
      },
    });
  };

  const handleEditorClick = () => {
    if (editorInstance === null) {
      createEditorInstance();
    }

    if (!(getTippyInstance()?.state?.isShown ?? false) && editorInstance.view.hasFocus) {
      delayShowInstance(refEditorParent.value);
    }
  };

  const handleQueryChange = value => {
    if (modelValue.value !== value) {
      setEditorContext(value);
      nextTick(() => {
        handleContainerClick();
      });
    }
  };

  const handleSqlParamsActiveChange = val => {
    sqlActiveParamsIndex.value = val;
  };

  const handleCancel = () => {
    getTippyInstance()?.hide();
    handleContainerClick();
  };

  onMounted(() => {
    createEditorInstance();
  });
</script>
<template>
  <div
    class="search-sql-query"
    @click="handleEditorClick"
  >
    <div
      ref="refEditorParent"
      class="search-sql-editor"
    ></div>
    <span
      class="empty-placeholder-text"
      v-show="!modelValue.length"
      >{{ placeholderText }}</span
    >
    <div style="display: none">
      <SqlQueryOptions
        ref="refSqlQueryOption"
        :value="modelValue"
        @active-change="handleSqlParamsActiveChange"
        @cancel="handleCancel"
        @change="handleQueryChange"
      ></SqlQueryOptions>
    </div>
  </div>
</template>
<style>
  .search-sql-query {
    display: inline-flex;
    align-items: center;
    width: 100%;

    .empty-placeholder-text {
      position: absolute;
      top: 50%;
      left: 14px;
      font-size: 12px;
      line-height: 30px;
      color: #c4c6cc;
      pointer-events: none;
      transform: translateY(-50%);
    }

    .search-sql-editor {
      width: 100%;
      padding-left: 8px;

      .cm-editor {
        &.cm-focused {
          outline: none;
        }

        .cm-activeLine {
          background-color: transparent;
        }

        .cm-scroller {
          .cm-gutters {
            display: none;

            /* border-right-color: transparent; */
            background-color: transparent;

            .cm-lineNumbers,
            .cm-foldGutter {
              .cm-activeLineGutter {
                background-color: transparent;
              }
            }
          }
        }
      }
    }
  }
</style>

<style scoped>
  @import 'tippy.js/dist/tippy.css';
</style>
<style>
  [data-theme='log-light'] {
    color: #63656e;
    background-color: #fff;
    box-shadow: 0 2px 6px 0 #0000001a;

    .tippy-content {
      padding: 0;
    }

    .tippy-arrow {
      color: #fff;

      &::after {
        background-color: #fff;
        box-shadow: 0 2px 6px 0 #0000001a;
      }
    }
  }
</style>
