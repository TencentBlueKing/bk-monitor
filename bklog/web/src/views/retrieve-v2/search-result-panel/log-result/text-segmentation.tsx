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
import { ref, computed, inject, watch, defineComponent, Ref, onMounted, onBeforeUnmount, onBeforeMount } from 'vue';

import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import UseTextSegmentation from '@/hooks/use-text-segmentation';
import { fabric } from 'fabric';
import { debounce } from 'lodash';

import { WordListItem } from '../../../../hooks/use-text-segmentation';
import useKonva from './use-konva';

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
    const refCanvas: Ref<HTMLDivElement> = ref();
    const refFrontCanvas: Ref<HTMLDivElement> = ref();

    const fontFamily = 'Menlo,Monaco,Consolas,Courier,"PingFang SC","Microsoft Yahei",monospace';
    const store = useStore();
    const { $t } = useLocale();
    const tableCellCache: WeakMap<
      object,
      WeakMap<object, Ref<{ showAll: boolean; textBox: fabric.Textbox; pageIndex: number }>>
    > = inject('tableCellCache');

    if (props.data && props.field) {
      if (!tableCellCache.has(props.data)) {
        tableCellCache.set(props.data, new WeakMap());
      }

      if (!tableCellCache.get(props.data).has(props.field)) {
        tableCellCache.get(props.data).set(props.field, ref({ showAll: false, textBox: null, pageIndex: 0 }));
      }
    }

    const getCachedValue = (attr: string, defaultValue?: any) => {
      return tableCellCache?.get(props.data)?.get(props.field)?.value?.[attr] ?? defaultValue;
    };

    let containerWidth = 0;

    const showAll = ref(getCachedValue('showAll', false));

    const refSegmentContent: Ref<HTMLElement> = ref();
    const textLineCount = ref(0);

    const formatText = ref('');

    const isWrap = computed(() => store.state.tableLineIsWrap);
    const isLimitExpandView = computed(() => store.state.isLimitExpandView || props.forceAll);
    const hasEllipsis = computed(() => !isLimitExpandView.value && textLineCount.value > 3);
    const btnText = computed(() => {
      if (showAll.value) {
        return ` ...${$t('收起')}`;
      }

      return ` ...${$t('更多')}`;
    });

    const handleMenuClick = event => {
      emit('menu-click', event);
    };

    const textSegmentInstance = new UseTextSegmentation({
      onSegmentClick: handleMenuClick,
      options: {
        content: props.content,
        field: props.field,
        data: props.data,
      },
    });

    const { initKonvaInstance, setRect, setHighlightWords, computeWordListPosition, fireEvent } = useKonva({
      onSegmentClick: (e, value) => {
        textSegmentInstance?.getCellClickHandler(e, value);
      },
    });

    let wordList: WordListItem[];
    // let pageIndex = getCachedValue('pageIndex', 0);
    let isDispose = false;
    // const pageSize = 400;

    // const getNextList = (size?) => {
    //   const startIndex = pageIndex * (size ?? pageSize);
    //   const endIndex = (pageIndex + 1) * (size ?? pageSize);
    //   if (startIndex <= wordList.length - 1) {
    //     pageIndex++;
    //     return wordList.slice(startIndex, endIndex);
    //   }

    //   return [];
    // };

    // const getNextText = (list?, size?) => {
    //   return (list ?? getNextList(size)).map(({ text }) => text).join('');
    // };

    /**
     * 初始化前三行数据
     */
    // const setNextText = (max?) => {
    //   if (mountedAllTag) {
    //     return;
    //   }

    //   textLineCount.value = getLines();
    //   const maxLength = isLimitExpandView.value || showAll.value ? max : 3;
    //   if (textLineCount.value <= maxLength) {
    //     const nextList = getNextList();
    //     if (nextList.length > 0) {
    //       const nextValue = getNextText(nextList);
    //       setHighlightWords(nextList);
    //       textLineCount.value = getLines();
    //       if (!isDispose) {
    //         requestAnimationFrame(() => {
    //           setNextText(max);
    //         });
    //       }
    //     }
    //   }
    // };

    const getWidth = wordList => {
      if (props.autoWidth && wordList.length === 1) {
        const context = document.createElement('canvas').getContext('2d');
        context.font = `12px ${fontFamily}`;
        const textWidth = context.measureText(wordList[0].text).width;
        return textWidth;
      }

      return refContent.value.offsetWidth;
    };

    const initKonvaTextBox = () => {
      const width = getWidth(wordList);
      refCanvas.value.setAttribute('width', `${width}`);
      initKonvaInstance(refCanvas.value, refFrontCanvas.value, width, refContent.value.offsetHeight, fontFamily);
      computeWordListPosition(wordList).then(list => {
        setHighlightWords(list);
      });
    };

    let textSegmentIndex = 0;
    const textSegmentPageSize = 50;
    const setTextSegmentChildNodes = (maxLength = 4) => {
      const fragment = new DocumentFragment();
      textLineCount.value = Math.ceil(refContent.value.scrollHeight / 20);

      if (textLineCount.value >= maxLength) {
        return;
      }

      const stepRun = (size?) => {
        if (textSegmentIndex >= 500) {
          const text = wordList
            .slice(textSegmentIndex)
            .map(item => item.text)
            .join('');

          const child = document.createElement('span');
          child.classList.add('others-text');
          child.innerText = text;
          fragment.appendChild(child);
          refSegmentContent.value.append(fragment);
          return;
        }

        const endIndex = textSegmentIndex + (size ?? textSegmentPageSize);
        if (textSegmentIndex < wordList.length) {
          wordList.slice(textSegmentIndex, endIndex).forEach(item => {
            const child = document.createElement(getTagName(item));
            child.classList.add(item.isCursorText ? 'valid-text' : 'others-text');
            child.innerText = item.text;
            fragment.appendChild(child);
          });
          textSegmentIndex = endIndex;
          refSegmentContent.value.append(fragment);

          requestAnimationFrame(() => {
            if (refContent.value) {
              textLineCount.value = Math.ceil(refContent.value.scrollHeight / 20);
              if (textLineCount.value < maxLength && !isDispose) {
                stepRun(textLineCount.value > 3 ? 500 : undefined);
              }
            }
          });
        }
      };

      stepRun();
    };

    const setMoreLines = () => {
      // if (getSegmentRenderType() === 'canvas' && showAll.value) {
      //   setNextText(Number.MAX_SAFE_INTEGER);
      // }

      if (getSegmentRenderType() === 'text') {
        let max = Number.MAX_SAFE_INTEGER;
        if (!showAll.value) {
          max = 4;
          pageIndex = 0;
          refSegmentContent.value.innerHTML = '';
        }
        setTextSegmentChildNodes(max);
      }
    };

    const handleClickMore = e => {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();
      showAll.value = !showAll.value;

      setMoreLines();
    };

    const getSegmentRenderType = () => {
      if (wordList.length < 10) {
        return 'text';
      }

      return 'canvas';
    };

    const getTagName = item => {
      if (item.isMark) {
        return 'mark';
      }

      if (/^(br|\n)$/.test(item.text)) {
        return 'br';
      }

      return 'span';
    };

    const handleTextSegmentClick = (e: MouseEvent) => {
      return textSegmentInstance.getTextCellClickHandler(e);
    };

    const setMounted = () => {
      const maxLength = isLimitExpandView.value || showAll.value ? Number.MAX_SAFE_INTEGER : 4;
      if (getSegmentRenderType() === 'canvas') {
        initKonvaTextBox();
      }

      if (getSegmentRenderType() === 'text') {
        setTextSegmentChildNodes(maxLength);
      }
    };

    onBeforeMount(() => {
      isDispose = false;
      wordList = textSegmentInstance.getChildNodes();
      formatText.value = textSegmentInstance.formatValue();
    });

    onMounted(() => {
      containerWidth = refContent.value.offsetWidth;
      setMounted();
    });

    onBeforeUnmount(() => {
      isDispose = true;
      if (tableCellCache?.get(props.data)?.get(props.field)) {
        Object.assign(tableCellCache.get(props.data).get(props.field)?.value, {
          showAll: showAll.value,
        });
      }
    });

    watch(
      () => [isLimitExpandView.value],
      () => {
        if (isLimitExpandView.value) {
          textSegmentIndex = 0;
          setMoreLines();
        }
      },
    );

    const debounceUpdateWidth = debounce(() => {
      if (!refContent.value) {
        return;
      }

      if (containerWidth !== refContent.value.offsetWidth) {
        containerWidth = refContent.value.offsetWidth;

        if (getSegmentRenderType() === 'canvas') {
          mountedAllTag = false;
          pageIndex = 0;
          const width = refContent.value.offsetWidth;
          setRect(width);
          // setNextText();
        }

        if (getSegmentRenderType() === 'text') {
          setTextSegmentChildNodes();
        }
      }
    });

    useResizeObserve(refContent, debounceUpdateWidth);

    const renderSegmentList = () => {
      if (getSegmentRenderType() === 'canvas') {
        return [
          <div
            ref={refCanvas}
            class='canvas-konva-background'
          ></div>,
          <div
            class='static-text'
            onClick={e => fireEvent('click', e)}
            onMouseenter={e => fireEvent('mouseenter', e)}
            onMouseleave={e => fireEvent('mouseleave', e)}
            onMousemove={e => fireEvent('mousemove', e)}
          >
            {formatText.value}
          </div>,
          <div
            ref={refFrontCanvas}
            class='canvas-konva-front'
          ></div>,
        ];
      }

      return (
        <span
          class='field-value'
          data-field-name={props.field.field_name}
          onClick={handleTextSegmentClick}
        >
          <span
            ref={refSegmentContent}
            class='segment-content'
          ></span>
        </span>
      );
    };

    const renderBody = () => {
      return (
        <div
          ref={refContent}
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
          <span
            class={[
              'btn-more-action',
              `word-${getSegmentRenderType()}`,
              { 'is-show': hasEllipsis.value || showAll.value },
            ]}
            onClick={handleClickMore}
          >
            {btnText.value}
          </span>
        </div>
      );
    };

    return { renderBody };
  },
  render() {
    return this.renderBody();
  },
});
