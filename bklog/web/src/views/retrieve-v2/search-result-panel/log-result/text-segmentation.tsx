/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { ref, computed, watch, defineComponent, Ref, onMounted, onBeforeUnmount, onBeforeMount } from 'vue';

import { isNestedField } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import UseTextSegmentation from '@/hooks/use-text-segmentation';
import { debounce } from 'lodash';

import { setScrollLoadCell } from '../../../../hooks/hooks-helper';
import { WordListItem } from '../../../../hooks/use-text-segmentation';

import './text-segmentation.scss';
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
  },
  emits: ['menu-click'],
  setup(props, { emit }) {
    const refContent: Ref<HTMLDivElement> = ref();

    const store = useStore();
    const { $t } = useLocale();

    const showAll = ref(false);

    const refSegmentContent: Ref<HTMLElement> = ref();
    const isWrap = computed(() => store.state.tableLineIsWrap);
    const isLimitExpandView = computed(() => store.state.isLimitExpandView || props.forceAll);
    const rootStyle = computed(() => {
      return {
        maxHeight: `${isLimitExpandView.value || showAll.value ? '50vh' : '66px'}`,
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
    let renderMoreItems: () => void = null;

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
      setListItem: (size?: number) => void;
      removeScrollEvent: () => void;
      reset: (list: WordListItem[]) => void;
    };

    const setWordSegmentRender = () => {
      const { setListItem, removeScrollEvent } = cellScrollInstance;
      renderMoreItems = setListItem;
      removeScrollEventFn = removeScrollEvent;

      // 这里面有做前500的分词，后面分段数据都是按照200分段，差不多一行左右的宽度文本
      // 这里默认渲染前500跟分词 + 10 - 20行溢出
      setListItem(isLimitExpandView.value ? 550 : 300);
      debounceUpdateWidth();
    };

    onMounted(() => {
      hasOverflowY.value = false;
      refSegmentContent.value.setAttribute('is-nested-value', `${isNestedValue}`);
      cellScrollInstance = setScrollLoadCell(
        wordList,
        refContent.value,
        refSegmentContent.value,
        (item: WordListItem) => {
          const child = document.createElement(getTagName(item));
          child.classList.add(item.isCursorText ? 'valid-text' : 'others-text');
          child.innerText = item.text;
          return child;
        },
      );

      setWordSegmentRender();
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
      () => isLimitExpandView.value,
      () => {
        renderMoreItems();
      },
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
      },
    );

    const showMoreAction = computed(() => hasOverflowY.value || (showAll.value && !isLimitExpandView.value));
    const getMoreAction = () => {
      if (showMoreAction.value) {
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
          'bklog-text-segment',
          'bklog-root-field',
          {
            'is-wrap-line': isWrap.value,
            'is-inline': !isWrap.value,
            'is-show-long': isLimitExpandView.value,
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
