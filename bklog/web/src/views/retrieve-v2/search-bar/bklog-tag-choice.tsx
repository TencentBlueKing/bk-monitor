import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, Ref, ref } from 'vue';
import PopInstanceUtil from '../../../global/pop-instance-util';
import './bklog-tag-choice.scss';
import useResizeObserve from '../../../hooks/use-resize-observe';
import useLocale from '../../../hooks/use-locale';
import { getCharLength } from '../../../common/util';

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
      default: '100px',
    },
    value: {
      type: [String, Number, Array],
      default: '',
    },
  },
  model: {
    prop: 'value',
    event: 'update:value',
  },
  emits: ['change', 'update:value'],
  setup(props, { slots, emit }) {
    const isListOpended = ref(false);
    const refRootElement: Ref<HTMLElement> = ref(null);
    const refChoiceList: Ref<HTMLElement> = ref(null);
    const refTagInputElement: Ref<HTMLElement> = ref(null);
    const inputTagValue = ref('');
    const tagInputIndex = ref(null);
    const containerWidth = ref(0);
    const activeItemIndex = ref(null);

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
      return props.list ?? [];
    });

    const handleInputValueChange = (e: any) => {
      const input = e.target;
      inputTagValue.value = input.value;
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
     * Enter 当前键入值
     * @param e
     */
    const handleInputKeyup = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        const targetValue = [...valueList.value.map(v => getListItemId(v)), inputTagValue.value];
        emit('update:value', targetValue);
        emit('change', targetValue);
        clearInputTag();

        nextTick(() => {
          console.log('---props', props.value);
        });
      }
    };

    const handleCustomTagClick = () => {
      const targetValue = [...valueList.value.map(v => getListItemId(v)), inputTagValue.value];
      emit('update:value', targetValue);
      emit('change', targetValue);
      nextTick(() => {
        console.log('---props', props.value);
      });
      clearInputTag();
    };

    const handleDocumentClick = (e: MouseEvent) => {
      if (
        refRootElement.value.contains(e.target as HTMLElement) ||
        refChoiceList.value.contains(e.target as HTMLElement)
      ) {
        return;
      }

      popInstance.hide(120);
      clearInputTag();
    };

    onMounted(() => {
      containerWidth.value = refRootElement.value.offsetWidth;
      document.addEventListener('click', handleDocumentClick);
    });

    onBeforeUnmount(() => {
      document.removeEventListener('click', handleDocumentClick);
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
      return optionList.value.map(item => (
        <div class='bklog-choice-list-item'>{slots.item?.(item) ?? getListItemName(item)}</div>
      ));
    };

    const renderValueList = () => {
      return valueWithInputList.value.map((item: any) => {
        if (item?.__tag_input__) {
          return (
            <span
              key='__tag_input__'
              class='bklog-choice-value-item tag-input'
            >
              <input
                type='text'
                ref={refTagInputElement}
                style={tagInputStyle.value}
                onInput={handleInputValueChange}
                onKeyup={handleInputKeyup}
              ></input>
            </span>
          );
        }

        return (
          <span
            class='bklog-choice-value-item'
            key={getListItemId(item)}
          >
            {getListItemName(item)}
            <i class='bklog-icon bklog-close'></i>
          </span>
        );
      });
    };

    return () => (
      <div
        class='bklog-tag-choice-container'
        onClick={handleContainerClick}
        ref={refRootElement}
      >
        <div class='bklog-tag-choice-input'>{renderValueList()}</div>
        <span class={[dropdownIconName.value, 'bklog-choice-dropdown-icon']}></span>
        <div v-show={false}>
          <div
            class='bklog-tag-choice-list'
            ref={refChoiceList}
            style={containerStyle.value}
          >
            {renderInputTag()}
            {renderList()}
          </div>
        </div>
      </div>
    );
  },
});
