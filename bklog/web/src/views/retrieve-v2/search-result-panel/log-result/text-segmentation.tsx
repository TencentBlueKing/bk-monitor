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
    const refContent: Ref<HTMLElement> = ref();
    const refCanvas: Ref<HTMLElement> = ref();

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

    let canvasInstance: fabric.Canvas;
    let textBox: fabric.Textbox;
    let wordList: any[];
    let pageIndex = getCachedValue('pageIndex', 0);
    let mountedAllTag = false;
    let isDispose = false;
    const pageSize = 400;

    const getNextList = (size?) => {
      const startIndex = pageIndex * (size ?? pageSize);
      const endIndex = (pageIndex + 1) * (size ?? pageSize);
      if (startIndex <= wordList.length - 1) {
        pageIndex++;
        return wordList.slice(startIndex, endIndex);
      }

      mountedAllTag = endIndex >= wordList.length;
      return [];
    };

    const getNextText = (list?, size?) => {
      return (list ?? getNextList(size)).map(({ text }) => text).join('');
    };

    // 根据字符索引查找分词边界
    const findWordBoundary = charIndex => {
      for (let word of wordList) {
        if (charIndex >= word.startIndex && charIndex < word.endIndex) {
          return word;
        }
      }
      return null;
    };

    const setMarkText = list => {
      list.forEach(item => {
        const { isMark } = item;
        if (isMark) {
          textBox.setSelectionStyles({ textBackgroundColor: 'rgb(255, 255, 0)' }, item.startIndex, item.endIndex);
        }
      });
    };

    const updateCanvas = () => {
      canvasInstance.setHeight(Math.max(textBox.height + 4, 40));
      canvasInstance.renderAll();
    };

    /**
     * 初始化前三行数据
     */
    const setNextText = (max?) => {
      if (mountedAllTag || !textBox) {
        return;
      }

      textLineCount.value = textBox.textLines.length;
      const maxLength = isLimitExpandView.value || showAll.value ? max : 3;
      if (textLineCount.value <= maxLength) {
        const nextList = getNextList();
        if (nextList.length > 0) {
          const nextValue = getNextText(nextList);
          const insertionPoint = textBox.text.length;
          const endPoint = insertionPoint + nextValue.length;

          textBox.insertChars(nextValue, undefined, insertionPoint, endPoint);
          setMarkText(nextList);
          textLineCount.value = textBox.textLines.length;
          updateCanvas();
          if (!isDispose) {
            requestAnimationFrame(() => {
              setNextText(max);
            });
          }
        }
      }
    };

    const getWidth = wordList => {
      if (props.autoWidth && wordList.length === 1) {
        const context = document.createElement('canvas').getContext('2d');
        context.font = `12px ${fontFamily}`;
        const textWidth = context.measureText(wordList[0].text).width;
        return textWidth;
      }

      return refContent.value.offsetWidth;
    };

    const hanldeTextBoxMousemove = evt => {
      const pointer = canvasInstance.getPointer(evt.e);
      const charIndex = textBox.getSelectionStartFromPointer(pointer);

      if (charIndex !== -1) {
        const wordBoundary = findWordBoundary(charIndex);

        if (wordBoundary?.isCursorText) {
          // 重置所有字符样式
          textBox.setSelectionStyles({ fill: '#313238' }, 0, textBox.text.length);
          // 高亮当前分词
          textBox.setSelectionStyles({ fill: '#3a84ff' }, wordBoundary.startIndex, wordBoundary.endIndex);
        }
      }
      canvasInstance.renderAll();
    };

    const hanldeTextBoxClick = evt => {
      const pointer = canvasInstance.getPointer(evt.e);
      const wordIndex = textBox.getSelectionStartFromPointer(pointer);

      if (wordIndex !== -1) {
        const wordBoundary = findWordBoundary(wordIndex);
        if (wordBoundary?.text) {
          textSegmentInstance?.getCellClickHandler(evt.e, wordBoundary.text);
        }
      }
    };

    const handleTextBoxMouseout = () => {
      textBox.setSelectionStyles({ fill: '#313238' }, 0, textBox.text.length);
      canvasInstance.renderAll();
    };

    const initFabricTextBox = (maxLength = 4) => {
      const width = getWidth(wordList);
      refCanvas.value.setAttribute('width', `${width}`);
      const nextListItems = getNextList();
      canvasInstance = new fabric.Canvas(refCanvas.value);

      if (!textBox) {
        textBox = new fabric.Textbox(getNextText(nextListItems), {
          fontSize: 12,
          fontFamily,
          width,
          wrapWidth: width,
          lineHeight: 1.6, // 行距
          left: 0,
          top: 4,
          selectable: false,
          editable: false, // 禁止编辑
          hoverCursor: 'pointer',
          backgroundColor: '',
          fill: '#313238',
          fontWeight: 'normal',
          splitByGrapheme: true, // 自动换行
          padding: 0,
          opacity: 0.9,
        });
      }

      // 鼠标移动事件
      textBox.on('mousemove', hanldeTextBoxMousemove);

      // 鼠标离开事件
      textBox.on('mouseout', handleTextBoxMouseout);

      // 鼠标点击事件
      textBox.on('mousedown', hanldeTextBoxClick);

      setMarkText(nextListItems);
      canvasInstance.add(textBox);
      textLineCount.value = textBox.textLines.length;

      updateCanvas();
      requestAnimationFrame(() => {
        setNextText(maxLength);
      });
    };

    const destroyFabricInstance = () => {
      if (!canvasInstance) {
        return;
      }

      if (textBox) {
        textBox.off('mousemove', hanldeTextBoxMousemove);
        textBox.off('mouseout', handleTextBoxMouseout);
        textBox.off('mousedown', hanldeTextBoxClick);
        textBox = undefined;
      }

      canvasInstance.clear();
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
      if (getSegmentRenderType() === 'fabric' && showAll.value) {
        setNextText(Number.MAX_SAFE_INTEGER);
      }

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
      // if (wordList.length < 100) {
      //   return 'text';
      // }

      // if (wordList.length < 3000) {
      //   return 'fabric';
      // }

      return 'text';
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
      if (getSegmentRenderType() === 'fabric') {
        initFabricTextBox(maxLength);
      }

      if (getSegmentRenderType() === 'text') {
        setTextSegmentChildNodes(maxLength);
      }
    };

    onBeforeMount(() => {
      isDispose = false;
      wordList = textSegmentInstance.getChildNodes();
    });

    onMounted(() => {
      containerWidth = refContent.value.offsetWidth;
      setMounted();
    });

    onBeforeUnmount(() => {
      isDispose = true;
      destroyFabricInstance();
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

        if (getSegmentRenderType() === 'fabric') {
          mountedAllTag = false;
          pageIndex = 0;
          const width = refContent.value.offsetWidth;
          canvasInstance.setWidth(width);
          textBox.text = '';
          textBox.set({ width, wrapWidth: width });
          setNextText();
        }

        if (getSegmentRenderType() === 'text') {
          setTextSegmentChildNodes();
        }
      }
    });

    useResizeObserve(refContent, debounceUpdateWidth);

    const renderSegmentList = () => {
      if (getSegmentRenderType() === 'fabric') {
        return <canvas ref={refCanvas}></canvas>;
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
