<script setup>
  import { ref, nextTick, computed, onMounted, watch } from 'vue';

  import SqlQueryOptions from './sql-query-options';
  import useFocusInput from './use-focus-input';
  import CreateLuceneEditor from './codemirror-lucene';
  import { debounce } from 'lodash';

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

  const refSqlQueryOption = ref(null);
  const isInputFocus = ref(false);
  const refUlRoot = ref(null);
  const separator = /\s(AND|OR)\s/i; // 区分查询语句条件
  const refEditorParent = ref(null);
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
      refSqlQueryOption.value?.beforeShowndFn?.();
      instance.popper?.style.setProperty('width', '100%');
    },
    onHiddenFn: () => {
      refSqlQueryOption.value?.beforeHideFn?.();
    },
  });

  const setEditorContext = val => {
    editorInstance.setValue(val);
  };

  const appendContextValue = val => {
    editorInstance.appendText(val);
  };

  const onEditorContextChange = doc => {
    emit('input', doc.text.join(''));
  };

  const debounceRetrieve = () => {
    emit('retrieve', modelValue.value);
  }

  watch(modelValue, () => {
    setEditorContext(modelValue.value);
  });

  const createEditorInstance = () => {
    editorInstance = CreateLuceneEditor({
      value: modelValue.value,
      target: refEditorParent.value,
      onChange: e => onEditorContextChange(e),
      onKeyEnter: view => {
        if (!(getTippyInstance()?.state?.isShown ?? false) || sqlActiveParamsIndex.value === null) {

          getTippyInstance()?.hide();
          debounceRetrieve();

          console.log('view', view);
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

  const sqlQueryItemList = computed(() => {
    return modelValue.value
      .split(separator)
      .filter(Boolean)
      .map(val => {
        if (/^\s*(AND|OR)\s*$/i.test(val)) {
          return {
            text: val,
            operator: val,
          };
        }

        return {
          text: val,
          operator: undefined,
        };
      });
  });

  const handleTextInputBlur = e => {
    isInputFocus.value = false;
    inputValue.value = '';
    handleInputBlur(e);
  };

  const handleFocusInput = () => {
    isInputFocus.value = true;
    nextTick(() => {
      delayShowInstance(refUlRoot.value);
    });
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
  }

  const handleCancel = () => {
    getTippyInstance()?.hide();
    handleContainerClick();
  };

  onMounted(() => {
    createEditorInstance();
  });
</script>
<template>
  <div class="search-sql-query">
    <div
      ref="refEditorParent"
      class="search-sql-editor"
    ></div>
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
    width: 100%;
    display: inline-flex;
    align-items: center;

    .search-sql-editor {
      width: 100%;

      .cm-editor {
        &.cm-focused {
          outline: none;
        }

        .cm-activeLine {
          background-color: transparent;
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
