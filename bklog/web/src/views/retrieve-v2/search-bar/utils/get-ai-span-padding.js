export const AI_SPAN_PADDING = {
  en: '126px',
  'zh-cn': '94px',
};

/**
 * 按语言计算 custom-placeholder 相对输入提示的让位距离。
 * 空输入时给 is-focus-input::after 让位；有输入时收回。
 * @param {string} language cookie `blueking_language`
 * @param {number} inputValueLength
 * @returns {string}
 */
export function getAiSpanPaddingLeft(language, inputValueLength) {
  if (inputValueLength === 0) {
    return AI_SPAN_PADDING[language] ?? AI_SPAN_PADDING['zh-cn'];
  }

  return '0px';
}

/**
 * 空 slot 不施加 margin，避免空 li 参与 flex-wrap。
 * @param {boolean} isSlotEmpty
 * @param {string} paddingLeft
 * @returns {{ marginLeft: string } | undefined}
 */
export function getCustomPlaceholderStyle(isSlotEmpty, paddingLeft) {
  if (isSlotEmpty) {
    return undefined;
  }

  return { marginLeft: paddingLeft };
}
