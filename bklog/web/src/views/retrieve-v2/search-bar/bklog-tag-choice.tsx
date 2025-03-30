import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, Ref, ref, watch } from 'vue';
import PopInstanceUtil from '../../../global/pop-instance-util';
import useResizeObserve from '../../../hooks/use-resize-observe';
import useLocale from '../../../hooks/use-locale';
import { getCharLength } from '../../../common/util';

import './bklog-tag-choice.scss';

export default defineComponent({
  props: {
    list: {
      type: Array,
      default: () => [],
    },
    id: {
      type: String,
      default: 'id',
    },
    name: {
      type: String,
      default: 'id',
    },
    minWidth: {
      type: String,
      default: '120px',
    },
    maxWidth: {
      type: String,
      default: '560px',
    },
    maxHeight: {
      type: String,
      default: null,
    },
    minHeight: {
      type: String,
      default: '32px',
    },

    valueTagMaxWidth: {
      type: String,
      default: '200px',
    },

    value: {
      type: [String, Number, Array],
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
    placeholder: {
      type: String,
      default: '请选择...',
    },
    foucsFixed: {
      type: Boolean,
      default: false,
    },
  },
  model: {
    prop: 'value',
    event: 'change',
  },
  emits: ['change', 'input', 'toggle'],
  setup(props, { slots, emit }) {
    const isListOpended = ref(false);
    const refRootElement: Ref<HTMLElement> = ref(null);
    const refChoiceList: Ref<HTMLElement> = ref(null);
    const refTagInputElement: Ref<HTMLElement> = ref(null);
    const refTagInputContainer: Ref<HTMLElement> = ref(null);
    const refFixedPointerElement: Ref<HTMLElement> = ref(null);
    let focusFixedElement: HTMLElement = null;
    let fixedInstance: PopInstanceUtil = null;

    const inputTagValue = ref('');
    const tagInputIndex = ref(null);
    const containerWidth = ref(0);
    const activeItemIndex = ref(null);
    const editItemOption = ref({
      index: null,
      width: 12,
    });

    const isInputFocused = ref(false);

    const INPUT_MIN_WIDTH = 12;

    const { t } = useLocale();

    useResizeObserve(refRootElement, entry => {
      containerWidth.value = (entry.target as HTMLElement).offsetWidth;
    });

    const containerStyle = computed(() => {
      return {
        width: `${containerWidth.value}px`,
      };
    });

    const tagInputStyle = computed(() => {
      const charLen = Math.max(getCharLength(inputTagValue.value), 1);

      return {
        minWidth: `${INPUT_MIN_WIDTH}px`,
        width: `${charLen * INPUT_MIN_WIDTH}px`,
      };
    });

    const stopDefaultPrevented = e => {
      e.stopPropagation();
      e.stopImmediatePropagation();
      e.preventDefault();
    };

    const popInstance = new PopInstanceUtil({
      refContent: () => refChoiceList.value,
      arrow: false,
      onShowFn: () => {
        emit('toggle', true);
        return true;
      },
      onHiddenFn: () => {
        emit('toggle', false);
        return true;
      },
      tippyOptions: {
        hideOnClick: false,
        appendTo: document.body,
        placement: 'bottom-start',
        onShown: () => {
          popInstance.setIsShowing(false);
        },
      },
    });

    const dropdownIconName = computed(() => {
      if (isListOpended.value) {
        return 'bk-icon icon-angle-up';
      }

      return 'bk-icon icon-angle-down';
    });

    const getListItemId = (item: any) => {
      if (typeof item === 'object') {
        return item[props.id] ?? item;
      }

      return item;
    };

    const getItemKey = (item: any, index) => {
      return `key_${index}_${getListItemId(item)}`;
    };

    const getListItemName = (item: any) => {
      if (typeof item === 'object') {
        return item[props.name] ?? item;
      }

      return item;
    };

    const valueList = computed(() => {
      if (Array.isArray(props.value)) {
        return props.value.map(item => (props.list ?? []).find(item2 => getListItemId(item2) === item) ?? item);
      }

      return [props.value].map(item => (props.list ?? []).find(item2 => getListItemId(item2) === item) ?? item);
    });

    const valueWithInputList = computed(() => {
      if (
        typeof tagInputIndex.value === 'number' &&
        tagInputIndex.value >= 0 &&
        tagInputIndex.value < valueList.value.length
      ) {
        return [
          ...valueList.value.slice(0, tagInputIndex.value),
          { __tag_input__: true },
          ...valueList.value.slice(tagInputIndex.value),
        ];
      }

      return [...valueList.value, { __tag_input__: true }];
    });

    const optionList = computed(() => {
      return (props.list ?? []).map(item => {
        return {
          item,
          selected: valueList.value.some(v => getListItemId(v) === getListItemId(item)),
        };
      });
    });

    const placeholderText = computed(() => {
      if (!isInputFocused.value && valueList.value.length === 0) {
        return props.placeholder;
      }

      return '';
    });

    const handleInputValueChange = (e: any) => {
      const input = e.target;
      inputTagValue.value = input.value;
      emit('input', input.value);
    };

    /**
     * 获取抛出事件
     * @param value
     */
    const emitValue = value => {
      const itemId = getListItemId(value);
      // 避免重复添加
      if (valueList.value.some(item => getListItemId(item) === itemId)) {
        return;
      }

      const targetValue = new Array();
      valueList.value.forEach(v => {
        targetValue.push(getListItemId(v));
      });

      targetValue.push(getListItemId(value));

      emit('change', targetValue);
    };

    /**
     * 鼠标点击空白位置执行当前focused的 edit input blur行为
     */
    const handleEditInputBlur = () => {
      if (editItemOption.value.index !== null) {
        let isUpdate = false;

        const targetValue = new Array();
        valueList.value.forEach((v, index) => {
          if (index !== editItemOption.value.index) {
            targetValue.push(getListItemId(v));
          } else {
            isUpdate = getListItemId(v) !== inputTagValue.value;
            if (inputTagValue.value !== '') {
              targetValue.push(inputTagValue.value);
            }
          }
        });

        if (isUpdate) {
          emit('change', targetValue);
        }
      }

      editItemOption.value.index = null;
      editItemOption.value.width = 12;
      inputTagValue.value = '';
    };

    /**
     * 当绑定的数据改变时，销毁当前弹出内容，根据Vue渲染出来的结果进行弹出内容的更新
     */
    const updateFiexedInstanceContent = () => {
      return new Promise(resolve => {
        nextTick(() => {
          destroyFixedContent();
          setFixedValueContent();
          fixedInstance.setProps({
            content: focusFixedElement,
          });

          popInstance.initInistance(focusFixedElement);
          popInstance.getTippyInstance().show();
          resolve(true);
        });
      });
    };

    const handleDeleteItemClick = (e, val) => {
      stopDefaultPrevented(e);

      const targetValue = new Array();
      valueList.value.forEach(v => {
        if (v !== val) {
          targetValue.push(getListItemId(v));
        }
      });

      emit('change', targetValue);
      refTagInputElement.value?.focus();
    };

    const handleOptionItemClick = val => {
      emitValue(getListItemId(val));
      if (props.foucsFixed) {
        updateFiexedInstanceContent();
      }
    };

    /**
     * Enter 当前键入值
     * @param e
     */
    const handleInputKeyup = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        stopDefaultPrevented(e);

        emitValue(inputTagValue.value);
        clearInputTag();
      }
    };

    const handleDeleteAllClick = e => {
      stopDefaultPrevented(e);
      emit('change', []);
    };

    let focusFixedElementHeight = 0;
    // 监听输入框高度改变
    // 自适应弹出位置
    const fixedContentResizeObserver = new ResizeObserver(() => {
      if (focusFixedElement) {
        if (focusFixedElementHeight !== focusFixedElement.offsetHeight) {
          focusFixedElementHeight = focusFixedElement.offsetHeight;
          popInstance.repositionTippyInstance();
        }
      }
    });

    /**
     * Fixed 模式Input事件添加监听
     * @param e
     */
    const handleCloneFixedInputChange = (e: InputEvent) => {
      handleInputValueChange(e);
      const target = e.target as HTMLInputElement;
      const charLen = Math.max(getCharLength(inputTagValue.value), 1);
      target.style.setProperty('width', `${charLen * INPUT_MIN_WIDTH}px`);
    };

    const destroyFixedContent = () => {
      focusFixedElement?.removeEventListener('click', handleFixedValueListClick);

      const input = focusFixedElement?.querySelector('[data-bklog-choice-text-input]') as HTMLInputElement;
      input?.removeEventListener('keyup', handleFixedValueInputKeyup);
      input?.removeEventListener('input', handleCloneFixedInputChange);
      fixedContentResizeObserver.disconnect();

      focusFixedElementHeight = 0;
      focusFixedElement = null;
    };

    const setFocuseFixedPopEvent = () => {
      if (focusFixedElement) {
        focusFixedElement.addEventListener('click', handleFixedValueListClick);

        const input = focusFixedElement.querySelector('[data-bklog-choice-text-input]') as HTMLInputElement;
        if (input) {
          input.addEventListener('keyup', handleFixedValueInputKeyup);
          input.addEventListener('input', handleCloneFixedInputChange);
        }
      }
    };

    const setFixedValueContent = () => {
      if (!focusFixedElement) {
        focusFixedElement = refTagInputContainer.value.cloneNode(true) as HTMLElement;
        focusFixedElementHeight = focusFixedElement.offsetHeight;
        fixedContentResizeObserver.observe(focusFixedElement);
        setFocuseFixedPopEvent();
      }
    };

    const handleCustomTagClick = (e: MouseEvent) => {
      emitValue(inputTagValue.value);
      clearInputTag();
      stopDefaultPrevented(e);
    };

    /**
     * 自动 focus 输入框
     * @returns
     */
    const autoFocusInput = () => {
      const editInput = focusFixedElement.querySelector('[data-bklog-choice-value-edit-input]') as HTMLInputElement;
      if (editInput) {
        editInput.focus();
        return;
      }

      const input = focusFixedElement.querySelector('[data-bklog-choice-text-input]') as HTMLInputElement;
      input?.focus();
    };

    /**
     * fixed 模式弹出内容点击事件监听
     * @param e
     * @returns
     */
    const handleFixedValueListClick = (e: MouseEvent) => {
      stopDefaultPrevented(e);

      const target = e?.target as HTMLElement;

      handleEditInputBlur();

      if (target?.classList.contains('bklog-choice-value-span')) {
        const index = target.parentElement.getAttribute('data-item-index');
        editItemOption.value.index = parseInt(index);
        editItemOption.value.width = target.parentElement.offsetWidth;
        inputTagValue.value = target.innerText;
      }

      // 点击删除单个值
      if (target.hasAttribute('data-bklog-choice-item-del')) {
        const index = parseInt(target.getAttribute('data-bklog-choice-item-del') ?? '-1', 10);
        if (index >= 0) {
          const targetValue = new Array();
          valueList.value.forEach((v, idx) => {
            if (idx !== index) {
              targetValue.push(getListItemId(v));
            }
          });

          emit('change', targetValue);
        }
      }

      updateFiexedInstanceContent().then(() => {
        autoFocusInput();
      });
    };

    const handleFixedValueInputKeyup = (e: KeyboardEvent) => {
      handleInputKeyup(e);
      if (e.key === 'Enter') {
        updateFiexedInstanceContent();
      }
    };

    fixedInstance = new PopInstanceUtil({
      refContent: () => {
        setFixedValueContent();
        return focusFixedElement;
      },
      arrow: false,
      tippyOptions: {
        appendTo: document.body,
        hideOnClick: false,
        placement: 'bottom-start',
        theme: 'log-pure-choice',
        offset: [0, -1],
        onShown: () => {
          fixedInstance.setIsShowing(false);
          nextTick(() => {
            autoFocusInput();
            popInstance.show(focusFixedElement);
            popInstance.repositionTippyInstance();
          });
        },
        onHidden: () => {
          destroyFixedContent();
        },
      },
    });

    const cloneFixedItem = () => {
      fixedInstance.show(refFixedPointerElement.value, true, true);
    };

    const execContainerClick = () => {
      if (hiddenItemCount.value > 0) {
        isInputFocused.value = true;

        calcItemEllipsis().then(() => {
          if (props.foucsFixed) {
            cloneFixedItem();
            return;
          }

          popInstance.show(refRootElement.value);
          refTagInputElement.value?.focus();
        });

        return;
      }

      if (props.foucsFixed) {
        cloneFixedItem();
        return;
      }

      popInstance.show(refRootElement.value);
      refTagInputElement.value?.focus();
    };

    const handleSelectedValueItemclick = (e: MouseEvent, item, index) => {
      if (!item.__tag_input__) {
        stopDefaultPrevented(e);

        const target = e.target as HTMLElement;
        editItemOption.value.index = index;
        editItemOption.value.width = target.parentElement.offsetWidth;
        inputTagValue.value = getListItemId(item);

        nextTick(execContainerClick);
      }
    };

    const clearInputTag = () => {
      (refTagInputElement.value as HTMLInputElement).value = '';
      inputTagValue.value = '';
    };

    const lastTagWidth = 40;
    const closeTagWidth = 30;
    const inputWidth = 12;
    const hiddenItemCount = ref(0);
    const hiddenItemIndex = ref([]);

    const calcItemEllipsis = () => {
      if (isInputFocused.value) {
        return Promise.resolve(true);
      }

      hiddenItemCount.value = 0;
      hiddenItemIndex.value.length = 0;
      hiddenItemIndex.value = [];

      return new Promise(resolve => {
        nextTick(() => {
          const { offsetHeight, scrollHeight, offsetWidth } = (refRootElement.value ?? {}) as HTMLElement;
          if (offsetHeight < scrollHeight) {
            const childList = Array.from(refTagInputContainer.value.children ?? []);
            let width = 0;
            const avalibleWidth = offsetWidth - closeTagWidth - inputWidth;

            childList.forEach((item: HTMLElement, index) => {
              if (!item.hasAttribute('data-ignore-element')) {
                const itemWidth = item.offsetWidth;
                width += itemWidth;

                if (avalibleWidth - width < lastTagWidth + inputWidth) {
                  hiddenItemIndex.value.push(index);
                  hiddenItemCount.value++;
                }
              }
            });

            resolve(true);
          }
        });
      });
    };

    const handleDocumentClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      handleEditInputBlur();

      if (
        refRootElement.value.contains(target) ||
        refChoiceList.value.contains(target) ||
        focusFixedElement?.contains(target)
      ) {
        if (refRootElement.value.contains(target) && !popInstance.isShown()) {
          popInstance.show(refRootElement.value);
          return;
        }

        return;
      }

      fixedInstance.hide();
      popInstance.hide();
      clearInputTag();

      isInputFocused.value = false;
      calcItemEllipsis();
    };

    const handleContainerClick = (e: MouseEvent) => {
      stopDefaultPrevented(e);
      nextTick(execContainerClick);
    };

    watch(
      () => [props.value],
      () => {
        if (isInputFocused.value) {
          execContainerClick();
          autoFocusInput();
          return;
        }

        calcItemEllipsis().then(() => {
          autoFocusInput();
        });
      },
    );

    onMounted(() => {
      containerWidth.value = refRootElement.value.offsetWidth;
      document.addEventListener('click', handleDocumentClick);
      calcItemEllipsis();
    });

    onBeforeUnmount(() => {
      document.removeEventListener('click', handleDocumentClick);
      popInstance?.uninstallInstance();
      fixedInstance?.uninstallInstance();
      fixedInstance = null;
    });

    const rootStyle = computed(() => {
      return {
        '--bklog-choice-min-width': props.minWidth ?? '120px',
        '--bklog-choice-max-width': props.maxWidth ?? '120px',
        '--bklog-choice-max-height': props.maxHeight ?? '100%',
        '--bklog-choice-min-height': props.minHeight,
      };
    });

    const valueTagStyle = computed(() => {
      return {
        maxWidth: props.valueTagMaxWidth,
      };
    });

    const renderInputTag = () => {
      return (
        <div
          class={[
            'bklog-choice-list-item',
            'custom-tag',
            {
              'is-hidden': inputTagValue.value.length === 0 || editItemOption.value.index !== null,
              'is-active': activeItemIndex.value === null,
            },
          ]}
          onClick={handleCustomTagClick}
        >
          {t('生成“{n}”标签', { n: inputTagValue.value })}
        </div>
      );
    };

    const renderOptionList = () => {
      return optionList.value.map(({ item, selected }) => (
        <div
          class={['bklog-choice-list-item', { 'is-selected': selected }]}
          onClick={() => handleOptionItemClick(item)}
        >
          {slots.item?.(item) ?? getListItemName(item)}
        </div>
      ));
    };

    const getValueContext = (item, index) => {
      if (editItemOption.value.index === index) {
        return (
          <input
            style={{ width: `${editItemOption.value.width}px` }}
            data-bklog-choice-value-edit-input
            class='bklog-choice-value-edit-input'
            value={getListItemId(item)}
          ></input>
        );
      }

      return [
        <span
          class='bklog-choice-value-span'
          onClick={e => handleSelectedValueItemclick(e, item, index)}
        >
          {getListItemName(item)}
        </span>,
        <i
          class='bklog-icon bklog-close'
          data-bklog-choice-item-del={index}
          onClick={e => handleDeleteItemClick(e, item)}
        ></i>,
      ];
    };

    const renderValueList = () => {
      return valueWithInputList.value.map((item: any, index) => {
        if (item?.__tag_input__) {
          return (
            <li
              key='__tag_input__'
              data-ignore-element='true'
              data-w-hidden='false'
              data-item-index={index}
              class={[
                'bklog-choice-value-item tag-input',
                {
                  'is-hidden':
                    editItemOption.value.index !== null || (hiddenItemCount.value > 0 && !isInputFocused.value),
                },
              ]}
            >
              <input
                type='text'
                ref={refTagInputElement}
                style={tagInputStyle.value}
                data-bklog-choice-text-input
                onInput={handleInputValueChange}
                onKeyup={handleInputKeyup}
              ></input>
            </li>
          );
        }

        return (
          <li
            class={['bklog-choice-value-item', { 'is-edit-item': editItemOption.value.index === index }]}
            style={valueTagStyle.value}
            data-w-hidden={hiddenItemIndex.value.includes(index) && !isInputFocused.value}
            data-item-index={index}
            key={getItemKey(item, index)}
          >
            {getValueContext(item, index)}
          </li>
        );
      });
    };

    return () => (
      <div
        class={[
          'bklog-tag-choice-container',
          {
            'is-focus': isInputFocused.value,
            'has-hidden-item': hiddenItemCount.value > 0,
            'is-focus-fixed': props.foucsFixed,
          },
        ]}
        onClick={handleContainerClick}
        style={rootStyle.value}
        ref={refRootElement}
      >
        <span
          ref={refFixedPointerElement}
          class='hidden-fixed-pointer'
        ></span>
        <ul
          class={['bklog-tag-choice-input', { 'is-focus': isInputFocused.value }]}
          ref={refTagInputContainer}
          style={rootStyle.value}
          data-placeholder={placeholderText.value}
        >
          {renderValueList()}
          <li
            data-ignore-element
            class={['bklog-choice-value-item', { 'is-hidden': hiddenItemCount.value === 0 || isInputFocused.value }]}
          >
            +{hiddenItemCount.value}
          </li>
        </ul>
        <span class={[dropdownIconName.value, 'bklog-choice-dropdown-icon']}></span>
        <span
          class='bk-icon icon-close-circle-shape delete-all-tags'
          onClick={handleDeleteAllClick}
        ></span>
        <div v-show={false}>
          <div
            class='bklog-tag-choice-list'
            ref={refChoiceList}
            style={containerStyle.value}
          >
            {renderInputTag()}
            <div
              class='bklog-choice-value-container'
              v-bkloading={{ isLoading: props.loading, size: 'small' }}
            >
              {renderOptionList()}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
