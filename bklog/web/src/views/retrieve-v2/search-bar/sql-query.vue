<script setup>
  import { ref, nextTick, onMounted, computed, onBeforeUnmount } from 'vue';

  import useLocale from '@/hooks/use-locale';

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

  const emit = defineEmits(['retrieve', 'input', 'change', 'height-change', 'popup-change']);
  const handleHeightChange = height => {
    emit('height-change', height);
  };

  const { t } = useLocale();
  const placeholderText = ` / ${t('快速定位到搜索')}，log:error AND"name=bklog"`;
  const refSqlQueryOption = ref(null);
  const refEditorParent = ref(null);
  const editorFocusPosition = ref(null);
  const refPopElement = ref(null);

  // 记录输入状态
  const inputState = ref({
    focusPos: null, // focus时的光标位置
    newContent: '', // focus后新增的内容
    hasNewInput: false, // 是否有新增输入
    hasSpace: false, // 是否包含空格
    lastSpacePos: null, // 最后一个空格的位置
    isSelecting: false, // 是否正在选择填充
  });

  // SQL查询提示选中可选项索引
  const sqlActiveParamsIndex = ref(null);

  let editorInstance = null;
  let isSelectedText = false;

  /**
   * 更新编辑器内容
   * @param val 更新值
   * @param from 开始位置
   * @param to 结束位置：如果是指定位置插入，To可以忽略，只要指定from位置就行
   * 如果是替换，需要指定结束位置；to：设置为 Infinity 表示从from位置到结束位置全部替换
   */
  const setEditorContext = (val, from = 0, to = undefined) => {
    editorInstance?.setValue(val, from, to);
  };

  /**
   * use-focus在监听到props.value更新时会调用此方法
   * 用于格式化并更新编辑器内容
   * @param item
   */
  const formatModelValueItem = item => {
    setEditorContext(item, 0, Infinity);
    return item;
  };

  /**
   * 用于点击操作判定当前是否在搜索容器内部进行多次点击
   * @param e
   */
  const handleWrapperClickCapture = e => {
    return refEditorParent.value?.contains(e.target) ?? false;
  };

  const { modelValue, delayShowInstance, getTippyInstance, handleContainerClick, hideTippyInstance } = useFocusInput(
    props,
    {
      onHeightChange: handleHeightChange,
      formatModelValueItem,
      refContent: refSqlQueryOption,
      refTarget: refEditorParent,
      refWrapper: refEditorParent,
      arrow: false,
      newInstance: false,
      addInputListener: false,
      tippyOptions: {
        maxWidth: 'none',
        offset: [0, 15],
        hideOnClick: false,
      },
      onShowFn: instance => {
        emit('popup-change', { isShow: true });

        if (isSelectedText) {
          return false;
        }

        if (refSqlQueryOption.value?.beforeShowndFn?.()) {
          instance.popper?.style.setProperty('width', '100%');
          refSqlQueryOption.value?.$el?.querySelector('.list-item')?.classList.add('is-hover');
          requestAnimationFrame(() => {
            editorInstance?.setFocus();
          });
          return true;
        }

        return false;
      },
      onHiddenFn: () => {
        refSqlQueryOption.value?.beforeHideFn?.();
        emit('popup-change', { isShow: false });
        return true;
      },
      handleWrapperClick: handleWrapperClickCapture,
    },
  );

  /**
   * 编辑器内容改变回掉事件
   * @param doc
   */
  const onEditorContextChange = doc => {
    const val = doc.text.join('');
    if (val !== props.value) {
      emit('input', val);
      nextTick(() => {
        emit('change', val);
      });
      if (val.length && !(getTippyInstance()?.state?.isShown ?? false)) {
        delayShowInstance(refEditorParent.value);
      }
    }
  };

  const isEmptySqlString = computed(() => {
    return /^\s*$/.test(modelValue.value) || !modelValue.value.length;
  });

  const debounceRetrieve = value => {
    emit('retrieve', value ?? modelValue.value);
  };

  const closeAndRetrieve = value => {
    // 键盘enter事件，如果当前没有选中任何可选项 或者当前没有联想提示
    // 此时执行查询操作，如果有联想提示，关闭提示弹出
    if (!(getTippyInstance()?.state?.isShown ?? false) || sqlActiveParamsIndex.value === null) {
      hideTippyInstance();
      debounceRetrieve(value);
    }
  };

  // 重置输入状态
  const resetInputState = () => {
    inputState.value = {
      focusPos: null,
      newContent: '',
      hasNewInput: false,
      hasSpace: false,
      lastSpacePos: null,
      isSelecting: false,
    };
  };

  // 更新输入状态
  const updateInputState = state => {
    const currentPos = state.selection.main.to;
    const currentValue = state.doc.toString();

    // 如果是新的focus，记录位置
    if (inputState.value.focusPos === null) {
      inputState.value.focusPos = currentPos;
      inputState.value.hasNewInput = false;
      inputState.value.hasSpace = false;
      inputState.value.lastSpacePos = null;
      inputState.value.isSelecting = false;
      return;
    }

    // 如果正在选择填充，不更新输入状态
    if (inputState.value.isSelecting) {
      return;
    }

    // 如果光标位置在focus位置之后，说明有新增内容
    if (currentPos > inputState.value.focusPos) {
      const newContent = currentValue.slice(inputState.value.focusPos, currentPos);
      // 检查是否包含空格
      const hasSpace = /\s/.test(newContent);

      inputState.value.newContent = newContent;
      inputState.value.hasNewInput = true;
      inputState.value.hasSpace = hasSpace;

      // 如果包含空格，找到最后一个空格的位置
      if (hasSpace) {
        const spaceMatch = newContent.match(/\s+$/);
        if (spaceMatch) {
          // 计算最后一个空格在文档中的位置
          inputState.value.lastSpacePos = inputState.value.focusPos + spaceMatch.index;
        }
      }
    } else if (currentPos < inputState.value.focusPos) {
      // 如果光标位置在focus位置之前，说明用户移动了光标，重置状态
      resetInputState();
      inputState.value.focusPos = currentPos;
    }
  };

  const getSelectionRenage = (value, replace, type) => {
    // 如果是替换模式，替换全部内容
    if (replace) {
      return {
        from: 0,
        to: Infinity,
      };
    }

    // 如果是选择填充，替换当前光标位置的内容
    if (inputState.value.isSelecting) {
      return {
        from: editorFocusPosition.value,
        to: editorFocusPosition.value,
      };
    }

    // 如果有focus位置且有新增输入，只替换新增的部分
    if (inputState.value.focusPos !== null && inputState.value.hasNewInput) {
      // 如果有空格，在最后一个空格的位置插入
      if (inputState.value.hasSpace && inputState.value.lastSpacePos !== null) {
        // 在最后一个空格的位置插入，保留空格
        return {
          from: inputState.value.lastSpacePos + 1, // 在空格后插入
          to: inputState.value.focusPos + inputState.value.newContent.length,
          insertSpace: false,
        };
      }

      // 如果没有空格，替换整个新增内容
      return {
        from: inputState.value.focusPos,
        to: inputState.value.focusPos + inputState.value.newContent.length,
      };
    }

    // 如果没有新增输入，在光标位置追加
    return {
      from: editorFocusPosition.value,
      to: editorFocusPosition.value,
    };
  };

  const handleQueryChange = (value, retrieve, replace = true, type = undefined) => {
    if (modelValue.value !== value) {
      // 确保编辑器实例存在
      if (!editorInstance) {
        return;
      }

      // 标记为选择填充状态
      inputState.value.isSelecting = true;

      const range = getSelectionRenage(value, replace, type);
      const { from, to, insertSpace } = range;

      // 如果需要插入空格，在值后面添加空格
      const finalValue = insertSpace ? `${value} ` : value;
      setEditorContext(finalValue, from, to);

      // 更新光标位置
      nextTick(() => {
        if (editorInstance) {
          if (retrieve) {
            const resolvedValue = editorInstance.getValue();
            closeAndRetrieve(resolvedValue);
          }
          // 重置选择状态
          inputState.value.isSelecting = false;
        }
      });
    }
  };

  const handleSqlParamsActiveChange = val => {
    sqlActiveParamsIndex.value = val;
  };

  const handleCancel = (force = false) => {
    hideTippyInstance();

    if (!force) {
      handleContainerClick();
    }
  };

  const handleDocumentClick = e => {
    if (
      refEditorParent?.value?.contains(e.target) ||
      refSqlQueryOption.value?.$el.contains(e.target) ||
      e.target?.parentElement?.hasAttribute('data-bklog-v3-pop-click-item')
    ) {
      return;
    }

    hideTippyInstance();
  };

  const handleEditorClick = () => {
    if (editorInstance === null) {
      createEditorInstance();
    }

    if (!(getTippyInstance()?.state?.isShown ?? false)) {
      delayShowInstance(refEditorParent.value);
    }
  };

  const createEditorInstance = () => {
    editorInstance = CreateLuceneEditor({
      value: /^\s*\*\s*$/.test(modelValue.value) ? '' : modelValue.value,
      target: refEditorParent.value,
      stopDefaultKeyboard: () => {
        return getTippyInstance()?.state?.isShown ?? false;
      },
      onChange: e => {
        onEditorContextChange(e);
      },
      onKeyEnter: () => {
        debounceRetrieve();
        return true;
      },
      onFocusChange: (state, isFocusing) => {
        if (isFocusing) {
          if (!(getTippyInstance()?.state?.isShown ?? false)) {
            delayShowInstance(refEditorParent.value);
          }
          // 重置选择状态
          inputState.value.isSelecting = false;
        }
      },
      onFocusPosChange: state => {
        editorFocusPosition.value = state.selection.main.to;
        isSelectedText = state.selection.main.to > state.selection.main.from;
        updateInputState(state);
      },
    });
  };

  onMounted(() => {
    createEditorInstance();
    document.addEventListener('click', handleDocumentClick);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick);
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
      ref="refPopElement"
      class="empty-placeholder-text"
      v-show="isEmptySqlString"
      >{{ placeholderText }}</span
    >
    <div style="display: none">
      <SqlQueryOptions
        ref="refSqlQueryOption"
        :focus-position="editorFocusPosition"
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
              font-weight: bold;
              color: #7c609e;
              font-family: RobotoMono-BoldItalic;
              font-style: italic;
            }

            .cm-not-keyword {
              .ͼb {
                color: #ea3636;
              }
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
