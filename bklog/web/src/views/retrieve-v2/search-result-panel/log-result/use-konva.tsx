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
import { onBeforeMount, onBeforeUnmount } from 'vue';

import Konva from 'konva';
import * as PIXI from 'pixi.js';

import CanvasText from './canvas-text';

import type { WordListItem } from '../../../../hooks/use-text-segmentation';

export default ({ onSegmentClick }) => {
  const konvaInstance: {
    backgroundStage: Konva.Stage | null;
    backgroundLayer: Konva.Layer | null;
    frontStage: Konva.Stage | null;
    frontActionLayer: Konva.Layer | null;
  } = {
    backgroundStage: null,
    backgroundLayer: null,
    frontStage: null,
    frontActionLayer: null,
  };

  const pixiInstance: {
    style: PIXI.TextStyle;
    app: PIXI.Application;
    container: HTMLDivElement;
  } = {
    style: undefined,
    app: undefined,
    container: undefined,
  };

  let fontFamily: string;
  const fontSize = 12;
  const lineHeight = 20 / 12;
  const rowHeight = lineHeight * fontSize;
  const webgl = false;

  let tempText: CanvasText;
  let boxWidth = 0;
  let boxHeight = 0;

  let wordList: WordListItem[];
  let hoverItem: any;
  let textContainer: HTMLDivElement;
  let isDisposeing = false;

  const containerBounds = { x: 0, y: 0, width: 0, height: 0 };

  const getTempText = () => {
    if (!tempText) {
      tempText = new CanvasText({ fontSize, fontFamily });
    }
    return tempText;
  };

  const appendColorText = (word: WordListItem) => {
    const fillColor = word.isMark ? 'rgb(255, 255, 0)' : 'rgba(255, 255, 255, 0.99)';
    const offsetTop = (rowHeight - fontSize) / 2;

    if (webgl) {
      const graphic = new PIXI.Graphics();

      graphic.filletRect(word.left, word.top + offsetTop, word.width, fontSize, 1);
      graphic.fill({
        color: fillColor,
      });
      pixiInstance.app.stage.addChild(graphic);

      const text = new PIXI.Text({
        x: word.left,
        y: word.top + offsetTop,
        text: word.text,
        style: new PIXI.TextStyle({
          fontWeight: '500',
          fill: '#3a84ff',
          fontFamily,
          fontSize,
          lineHeight,
        }),
      });

      pixiInstance.app.stage.addChild(text);
      return;
    }

    const konvaRect = new Konva.Rect({
      x: word.left,
      y: word.top + offsetTop,
      width: word.width,
      height: fontSize,
      fill: fillColor,
    });

    const konvaText = new Konva.Text({
      text: word.text,
      x: word.left,
      y: word.top + 1,
      fontSize,
      fontFamily,
      fill: '#3a84ff',
      lineHeight,
    });

    konvaInstance.frontActionLayer.add(konvaRect);
    konvaInstance.frontActionLayer.add(konvaText);
  };

  const updateContainerBounds = () => {
    const { x, y, width, height } = textContainer.getBoundingClientRect();
    Object.assign(containerBounds, { x, y, width, height });
    boxWidth = width;
    boxHeight = height;
  };

  const isWordInClickSection = (item: WordListItem, pointer) => {
    const { left, top, width } = item;
    const bottom = top + 20;
    const right = left + width;
    const { x, y } = pointer;
    return left <= x && top <= y && bottom >= y && right >= x;
  };

  const getDistance = (x1, y1, x2, y2) => {
    return Math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2);
  };

  const getClickOffset = (item: WordListItem, pointer) => {
    if (item.split?.length) {
      const [leftItem, rightItem] = item.split;
      const leftDistance = Math.abs(
        getDistance(leftItem.left + leftItem.width / 2, leftItem.top + fontSize / 2, pointer.x, pointer.y),
      );
      const rightDistance = Math.abs(
        getDistance(rightItem.left + rightItem.width / 2, rightItem.top + fontSize / 2, pointer.x, pointer.y),
      );

      if (leftDistance < rightDistance) {
        return { offsetX: 0, offsetY: leftItem.top + fontSize - pointer.y + 2 };
      }

      return { offsetX: 0, offsetY: rightItem.top + fontSize - pointer.y + 2 };
    }

    return { offsetX: 0, offsetY: item.top + fontSize - pointer.y + 2 };
  };

  const getPointerByMouseEvent = (e: MouseEvent) => {
    const { x, y } = e;
    return { x: x - containerBounds.x, y: y - containerBounds.y };
  };

  const isSelectionCurrentNode = () => {
    const selection = window.getSelection();
    if (!selection?.isCollapsed) {
      const node = selection.focusNode.parentElement;
      return node === konvaInstance.frontStage.container().parentElement.querySelector('.static-text');
    }

    return false;
  };

  const handleTextBoxClick = evt => {
    if (isSelectionCurrentNode()) {
      return;
    }

    const pointer = getPointerByMouseEvent(evt);
    const word = wordList.find(item => {
      if (!item.isCursorText) {
        return false;
      }

      if (item.split?.length) {
        return item.split.some(child => isWordInClickSection(child, pointer));
      }

      return isWordInClickSection(item, pointer);
    });

    if (word?.isCursorText && word?.text) {
      const { offsetX, offsetY } = getClickOffset(word, pointer);
      onSegmentClick?.(evt, word?.text, { offsetX, offsetY });
    }
  };

  const initKonvaInstance = (
    backgroundContainer: HTMLDivElement,
    frontContainer: HTMLDivElement,
    width: number,
    height: number,
    family: string,
  ) => {
    fontFamily = family;
    boxWidth = width;
    boxHeight = height;
    textContainer = frontContainer.parentElement.querySelector('.static-text');

    konvaInstance.backgroundStage = new Konva.Stage({
      container: backgroundContainer,
      width,
      height,
    });

    pixiInstance.container = frontContainer;

    if (!webgl) {
      konvaInstance.frontStage = new Konva.Stage({
        container: frontContainer,
        width,
        height,
      });
    }

    initLayer();
    updateContainerBounds();
  };

  const setRect = (width?: number, height?: number) => {
    if (width) {
      konvaInstance.backgroundStage.width(width);
      konvaInstance.frontStage?.width?.(width);
    }

    if (height) {
      konvaInstance.backgroundStage.height(height);
      konvaInstance.frontStage?.height?.(height);
    }

    updateContainerBounds();
  };

  const getRangePosition = (startIndex: number, endIndex: number) => {
    const range = document.createRange();

    range.setStart(textContainer.firstChild, startIndex);
    range.setEnd(textContainer.firstChild, endIndex);

    const { x, y } = range.getBoundingClientRect();
    const top = Math.floor((y - containerBounds.y) / rowHeight) * rowHeight;
    const offsetLeft = x - containerBounds.x;

    return { top, left: offsetLeft };
  };

  // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
  const getWrapText = (item: WordListItem, leftWidth: number) => {
    const box = getTempText();
    const chars = item.text.split('');
    const leftText: any[] = [];
    let width = 0;
    let bufferWidth = 0;
    while (width < leftWidth) {
      const char = chars.shift();
      bufferWidth = box.width(char);
      width += bufferWidth;
      if (width < leftWidth) {
        bufferWidth = 0;
        leftText.push(char);
      } else if (width - leftWidth < 1) {
        const startIndex = item.startIndex + leftText.length;
        const { top } = getRangePosition(startIndex, startIndex + 1);

        if (top === item.top) {
          bufferWidth = 0;
          leftText.push(char);
        } else {
          chars.unshift(char);
        }
      } else {
        chars.unshift(char);
      }
    }

    const leftTextWidth = width > bufferWidth ? width - bufferWidth : 0;
    return [
      {
        text: leftText.join(''),
        width: leftTextWidth <= leftWidth ? leftTextWidth : leftWidth,
        renderWidth: leftTextWidth,
      },
      { text: chars.join('') },
    ];
  };

  const resetSplitWordWrap = (leftText: WordListItem, rightText: WordListItem) => {
    while (leftText.text.length > 0 && rightText.left > 0) {
      rightText.text = leftText.text.slice(-1) + rightText.text;
      leftText.text = leftText.text.slice(0, -1);

      const text = getTempText();
      const width = text.width(rightText.text);
      const diff = width - rightText.width;
      leftText.width -= diff;
      rightText.left -= diff;
      rightText.width = width;
    }
  };

  // biome-ignore-start lint/style/noParameterAssign: reason
  const resetWordWrapPositon = (
    textNode,
    itemList: WordListItem[],
    currentIndex: number,
    originLeft: number,
    updateLeft = true,
    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
  ) => {
    const item = itemList[currentIndex];

    if (!item || isDisposeing) {
      return originLeft;
    }

    const getDiffWidth = (diffL, diffT, target: WordListItem) => {
      if (target.top < diffT) {
        return diffL + containerBounds.width - target.left;
      }

      return diffL - target.left;
    };

    if (item.split) {
      const [leftText, rightText] = item.split;
      const offsetXIndex = leftText?.text?.length ?? 0;

      // biome-ignore lint/nursery/noShadow: reason
      const { top, left } = getRangePosition(item.startIndex + offsetXIndex, item.endIndex);

      if (left > rightText.left || top > rightText.top) {
        const diffWidth = getDiffWidth(left, top, rightText);
        rightText.left = left;
        rightText.top = top;

        resetSplitWordWrap(leftText, rightText);

        if (updateLeft) {
          originLeft += diffWidth;
        }

        if (leftText.text.length === 0) {
          item.left = rightText.left;
          item.top = rightText.top;
          item.line = rightText.line;
          item.split = undefined;
        }

        if (item.left > 0) {
          return resetWordWrapPositon(textNode, itemList, currentIndex - 1, originLeft, false);
        }
      }

      return originLeft;
    }

    // const range = document.createRange();
    // 这里获取分词最后一个字符
    // 用于判定当前分词是否因为系统渲染进行了换行操作
    const offsetXIndex = item.text.length > 1 ? item.text.length - 1 : 0;
    const { top, left } = getRangePosition(item.startIndex + offsetXIndex, item.endIndex);

    // 说明整个分词在当前行，此时只需要偏移计算量
    // 继续回溯上一个分词
    if (top === item.top) {
      const rightText = item.text.slice(-1);
      const text = getTempText();
      const rightTxtWidth = text.width(rightText);
      const wordLeft = left - item.width + rightTxtWidth;

      // 实际位置肯定会比计算位置靠后
      // 此时需要整个分词向后偏移差异量
      if (wordLeft > item.left) {
        if (updateLeft) {
          originLeft = originLeft + wordLeft - item.left;
        }

        item.left = wordLeft;
        return resetWordWrapPositon(textNode, itemList, currentIndex - 1, originLeft, false);
      }

      return originLeft;
    }

    // 分词在系统渲染后被强制换行了
    if (top > item.top) {
      const rightText = item.text.slice(-1);
      const text = getTempText();
      const width = text.width(rightText);

      if (updateLeft) {
        originLeft = boxWidth - item.left + originLeft + left;
      }

      item.split = [
        {
          ...item,
          text: item.text.slice(0, -1),
          width: item.width - width,
          top: item.top,
        },
        {
          ...item,
          text: rightText,
          width,
          left,
          top,
        },
      ].filter(newItem => newItem.text.length > 0);

      if (item.split?.length > 1) {
        // biome-ignore lint/nursery/noShadow: reason
        const [leftText, rightText] = item.split;
        resetSplitWordWrap(leftText, rightText);
      }

      if (item.split?.length === 1) {
        item.top = item.split[0].top;
        item.left = item.split[0].left;
        item.width = item.split[0].width;
        item.split = undefined;

        if (item.left === 0) {
          return originLeft;
        }
      }

      return resetWordWrapPositon(textNode, itemList, currentIndex - (item.split ? 0 : 1), originLeft, false);
    }

    return originLeft;
  };
  // biome-ignore-end lint/style/noParameterAssign: reason

  const getRequestAnimationFrame = () => {
    return window.requestAnimationFrame;
  };

  // biome-ignore lint/nursery/noShadow: reason
  const computeWordListPosition = (list?: WordListItem[], next?: (list?: WordListItem[]) => void) => {
    wordList = list;
    return new Promise<WordListItem[]>(resolve => {
      getRequestAnimationFrame()(() => {
        let left = 0;
        // 换行产生的偏移量
        const offsetWidth = 0;
        // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
        (wordList || []).forEach((item, index) => {
          if (isDisposeing) {
            return;
          }

          if (item.left === undefined && item.top === undefined) {
            const isWrap = /^(\n|\r)$/.test(item.text);
            const isEmpty = /^\t$/.test(item.text) && /^(\n|\r)$/.test(wordList[index - 1]?.text ?? '');

            let width = 0;

            if (!isWrap) {
              const box = getTempText();
              width = box.width(item.text);
            }

            const line = Math.floor(left / boxWidth);

            Object.assign(item, {
              left: (left % boxWidth) + offsetWidth,
              top: line * fontSize * lineHeight,
              width,
              line,
            });

            left += width;

            if (isWrap && item.left > 0) {
              left = left + boxWidth - item.left;
            }

            if (isEmpty) {
              left -= width;
              item.width = 0;
            }

            const nextLine = Math.floor(left / boxWidth);

            // 用于判定边界极限情况
            // 如果增加当前分词宽后，总宽度计算出来结果行数改变 & 有多余宽度才能判定分词被换行
            // 如果正好换行没有多余宽度，说明当前分词正好在换行位置
            const nextLineOffset = left % boxWidth;

            // 分词在换行被截断
            if (nextLine > line && nextLineOffset > 0 && item.width > 0 && item.text?.length) {
              const diffWidth = left % boxWidth;
              const [leftText, rightText] = getWrapText(item, width - diffWidth);
              rightText.width = item.width - leftText.width;
              left = boxWidth * nextLine + width - leftText.width;

              if (rightText.text === '' && rightText.width > 0) {
                left -= rightText.width;
              }

              item.split = [
                {
                  text: leftText.text,
                  isMark: item.isMark,
                  isCursorText: item.isCursorText,
                  left: item.left,
                  top: item.top,
                  width: leftText.width,
                  renderWidth: leftText.renderWidth,
                  line,
                },
                {
                  text: rightText.text,
                  isMark: item.isMark,
                  isCursorText: item.isCursorText,
                  left: 0,
                  top: item.top + fontSize * lineHeight,
                  width: width - leftText.width,
                  line: nextLine,
                },
              ].filter(newItem => newItem.width > 0 && item.text !== '');

              if (item.split.length === 1) {
                item.left = item.split[0].left;
                item.top = item.split[0].top;
                item.width = item.split[0].width;
                item.line = item.split[0].line;
                item.renderWidth = item.split[0].renderWidth;
                item.split = undefined;
              }

              left = resetWordWrapPositon(textContainer.firstChild, wordList, index, left, true);
            }
          }
        });

        next?.(wordList);
        resolve(wordList);
      });
    });
  };

  const validateWordPosition = () => {
    const lastWord = wordList.at(-1);
    const { top, left } = getRangePosition(lastWord.startIndex, lastWord.endIndex);
    return top === lastWord.top && left === lastWord.left;
  };

  const setMarkWordRect = (item: WordListItem) => {
    // 创建一个背景矩形
    const rect = new Konva.Rect({
      x: item.left,
      y: item.top + (fontSize * lineHeight - fontSize) / 2,
      width: item.width,
      height: fontSize,
      fill: 'rgb(255, 255, 0)',
    });

    konvaInstance.backgroundLayer?.add(rect);
  };

  const setHighlightWords = (words: WordListItem[]) => {
    if (isDisposeing) {
      return;
    }

    const filterWords = words.filter(item => item.isMark);
    for (const item of filterWords) {
      if (isDisposeing || item.left === undefined) {
        continue;
      }

      if (item.split?.length) {
        item.split.forEach(setMarkWordRect);
      } else {
        setMarkWordRect(item);
      }
    }
  };

  let mouseenterTimer: any;

  const handleTextBoxMouseenter = evt => {
    mouseenterTimer && clearTimeout(mouseenterTimer);
    mouseenterTimer = setTimeout(() => {
      if (webgl && !pixiInstance.app) {
        pixiInstance.app = new PIXI.Application();
        pixiInstance.app.init({
          width: boxWidth,
          height: boxHeight,
          backgroundAlpha: 0,
          autoDensity: true,
          resolution: window.devicePixelRatio * 2,
          antialias: true,
        });
        pixiInstance.container.appendChild(pixiInstance.app.canvas);
      }
      updateContainerBounds();
      handleTextBoxMousemove(evt);
    }, 100);
  };

  // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
  const handleTextBoxMousemove = evt => {
    if (webgl && !pixiInstance.app) {
      return;
    }

    if (isSelectionCurrentNode()) {
      // 如果有文本被选中此时跳过后续高亮逻辑
      konvaInstance.frontActionLayer?.destroyChildren();
      return;
    }

    const pointer = getPointerByMouseEvent(evt);
    const validateWordRect = item => {
      const { left, top, width } = item;
      const bottom = top + 20;
      const right = left + width;
      const { x, y } = pointer;
      return left <= x && top <= y && bottom >= y && right >= x;
    };
    const word = wordList.find(item => {
      if (item.split?.length) {
        return item.split.some(child => validateWordRect(child));
      }

      return validateWordRect(item);
    });

    if (word?.isCursorText && hoverItem !== word) {
      hoverItem = word;
      if (webgl) {
        pixiInstance.app?.stage?.removeChildren(0, pixiInstance.app.stage.children.length);
      } else {
        konvaInstance.frontActionLayer?.destroyChildren();
      }

      if (word.split?.length) {
        for (const item of word.split) {
          appendColorText(item);
        }

        return;
      }

      appendColorText(word);
    }
  };

  const handleTextBoxMouseleave = () => {
    mouseenterTimer && clearTimeout(mouseenterTimer);

    if (webgl) {
      pixiInstance.app?.stop?.();
      pixiInstance.app?.stage?.removeChildren?.(0, pixiInstance.app.stage.children.length);
      pixiInstance.app?.destroy?.({ removeView: true });
      pixiInstance.app = undefined;
      return;
    }

    konvaInstance.frontActionLayer?.destroyChildren();
  };

  const initLayer = () => {
    konvaInstance.backgroundLayer = new Konva.Layer({ id: 'backgroundLayer' });
    konvaInstance.backgroundStage.add(konvaInstance.backgroundLayer);

    if (!webgl) {
      konvaInstance.frontActionLayer = new Konva.Layer({ id: 'frontActionLayer' });
      konvaInstance.frontStage.add(konvaInstance.frontActionLayer);
    }
  };

  const getLines = () => {
    const lines = boxHeight / 20;
    return lines;
  };

  const events = {
    mouseenter: handleTextBoxMouseenter,
    mousemove: handleTextBoxMousemove,
    mouseleave: handleTextBoxMouseleave,
    click: handleTextBoxClick,
  };

  const fireEvent = (type: string, e: MouseEvent) => {
    requestAnimationFrame(() => {
      events[type]?.(e);
    });
  };

  const destroyKonvaInstance = () => {
    konvaInstance.frontActionLayer?.destroyChildren();
    konvaInstance.frontActionLayer?.destroy();
    konvaInstance.frontActionLayer = null;

    konvaInstance.backgroundLayer?.destroyChildren();
    konvaInstance.backgroundLayer?.destroy();
    konvaInstance.backgroundLayer = null;

    konvaInstance.frontStage?.destroyChildren();
    konvaInstance.frontStage?.destroy();
    konvaInstance.frontStage = null;

    konvaInstance.backgroundStage?.destroyChildren();
    konvaInstance.backgroundStage?.destroy();

    konvaInstance.backgroundStage = null;
  };

  const resetWordList = () => {
    for (const item of wordList) {
      item.split = undefined;
      item.left = undefined;
      item.top = undefined;
    }

    destroyKonvaInstance();
  };

  onBeforeUnmount(() => {
    isDisposeing = true;
    destroyKonvaInstance();
    tempText?.destroy();
    tempText = undefined;
  });

  onBeforeMount(() => {
    isDisposeing = false;
  });

  return {
    setRect,
    getLines,
    fireEvent,
    setHighlightWords,
    initKonvaInstance,
    computeWordListPosition,
    updateContainerBounds,
    resetWordList,
    initLayer,
    validateWordPosition,
  };
};
