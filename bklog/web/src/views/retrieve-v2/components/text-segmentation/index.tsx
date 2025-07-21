import { ref, computed, watch, defineComponent, Ref, onMounted, onBeforeUnmount, onBeforeMount, nextTick } from 'vue';

import { isNestedField } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import UseTextSegmentation from '@/hooks/use-text-segmentation';
import { debounce } from 'lodash';

import { setScrollLoadCell } from '@/hooks/hooks-helper';
import { WordListItem } from '@/hooks/use-text-segmentation';
import RetrieveHelper from '@/views/retrieve-helper';

import './index.scss';

export default defineComponent({
  props: {
    field: { type: Object, required: true },
    data: { type: Object },
    content: { type: [String, Number, Boolean], required: true },
    forceAll: {
      type: Boolean,
      default: false,
    },
    autoWidth: {
      type: Boolean,
      default: false,
    },
    isWrap: {
      type: Boolean,
      default: false,
    },
    isLimitExpandView: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['menu-click'],
  setup(props, { emit }) {
    const refContent: Ref<HTMLDivElement> = ref();
    const { $t } = useLocale();
    const showAll = ref(false);
    const refSegmentContent: Ref<HTMLElement> = ref();

    const rootStyle = computed(() => {
      return {
        maxHeight: `${props.isLimitExpandView || showAll.value ? '50vh' : '68px'}`,
      };
    });

    // 是否有纵向滚动条
    const hasOverflowY = ref(false);

    const btnText = computed(() => {
      if (showAll.value) {
        return ` ...${$t('收起')}`;
      }

      return ` ...${$t('更多')}`;
    });

    const handleMenuClick = event => {
      emit('menu-click', event);
    };

    let textSegmentInstance = new UseTextSegmentation({
      onSegmentClick: handleMenuClick,
      options: {
        content: props.content,
        field: props.field,
        data: props.data,
      },
    });

    let wordList: WordListItem[];
    let renderMoreItems: (size?, next?) => void = null;

    const getTagName = item => {
      if (item.isMark) {
        return 'mark';
      }

      if (/^(br|\n)$/.test(item.text)) {
        return 'br';
      }

      return 'span';
    };

    const handleClickMore = e => {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();
      showAll.value = !showAll.value;

      renderMoreItems?.();
    };

    const handleTextSegmentClick = (e: MouseEvent) => {
      return textSegmentInstance.getTextCellClickHandler(e);
    };

    let isNestedValue = false; // data-depth
    const setWordList = () => {
      const fieldName = props.field.field_name;
      const fieldKeys = fieldName.split('.');
      isNestedValue = isNestedField(fieldKeys, props.data);
      wordList = textSegmentInstance.getChildNodes(isNestedValue);
    };

    const debounceUpdateWidth = debounce(() => {
      hasOverflowY.value = false;
      if (refContent.value) {
        const { offsetHeight, scrollHeight } = refContent.value;
        hasOverflowY.value = offsetHeight < scrollHeight;
      }
    });

    onBeforeMount(() => {
      setWordList();
    });

    let removeScrollEventFn = null;
    let cellScrollInstance: {
      setListItem: (size?: number, next?: () => void) => void;
      removeScrollEvent: () => void;
      reset: (list: WordListItem[]) => void;
    };

    const setWordSegmentRender = () => {
      const { setListItem, removeScrollEvent } = cellScrollInstance;
      renderMoreItems = setListItem;
      removeScrollEventFn = removeScrollEvent;

      // 这里面有做前500的分词，后面分段数据都是按照200分段，差不多一行左右的宽度文本
      // 这里默认渲染前500跟分词 + 10 - 20行溢出
      setListItem(props.isLimitExpandView ? 550 : 300);
      debounceUpdateWidth();
    };

    onMounted(() => {
      hasOverflowY.value = false;
      nextTick(() => {
        if (refSegmentContent.value) {
          refSegmentContent.value.setAttribute('is-nested-value', `${isNestedValue}`);
        }
        cellScrollInstance = setScrollLoadCell(
          wordList,
          refContent.value,
          refSegmentContent.value,
          (item: WordListItem) => {
            const child = document.createElement(getTagName(item));
            child.classList.add(item.isCursorText ? 'valid-text' : 'others-text');

            if (item.isBlobWord) {
              child.innerHTML = item.text?.length ? item.text : '""';
              return child;
            }

            child.textContent = item.text?.length ? item.text : '""';
            return child;
          }
        );

        setWordSegmentRender();

        nextTick(() => RetrieveHelper.highlightElement(refSegmentContent.value));
      });
    });

    onBeforeUnmount(() => {
      removeScrollEventFn?.();
    });

    useResizeObserve(refContent, debounceUpdateWidth);

    const renderSegmentList = () => {
      return (
        <div
          ref={refContent}
          style={rootStyle.value}
          class='field-value bklog-word-segment'
          data-field-name={props.field.field_name}
          onClick={handleTextSegmentClick}
        >
          <span
            ref={refSegmentContent}
            class='segment-content'
          ></span>
        </div>
      );
    };

    watch(
      () => props.isLimitExpandView,
      () => {
        renderMoreItems();
      }
    );

    watch(
      () => props.content,
      () => {
        textSegmentInstance = new UseTextSegmentation({
          onSegmentClick: handleMenuClick,
          options: {
            content: props.content,
            field: props.field,
            data: props.data,
          },
        });
        setWordList();
        const { reset } = cellScrollInstance;
        reset(wordList);
        setWordSegmentRender();
      }
    );

    const showMoreAction = computed(() => hasOverflowY.value || (showAll.value && !props.isLimitExpandView));
    const getMoreAction = () => {
      if (showMoreAction.value && !props.isLimitExpandView) {
        return (
          <span
            class={['btn-more-action', `word-text`, 'is-show']}
            onClick={handleClickMore}
          >
            {btnText.value}
          </span>
        );
      }
    };

    return () => (
      <div
        class={[
          'bklog-v3-wrapper',
          'bklog-text-segment',
          'bklog-root-field',
          {
            'is-wrap-line': props.isWrap,
            'is-inline': !props.isWrap,
            'is-show-long': props.isLimitExpandView,
            'is-expand-all': showAll.value,
          },
        ]}
      >
        {renderSegmentList()}
        {getMoreAction()}
      </div>
    );
  },
});
