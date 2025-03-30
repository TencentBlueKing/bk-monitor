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
     * 当绑定的数据改变时，销毁当前弹出内容，根据Vue渲染出来的结果进行弹出内容的更新
     */
    const updateFiexedInstanceContent = () => {
      nextTick(() => {
        destroyFixedContent();
        setFixedValueContent();
        fixedInstance.setProps({
          content: focusFixedElement,
        });

        popInstance.initInistance(focusFixedElement);
        popInstance.getTippyInstance().show();
      });
    };

    const handleDeleteItemClick = (e, val) => {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const targetValue = new Array();
      valueList.value.forEach(v => {
        if (v !== val) {
          targetValue.push(getListItemId(v));
        }
      });

      emit('change', targetValue);
      refTagInputElement.value?.focus();
    };

    const handleValueItemClick = val => {
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
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        emitValue(inputTagValue.value);
        clearInputTag();
      }
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

    const destroyFixedContent = () => {
      focusFixedElement?.removeEventListener('click', handleFixedValueListClick);

      const input = focusFixedElement?.querySelector('[data-bklog-choice-text-input]') as HTMLInputElement;
      input?.removeEventListener('keyup', handleFixedValueInputKeyup);
      input?.removeEventListener('input', cloneFixedInputChange);
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
          input.addEventListener('input', cloneFixedInputChange);
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

    // const handleValueItemclick = (e, item, index) => {
    //   if (!item.__tag_input__) {
    //     const target = e.target as HTMLElement;
    //     editItemOption.value.index = index;
    //     editItemOption.value.width = target.parentElement.offsetWidth;
    //   }
    // };

    const handleCustomTagClick = (e: MouseEvent) => {
      emitValue(inputTagValue.value);
      clearInputTag();
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();
    };

    const cloneFixedInputChange = (e: InputEvent) => {
      handleInputValueChange(e);
      const target = e.target as HTMLInputElement;
      const charLen = Math.max(getCharLength(inputTagValue.value), 1);
      target.style.setProperty('width', `${charLen * INPUT_MIN_WIDTH}px`);
    };

    const handleFixedValueListClick = (e: MouseEvent) => {
      const target = e?.target as HTMLElement;

      if (target?.classList.contains('bklog-choice-value-span')) {
        const index = target.parentElement.getAttribute('data-item-index');

        editItemOption.value.index = parseInt(index);
        editItemOption.value.width = target.offsetWidth;
        updateFiexedInstanceContent();
        return;
      }

      const editInput = focusFixedElement.querySelector('[data-bklog-choice-value-edit-input]') as HTMLInputElement;
      if (editInput) {
        editInput.focus();
        return;
      }

      const input = focusFixedElement.querySelector('[data-bklog-choice-text-input]') as HTMLInputElement;
      input?.focus();
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
        offset: [10, 0],
        onShown: () => {
          const input = focusFixedElement?.querySelector('[data-bklog-choice-text-input]') as HTMLInputElement;
          input?.focus();
          fixedInstance.setIsShowing(false);
        },
        onHidden: () => {
          destroyFixedContent();
        },
      },
    });

    const cloneFixedItem = () => {
      fixedInstance.show(refFixedPointerElement.value, true, true);
      nextTick(() => {
        popInstance.show(focusFixedElement ?? refRootElement.value);
      });
    };

    const handleContainerClick = () => {
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

    const documentClickEventResolver = (e: MouseEvent) => {
      const target = e.target as HTMLElement;

      if (target.classList.contains('bklog-choice-value-span')) {
      }

      if (focusFixedElement?.contains(target)) {
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
            target.parentElement?.remove();
          }
        }
      }
    };

    const handleDocumentClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (
        refRootElement.value.contains(target) ||
        refChoiceList.value.contains(target) ||
        focusFixedElement?.contains(target)
      ) {
        documentClickEventResolver(e);
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

    watch(
      () => [props.value],
      () => {
        if (isInputFocused.value) {
          handleContainerClick();
          return;
        }

        calcItemEllipsis();
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
            { 'is-hidden': inputTagValue.value.length === 0, 'is-active': activeItemIndex.value === null },
          ]}
          onClick={handleCustomTagClick}
        >
          {t('生成“{n}”标签', { n: inputTagValue.value })}
        </div>
      );
    };

    const renderList = () => {
      return optionList.value.map(({ item, selected }) => (
        <div
          class={['bklog-choice-list-item', { 'is-selected': selected }]}
          onClick={() => handleValueItemClick(item)}
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
          // onClick={e => handleValueItemclick(e, item, index)}
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
                { 'is-hidden': hiddenItemCount.value > 0 && !isInputFocused.value },
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
          class='bklog-tag-choice-input'
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
              {renderList()}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
