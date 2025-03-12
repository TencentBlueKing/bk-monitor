<script setup>
  import { ref, nextTick, onMounted, computed } from 'vue';

  import CreateLuceneEditor from './codemirror-lucene';
  import SqlQueryOptions from './sql-query-options';
  import useFocusInput from './use-focus-input';

  const props = defineProps({
    value: {
      type: String,
      required: true,
      default: '',
    },
  });

  const emit = defineEmits(['retrieve', 'input', 'change', 'height-change']);
  const handleHeightChange = height => {
    emit('height-change', height);
  };

  const placeholderText = '/快速定位到搜索，log:error AND"name=bklog"';
  const refSqlQueryOption = ref(null);
  const refEditorParent = ref(null);

  // SQL查询提示选中可选项索引
  const sqlActiveParamsIndex = ref(null);

  let editorInstance = null;

  const setEditorContext = val => {
    editorInstance?.setValue(val);
  };

  const formatModelValueItem = item => {
    setEditorContext(item);
    return item;
  };

  const handleWrapperClickCapture = e => {
    return refEditorParent.value?.contains(e.target) ?? false;
  };

  const {
    modelValue,
    isDocumentMousedown,
    setIsDocumentMousedown,
    delayShowInstance,
    getTippyInstance,
    handleContainerClick,
  } = useFocusInput(props, {
    onHeightChange: handleHeightChange,
    formatModelValueItem,
    refContent: refSqlQueryOption,
    arrow: false,
    newInstance: false,
    addInputListener: false,
    tippyOptions: {
      maxWidth: 'none',
      offset: [0, 15],
    },
    onShowFn: instance => {
      if (refSqlQueryOption.value?.beforeShowndFn?.()) {
        instance.popper?.style.setProperty('width', '100%');
        refSqlQueryOption.value?.$el?.querySelector('.list-item')?.classList.add('is-hover');
        return true;
      }

      return false;
    },
    onHiddenFn: () => {
      if (isDocumentMousedown.value) {
        setIsDocumentMousedown(false);
        return false;
      }
      refSqlQueryOption.value?.$el?.querySelector('.list-item ')?.classList.remove('is-hover');
      refSqlQueryOption.value?.beforeHideFn?.();
      return true;
    },
    handleWrapperClick: handleWrapperClickCapture,
  });

  const onEditorContextChange = doc => {
    const val = doc.text.join('');
    emit('input', val);
    if (val.length && !(getTippyInstance()?.state?.isShown ?? false)) {
      delayShowInstance(refEditorParent.value);
    }
  };

  const isEmptySqlString = computed(() => {
    return /^\s*$/.test(modelValue.value) || !modelValue.value.length;
  });

  const debounceRetrieve = () => {
    emit('retrieve', modelValue.value);
  };

  const closeAndRetrieve = () => {
    // 键盘enter事件，如果当前没有选中任何可选项 或者当前没有联想提示
    // 此时执行查询操作，如果有联想提示，关闭提示弹出
    if (!(getTippyInstance()?.state?.isShown ?? false) || sqlActiveParamsIndex.value === null) {
      getTippyInstance()?.hide();
      debounceRetrieve();
    }
  };

  const createEditorInstance = () => {
    editorInstance = CreateLuceneEditor({
      value: /^\s*\*\s*$/.test(modelValue.value) ? '' : modelValue.value,
      target: refEditorParent.value,
      stopDefaultKeyboard: () => {
        return getTippyInstance()?.state?.isShown ?? false;
      },
      onChange: e => onEditorContextChange(e),
      onKeyEnter: () => {
        closeAndRetrieve();
        return true;
      },
      onFocusChange: isFocusing => {
        if (isFocusing && !(getTippyInstance()?.state?.isShown ?? false)) {
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

  const handleQueryChange = (value, retrieve) => {
    if (modelValue.value !== value) {
      setEditorContext(value);
      nextTick(() => {
        handleContainerClick();
        if (retrieve) {
          closeAndRetrieve();
        }
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
      v-show="isEmptySqlString"
      >{{ placeholderText }}</span
    >
    <div style="display: none">
      <SqlQueryOptions
        ref="refSqlQueryOption"
        :value="modelValue"
        @active-change="handleSqlParamsActiveChange"
        @cancel="handleCancel"
        @change="handleQueryChange"
        @retrieve="closeAndRetrieve"
      ></SqlQueryOptions>
    </div>
  </div>
</template>
<style lang="scss">
  .search-sql-query {
    display: inline-flex;
    align-items: center;
    width: 100%;

    .empty-placeholder-text {
      position: absolute;
      top: 50%;
      left: 14px;
      font-family: 'Roboto Mono', Consolas, Menlo, Courier, monospace;
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
          font-family: Menlo, Monaco, Consolas, Courier, 'PingFang SC', 'Microsoft Yahei', monospace;
          font-size: 12px;

          .cm-line {
            width: fit-content;
            color: #b17313;

            .ͼb {
              color: #7c609e;
            }

            .ͼi,
            .ͼf {
              color: #02776e;
            }
          }

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

<style lang="scss">
  @import 'tippy.js/dist/tippy.css';
</style>
<style lang="scss">
  [data-tippy-root] .tippy-box {
    &[data-theme^='log-light'] {
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
  }
</style>
