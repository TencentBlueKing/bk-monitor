import Konva from 'konva';
import { WordListItem } from '../../../../hooks/use-text-segmentation';
export default () => {
  const konvaInstance: {
    stage: null | Konva.Stage;
    layer: null | Konva.Layer;
    actionLayer: null | Konva.Layer;
    textBox: null | Konva.Text;
  } = {
    stage: null,
    layer: null,
    textBox: null,
    actionLayer: null,
  };

  let fontFamily;
  const fontSize = 12;
  const lineHeight = 20 / 12;
  let tempText;

  let wordList: WordListItem[];

  const initKonvaInstance = (container, width, height, family) => {
    fontFamily = family;
    konvaInstance.stage = new Konva.Stage({
      container,
      width,
      height,
    });

    konvaInstance.layer = new Konva.Layer();
    konvaInstance.actionLayer = new Konva.Layer();

    konvaInstance.textBox = new Konva.Text({
      x: 0,
      y: 0,
      fontSize,
      fontFamily: family ?? 'Microsoft YaHei',
      lineHeight,
      fill: '#000000',
      wrap: 'char',
      width,
      // height,
    });

    konvaInstance.layer.add(konvaInstance.textBox);
    konvaInstance.stage.add(konvaInstance.actionLayer);

    konvaInstance.stage.add(konvaInstance.layer);
  };

  const setText = (text: string, append = true) => {
    if (append) {
      konvaInstance.textBox.text(konvaInstance.textBox.text() + text);
      konvaInstance.stage.height(konvaInstance.textBox.height());
      return;
    }

    konvaInstance.textBox.text(text);
  };

  const setRect = (width?: number, height?: number) => {
    if (width) {
      konvaInstance.stage.width(width);
    }

    if (height) {
      konvaInstance.stage.height(height);
    }
  };

  const getTempText = () => {
    if (!tempText) {
      tempText = new Konva.Text({
        x: 0,
        y: 0,
        fontSize,
        fontFamily,
        lineHeight,
        fill: '#000000',
      });
    }
    return tempText;
  };

  const computeWordPosition = (word: WordListItem) => {
    if (word.left && word.top && word.width) {
      return;
    }

    const box = getTempText();
    const text = konvaInstance.textBox.text();
    const boxWidth = konvaInstance.textBox.width();
    const startIndex = word.startIndex;
    const leftText = text.slice(0, startIndex);

    box.text(leftText);
    const width = box.width();
    const left = width % boxWidth;
    const top = Math.floor(width / boxWidth) * fontSize * lineHeight;

    box.text(word.text);
    const rectWidth = box.width();
    Object.assign(word, { left, top, width: rectWidth });
  };

  const computeWordListPosition = (list: WordListItem[]) => {
    wordList = list;
    return new Promise((resolve, reject) => {
      wordList.forEach(item => {
        computeWordPosition(item);
      });

      resolve(wordList);
    });
  };

  const setHighlightWords = (words: WordListItem[]) => {
    words
      .filter(item => item.isMark)
      .forEach(item => {
        computeWordPosition(item);
        // 创建一个背景矩形
        const rect = new Konva.Rect({
          x: item.left,
          y: item.top + 1,
          width: item.width,
          height: fontSize + 2,
          fill: 'rgb(255, 255, 0)',
        });

        konvaInstance.actionLayer.add(rect);
      });
  };

  const getLines = () => {
    const lines = konvaInstance.textBox.height() / 20;
    return lines;
  };

  const hanldeTextBoxMousemove = evt => {
    const pointer = konvaInstance.stage.getPointerPosition();
    const word = wordList.find(item => {
      return item.le;
    });
    // const
    // const charIndex = textBox.getSelectionStartFromPointer(pointer);
    // if (charIndex !== -1) {
    //   const wordBoundary = findWordBoundary(charIndex);
    //   if (wordBoundary?.isCursorText) {
    //     // 重置所有字符样式
    //     textBox.setSelectionStyles({ fill: '#313238' }, 0, textBox.text.length);
    //     // 高亮当前分词
    //     textBox.setSelectionStyles({ fill: '#3a84ff' }, wordBoundary.startIndex, wordBoundary.endIndex);
    //   }
    // }
    // canvasInstance.renderAll();
  };

  const hanldeTextBoxClick = evt => {
    // const pointer = canvasInstance.getPointer(evt.e);
    // const wordIndex = textBox.getSelectionStartFromPointer(pointer);
    // if (wordIndex !== -1) {
    //   const wordBoundary = findWordBoundary(wordIndex);
    //   if (wordBoundary?.text) {
    //     textSegmentInstance?.getCellClickHandler(evt.e, wordBoundary.text);
    //   }
    // }
  };

  const handleTextBoxMouseout = () => {
    // textBox.setSelectionStyles({ fill: '#313238' }, 0, textBox.text.length);
    // canvasInstance.renderAll();
  };

  const setMounted = () => {
    konvaInstance.stage.on('mousemove', hanldeTextBoxMousemove);
    konvaInstance.stage.on('mouseout', handleTextBoxMouseout);
    konvaInstance.stage.on('click', hanldeTextBoxClick);
  };

  return {
    setText,
    setRect,
    getLines,
    setHighlightWords,
    initKonvaInstance,
    computeWordListPosition,
  };
};
