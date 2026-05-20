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

/** 高亮分段项 */
interface HighlightSegment {
  str: string;
  style: string | null;
  isHighLight?: boolean;
}

/** <mark> 标签高亮样式（与 isUnique 过滤关键词一致） */
const MARK_HIGHLIGHT_STYLE = 'color: #FF5656; font-size: 12px; font-weight: 700;';

/**
 * 解析 <mark> 标签，将标记内容转为高亮分段
 * - <mark>keyword</mark> → { str: 'keyword', style: MARK_HIGHLIGHT_STYLE }
 * - 其他文本 → { str: '...', style: null }
 */
const parseMarkTags = (str: string): HighlightSegment[] => {
  const segments: HighlightSegment[] = [];
  const markRegex = /<mark>([\s\S]*?)<\/mark>/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = markRegex.exec(str)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ str: str.slice(lastIndex, match.index), style: null });
    }
    segments.push({ str: match[1], style: MARK_HIGHLIGHT_STYLE });
    lastIndex = markRegex.lastIndex;
  }

  if (lastIndex < str.length) {
    segments.push({ str: str.slice(lastIndex), style: null });
  }

  return segments.length > 0 ? segments : [{ str, style: null }];
};

/** 高亮配置项 */
export interface HighlightItem {
  str: string;
  style: string;
  isUnique: boolean;
}

/**
 * 将字符串按高亮规则拆分为分段数组
 * 逻辑与 highlight-html.js 严格一致：
 * 1. 先处理 isUnique=true 的高亮项（用于过滤关键字红色标记）
 * 2. 再处理 isUnique=false 的高亮项（全局匹配，用于高亮关键词彩色标记）
 */
export const highlightStringToArray = (
  str: string,
  highlights: HighlightItem[],
  caseInsensitive: boolean,
): HighlightSegment[] => {
  let resultArray: HighlightSegment[] = parseMarkTags(str);

  // 先处理 isUnique 为 true 的高亮项
  for (const highlight of highlights.filter(h => h.isUnique)) {
    const { str: searchStr, style } = highlight;
    const regexFlags = caseInsensitive ? '' : 'i';

    const re = new RegExp(searchStr.replace(/[-[\]{}()*+?.,\\^$|#\s*]/g, '\\$&'), regexFlags);
    const tempResultArray: HighlightSegment[] = [];

    resultArray.forEach((segment) => {
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
          tempResultArray.push({ str: matchedText, style });
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
    .forEach((highlight) => {
      const { str: searchStr, style } = highlight;
      const regexFlags = caseInsensitive ? 'g' : 'gi';

      const re = new RegExp(searchStr.replace(/[-[\]{}()*+?.,\\^$|#\s*]/g, '\\$&'), regexFlags);
      const tempResultArray: HighlightSegment[] = [];

      resultArray.forEach((segment) => {
        if (segment.style === null) {
          let matchIndex = 0;
          let match: RegExpExecArray | null;

          while ((match = re.exec(segment.str)) !== null) {
            const matchedText = match[0];
            const beforeMatch = segment.str.slice(matchIndex, match.index);
            if (beforeMatch) {
              tempResultArray.push({ str: beforeMatch, style: null });
            }
            tempResultArray.push({ str: matchedText, style, isHighLight: true });
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

const tagStyle = `padding: 2px 2px;
font-family: var(--bklog-v3-row-tag-font);
font-weight: 500;
background-color: #ebeef5;
border-radius: 2px;
display: inline-block;
line-height: 16px;`;

const rowStyle = `font-family: var(--bklog-v3-row-ctx-font);
font-size: var(--table-fount-size);`;

/**
 * 渲染高亮 HTML（与 highlight-html.js 渲染逻辑严格一致）
 * - 按 key:value 展示 item 的每个 entry
 * - value 按高亮数组渲染
 * - isShowKey 控制是否显示 key 标签
 * - data-index 属性区分 'light'（高亮）和 'filter'（过滤匹配）
 */
export const renderHighlightHtml = (
  item: Record<string, any>,
  lightList: HighlightItem[],
  ignoreCase: boolean,
  isShowKey: boolean,
) => {
  const parseList = Object.entries(item).map(([key, val]) => ({
    key,
    val: highlightStringToArray(val, lightList, ignoreCase),
  }));

  return (
    <span style='white-space: pre-wrap; word-break: break-all;'>
      {parseList.map(entry => (
        <span style={rowStyle}>
          {isShowKey && (
            <span>
              <span style={tagStyle}>{entry.key}:</span>
              {'\u00a0'}
            </span>
          )}
          {entry.val.map((seg) =>
            seg.style
              ? <span style={seg.style} data-index={seg?.isHighLight ? 'light' : 'filter'}>{seg.str}</span>
              : seg.str
          )}
          {'\u00a0'}
        </span>
      ))}
    </span>
  );
};
