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
    maxWidth: {
      type: String,
      default: '560px',
    },
    maxHeight: {
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

    const inputTagValue = ref('');
    const tagInputIndex = ref(null);
    const containerWidth = ref(0);
    const activeItemIndex = ref(null);

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

    const handleContainerClick = () => {
      popInstance.show(refRootElement.value);
      refTagInputElement.value?.focus();
    };

    const clearInputTag = () => {
      (refTagInputElement.value as HTMLInputElement).value = '';
      inputTagValue.value = '';
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

    const handleDeleteItemClick = val => {
      const targetValue = new Array();
      valueList.value.forEach(v => {
        if (v !== val) {
          targetValue.push(getListItemId(v));
        }
      });

      emit('change', targetValue);
    };

    const handleValueItemClick = val => {
      emitValue(getListItemId(val));
    };

    const handleInputFocus = isFocus => {
      isInputFocused.value = isFocus;
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

    const handleCustomTagClick = () => {
      emitValue(inputTagValue.value);
      clearInputTag();
    };

    const handleDocumentClick = (e: MouseEvent) => {
      if (
        refRootElement.value.contains(e.target as HTMLElement) ||
        refChoiceList.value.contains(e.target as HTMLElement)
      ) {
        if (refRootElement.value.contains(e.target as HTMLElement) && !popInstance.isShown()) {
          popInstance.show(refRootElement.value);
          return;
        }

        return;
      }

      popInstance.hide();
      clearInputTag();
    };

    const lastTagWidth = 40;
    const closeTagWidth = 30;
    const inputWidth = 12;
    const hiddenItemCount = ref(0);
    const hiddenItemIndex = ref([]);

    const calcItemEllipsis = () => {
      hiddenItemCount.value = 0;
      hiddenItemIndex.value.length = 0;
      hiddenItemIndex.value = [];

      nextTick(() => {
        const { offsetHeight, scrollHeight, offsetWidth } = (refRootElement.value ?? {}) as HTMLElement;
        if (offsetHeight < scrollHeight) {
          const childList = Array.from(refTagInputContainer.value.children ?? []);
          let width = 0;
          const maxLength = childList.length - 1;
          const avalibleWidth = offsetWidth - closeTagWidth - inputWidth;

          childList.forEach((item: HTMLElement, index) => {
            if (!item.hasAttribute('data-ignore-element')) {
              const itemWidth = item.offsetWidth;
              width += itemWidth;

              if (avalibleWidth - width < lastTagWidth + inputWidth) {
                hiddenItemIndex.value.push(index);
                hiddenItemCount.value++;
                // if (hiddenItemCount.value === 1) {
                //   // 如果不是最后一个元素需要考虑 +n 位置的预留
                //   if (maxLength > index) {
                //     const diffWidth = offsetWidth - width + itemWidth;

                //     // 考虑回溯上一个元素，保证预留足够空间展示 +n 位置的字符
                //     if (diffWidth < lastTagWidth) {
                //       hiddenItemCount.value++;
                //       hiddenItemIndex.value.push(index - 1);
                //     }
                //   }
                // }
              }
            }
          });
        }
      });
    };

    watch(
      () => [props.value],
      () => {
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
    });

    const rootStyle = computed(() => {
      return {
        maxWidth: props.maxWidth,
        maxHeight: props.maxHeight,
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

    const renderValueList = () => {
      return valueWithInputList.value.map((item: any, index) => {
        if (item?.__tag_input__) {
          return (
            <li
              key='__tag_input__'
              data-ignore-element='true'
              data-w-hidden='false'
              data-item-index={index}
              class={['bklog-choice-value-item tag-input', { 'is-hidden': hiddenItemCount.value > 0 }]}
            >
              <input
                type='text'
                ref={refTagInputElement}
                style={tagInputStyle.value}
                onBlur={() => handleInputFocus(false)}
                onFocus={() => handleInputFocus(true)}
                onInput={handleInputValueChange}
                onKeyup={handleInputKeyup}
              ></input>
            </li>
          );
        }

        return (
          <li
            class='bklog-choice-value-item'
            style={valueTagStyle.value}
            data-w-hidden={hiddenItemIndex.value.includes(index)}
            data-item-index={index}
            key={getItemKey(item, index)}
          >
            {getListItemName(item)}
            <i
              class='bklog-icon bklog-close'
              onClick={() => handleDeleteItemClick(item)}
            ></i>
          </li>
        );
      });
    };

    return () => (
      <div
        class={['bklog-tag-choice-container', { 'is-focus': isInputFocused.value }]}
        onClick={handleContainerClick}
        style={rootStyle.value}
        ref={refRootElement}
      >
        <ul
          class='bklog-tag-choice-input'
          ref={refTagInputContainer}
          data-placeholder={placeholderText.value}
        >
          {renderValueList()}
          <li
            data-ignore-element
            class={['bklog-choice-value-item', { 'is-hidden': hiddenItemCount.value === 0 }]}
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
