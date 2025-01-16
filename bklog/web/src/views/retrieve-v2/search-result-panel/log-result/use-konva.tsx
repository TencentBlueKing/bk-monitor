import Konva from 'konva';
import { WordListItem } from '../../../../hooks/use-text-segmentation';
export default ({ onSegmentClick }) => {
  const konvaInstance: {
    stage: null | Konva.Stage;
    layer: null | Konva.Layer;
    actionLayer: null | Konva.Layer;
    colorLayer: null | Konva.Layer;
    textBox: null | Konva.Text;
  } = {
    stage: null,
    layer: null,
    textBox: null,
    actionLayer: null,
    colorLayer: null,
  };

  let fontFamily;
  const fontSize = 12;
  const lineHeight = 20 / 12;
  let tempText;

  let wordList: WordListItem[];
  let hoverItem;

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

  const appendColorText = (word: WordListItem) => {
    const fillColor = word.isMark ? 'rgb(255, 255, 0)' : 'rgb(255, 255, 255)';
    const rect = new Konva.Rect({
      x: word.left,
      y: word.top + (fontSize * lineHeight - fontSize) / 2,
      width: word.width,
      height: fontSize,
      fill: fillColor,
    });

    const text = new Konva.Text({
      fontSize,
      lineHeight,
      fontFamily,
      x: word.left,
      y: word.top,
      text: word.text,
      fill: '#3a84ff',
    });

    konvaInstance.colorLayer.add(rect);
    konvaInstance.colorLayer.add(text);
  };

  let isMouseDown = false;
  let startPosition = { x: 0, y: 0 };

  const drawSelectionText = () => {
    const pointer = konvaInstance.stage.getPointerPosition();
    const rectList = [];
    const height = fontSize * lineHeight;
    const boxWidth = konvaInstance.textBox.width();

    const left = Math.min(startPosition.x, pointer.x);
    const top = Math.min(startPosition.y, pointer.y);
    const bottom = Math.max(startPosition.y, pointer.y);
    const right = Math.max(startPosition.x, pointer.x);

    const startLine = Math.ceil(top / height);
    const endLine = Math.ceil(bottom / height);

    if (startLine !== endLine) {
      rectList.push({
        x: left,
        y: (startLine - 1) * height,
        width: boxWidth - left,
        height,
        lineNumber: startLine - 1,
      });

      rectList.push({
        x: 0,
        y: (endLine - 1) * height,
        width: right,
        height,
        lineNumber: endLine - 1,
      });

      new Array(endLine - startLine - 1).fill('').forEach((_, index) => {
        rectList.push({
          x: 0,
          y: (startLine + index) * height,
          width: boxWidth,
          height,
          lineNumber: startLine + index,
        });
      });
    }

    if (startLine === endLine) {
      rectList.push({
        x: left,
        y: (startLine - 1) * height,
        width: right - left,
        height,
        lineNumber: startLine - 1,
      });
    }

    konvaInstance.colorLayer.removeChildren();
    rectList.forEach(item => {
      const { x, y, width, height } = item;
      const rect = new Konva.Rect({
        x,
        y,
        width,
        height,
        fill: '#1768EF',
      });

      konvaInstance.colorLayer.add(rect);
    });
  };

  const hanldeTextBoxMousemove = ({ evt }) => {
    if (isMouseDown) {
      requestAnimationFrame(drawSelectionText);
      return;
    }

    const pointer = konvaInstance.stage.getPointerPosition();
    const word = wordList.find(item => {
      const { left, top, width } = item;
      const bottom = top + 20;
      const right = left + width;
      const { x, y } = pointer;
      return left <= x && top <= y && bottom >= y && right >= x;
    });

    if (word?.isCursorText && hoverItem !== word) {
      hoverItem = word;
      konvaInstance.colorLayer.destroyChildren();
      if (word.split?.length) {
        word.split.forEach(item => {
          appendColorText(item);
        });

        return;
      }

      appendColorText(word);
    }
  };

  const hanldeTextBoxClick = ({ evt }) => {
    const pointer = konvaInstance.stage.getPointerPosition();
    const word = wordList.find(item => {
      const { left, top, width } = item;
      const bottom = top + 20;
      const right = left + width;
      const { x, y } = pointer;
      return left <= x && top <= y && bottom >= y && right >= x;
    });

    if (word?.isCursorText && word?.text) {
      onSegmentClick?.(evt, word?.text);
    }
  };

  const hanldeStageMounsedown = () => {
    isMouseDown = true;
    startPosition = konvaInstance.stage.getPointerPosition();
  };

  const handleTextBoxMouseout = () => {
    if (!isMouseDown) {
      konvaInstance.colorLayer.destroyChildren();
    }
  };

  const handleStageMouseup = () => {
    isMouseDown = false;
  };

  const setMounted = () => {
    konvaInstance.stage.on('mousemove', hanldeTextBoxMousemove);
    konvaInstance.stage.on('mouseleave', handleTextBoxMouseout);
    konvaInstance.stage.on('click', hanldeTextBoxClick);
    // konvaInstance.stage.on('mousedown', hanldeStageMounsedown);
    // konvaInstance.stage.on('mouseup', handleStageMouseup);
  };

  const initKonvaInstance = (container, width, height, family) => {
    fontFamily = family;
    konvaInstance.stage = new Konva.Stage({
      container,
      width,
      height,
    });

    konvaInstance.layer = new Konva.Layer();
    konvaInstance.actionLayer = new Konva.Layer();
    konvaInstance.colorLayer = new Konva.Layer();

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
    konvaInstance.stage.add(konvaInstance.colorLayer);

    setMounted();
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

  const getWrapText = (text: string, leftWidth: number) => {
    const box = getTempText();
    const chars = text.split('');
    const leftText = [];
    let width = 0;
    let bufferWidth = 0;
    while (width < leftWidth) {
      const char = chars.shift();
      box.text(char);
      bufferWidth = box.width();
      width += bufferWidth;
      if (width < leftWidth) {
        bufferWidth = 0;
        leftText.push(char);
      } else {
        chars.unshift(char);
      }
    }

    return [{ text: leftText.join(''), width: width - bufferWidth }, { text: chars.join('') }];
  };

  const computeWordListPosition = (list: WordListItem[]) => {
    wordList = list;
    const boxWidth = konvaInstance.textBox.width();

    return new Promise((resolve, reject) => {
      let left = 0;
      // 换行产生的偏移量
      let offsetWidth = 0;
      let preWidth = 0;
      wordList.forEach(item => {
        const box = getTempText();
        preWidth = left;
        box.text(item.text);
        const width = box.width();
        const line = Math.floor(left / boxWidth);

        Object.assign(item, {
          left: (left % boxWidth) + offsetWidth,
          top: line * fontSize * lineHeight,
          width,
          line,
        });

        left = left + width;
        const nextLine = Math.floor(left / boxWidth);

        // 分词在换行被截断
        if (nextLine > line) {
          const diffWidth = left - boxWidth;
          const [leftText, rightText] = getWrapText(item.text, width - diffWidth);
          offsetWidth = boxWidth - (preWidth % boxWidth) - leftText.width;

          item.split = [
            {
              text: leftText.text,
              isMark: item.isMark,
              isCursorText: item.isCursorText,
              left: item.left,
              top: item.top,
              width: leftText.width,
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
          ];
        }
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
          y: item.top + (fontSize * lineHeight - fontSize) / 2,
          width: item.width,
          height: fontSize,
          fill: 'rgb(255, 255, 0)',
        });

        konvaInstance.actionLayer.add(rect);
      });
  };

  const getLines = () => {
    const lines = konvaInstance.textBox.height() / 20;
    return lines;
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
