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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

interface IProps {
  caseSensitive?: boolean;
  content: string;
  keyword: string;
}

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // 转义特殊字符
}
@Component
export default class TextHighlighter extends tsc<IProps> {
  @Prop({ type: String, default: '' }) content: string;
  @Prop({ type: String, default: '' }) keyword: string;
  @Prop({ type: Boolean, default: false }) caseSensitive: string;

  get processedFragments() {
    return this.splitHighlightFragments(this.content, this.keyword);
  }

  splitHighlightFragments(content: string, keyword: string) {
    const escapedKeyword = escapeRegExp(keyword);
    if (!keyword) return [{ text: content, highlight: false }];

    const regex = new RegExp(`(${escapedKeyword})`, 'gi');
    const tokens = content.split(regex);

    return tokens.filter(Boolean).map(token => ({
      text: token,
      highlight: this.caseSensitive ? token === keyword : token.toLowerCase() === keyword.toLowerCase(),
    }));
  }

  render() {
    return (
      <span>
        {this.processedFragments.map(fragment => {
          if (fragment.highlight) {
            return <span class='highlight'>{fragment.text}</span>;
          }
          return fragment.text;
        })}
      </span>
    );
  }
}
