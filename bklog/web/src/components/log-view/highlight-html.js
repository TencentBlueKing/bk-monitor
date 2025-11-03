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

export default {
  functional: true,
  props: {
    item: {
      type: Object,
      required: true,
    },
    ignoreCase: {
      type: Boolean,
      default: false,
    },
    lightList: {
      type: Array,
      default: () => [],
    },
    isShowKey: {
      type: Boolean,
      default: true,
    },
  },
  render(h, c) {
    const { item, lightList, ignoreCase, isShowKey } = c.props;

    /**
     * @desc: 包含和高亮的列表生成的展示数组
     * @param {String} str 展示的字符串
     * @param {Array} highlights 高亮数组 包含\高亮
     * @param {Boolean} caseInsensitive 是否大小写敏感
     * @returns {Array} 处理完后的高亮数组
     */
    const highlightStringToArray = (str, highlights, caseInsensitive) => {
      // 最终结果数组
      let resultArray = [{ str: str, style: null }];

      // 先处理 isUnique 为 true 的高亮项
      for (const highlight of highlights.filter(h => h.isUnique)) {
        const { str: searchStr, style } = highlight;
        let regexFlags = caseInsensitive ? '' : 'i';

        const re = new RegExp(searchStr.replace(/[-[\]{}()*+?.,\\^$|#\s*]/g, '\\$&'), regexFlags);
        const tempResultArray = [];

        resultArray.forEach(segment => {
          if (segment.style === null) {
            const match = re.exec(segment.str);
            if (match) {
              const matchedText = match[0];
              const matchIndex = match.index;
              const beforeMatch = segment.str.slice(0, matchIndex);
              const afterMatch = segment.str.slice(matchIndex + matchedText.length);

              if (beforeMatch) {
                tempResultArray.push({ str: beforeMatch, style: null });
              }
              tempResultArray.push({ str: matchedText, style: style });
              if (afterMatch) {
                tempResultArray.push({ str: afterMatch, style: null });
              }
            } else {
              tempResultArray.push(segment);
            }
          } else {
            tempResultArray.push(segment);
          }
        });

        resultArray = tempResultArray;
      }

      // 再处理 isUnique 为 false 的高亮项
      highlights
        .filter(h => !h.isUnique)
        .forEach(highlight => {
          const { str: searchStr, style } = highlight;
          let regexFlags = caseInsensitive ? 'g' : 'gi';

          const re = new RegExp(searchStr.replace(/[-[\]{}()*+?.,\\^$|#\s*]/g, '\\$&'), regexFlags);
          const tempResultArray = [];

          resultArray.forEach(segment => {
            if (segment.style === null) {
              let matchIndex = 0;
              let match;

              while ((match = re.exec(segment.str)) !== null) {
                const matchedText = match[0];
                const beforeMatch = segment.str.slice(matchIndex, match.index);
                if (beforeMatch) {
                  tempResultArray.push({ str: beforeMatch, style: null });
                }
                tempResultArray.push({ str: matchedText, style: style, isHighLight: true });
                matchIndex = match.index + matchedText.length;
              }

              if (matchIndex < segment.str.length) {
                tempResultArray.push({ str: segment.str.slice(matchIndex), style: null });
              }
            } else {
              tempResultArray.push(segment);
            }
          });

          resultArray = tempResultArray;
        });

      return resultArray;
    };

    const parseList = Object.entries(item).map(([key, val]) => ({
      key,
      val: highlightStringToArray(val, lightList, ignoreCase),
    }));
    return (
      <span style='white-space: normal;word-break: break-all; white-space: pre-wrap;'>
        {parseList.map(item => (
          <span>
            {isShowKey && (
              <span>
                <span style='background: #E6E9F0; color: #16171A; display: inline-block; line-height: 16px; padding: 0 2px;'>
                  {item.key}:
                </span>
                {'\u00a0'}
              </span>
            )}
            {item.val.map(item => {
              if (item.style)
                return (
                  <span
                    style={item.style}
                    data-index={item?.isHighLight ? 'light' : 'filter'}
                  >
                    {item.str}
                  </span>
                );
              return item.str;
            })}
            &nbsp;
          </span>
        ))}
      </span>
    );
  },
};
