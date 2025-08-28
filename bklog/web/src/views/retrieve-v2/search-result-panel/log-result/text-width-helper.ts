import { debounce } from 'lodash-es';
let canvasInstance = undefined;
let canvasContext = undefined;

const delayDestroyCanvasInstance = debounce(() => {
  canvasInstance = undefined;
  canvasContext = undefined;
}, 1000);

export default (text, maxWidth, font) => {
  if (!canvasInstance) {
    canvasInstance = document.createElement('canvas');
    canvasContext = canvasInstance.getContext('2d');
    canvasContext.font = font;
  }

  const getTextWidth = char => {
    const metrics = canvasContext.measureText(char);
    return metrics.width;
  };

  const truncateTextWithCanvas = () => {
    if (maxWidth <= 0) {
      return '';
    }

    if (typeof text !== 'string') {
      return text;
    }

    const availableWidth = maxWidth;

    // 移除 <mark> 标签
    const groups = text.split(/<\/?mark>/g);

    // 计算最大宽度字符串
    let truncatedText = '';
    let currentWidth = 0;
    let temp = true;
    const length = groups.length;
    let groupIndex = 0;
    groupLoop: for (const group of groups) {
      groupIndex++;

      for (const char of group) {
        const charWidth = getTextWidth(char);
        if (currentWidth + charWidth > availableWidth) {
          break groupLoop;
        }
        truncatedText += char;
        currentWidth += charWidth;
      }

      if (groupIndex < length) {
        truncatedText += temp ? '<mark>' : '</mark>';
        temp = !temp;
      }
    }

    if (!temp) {
      truncatedText += '</mark>';
    }

    const openingTagPattern = /<mark>/g;
    const closingTagPattern = /<\/mark>/g;

    // 计算截取文本中的 <mark> 和 </mark> 标签数量
    const openCount = (truncatedText.match(openingTagPattern) || []).length;
    const closeCount = (truncatedText.match(closingTagPattern) || []).length;

    // 如果 <mark> 标签数量多于 </mark>，则追加一个 </mark>
    if (openCount > closeCount) {
      truncatedText += '</mark>';
    }

    if (!temp) {
      truncatedText += '</mark>';
    }

    return truncatedText;
  };

  const result = truncateTextWithCanvas();
  delayDestroyCanvasInstance();
  return result;
};
