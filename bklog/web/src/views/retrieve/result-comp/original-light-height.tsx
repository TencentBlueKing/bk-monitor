/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import { Component, Prop } from 'vue-property-decorator';
import './original-light-height.scss';

interface IProps {
  originJsonStr: string;
}

@Component
export default class QueryStatement extends tsc<IProps> {
  /** 原始日志字符串 */
  @Prop({ type: String, default: '' }) originJsonStr: string;

  segmentReg = /<black-mark>(.*?)<\/black-mark>|<mark>(.*?)<\/mark>/;

  /** 正则切割原始日志 */
  get splitList() {
    const value = this.originJsonStr;
    let arr = value.split(this.segmentReg);
    arr = arr.filter(val => val && val.length);
    return arr;
  }

  /** key高亮列表 */
  get blackMarkList() {
    let markVal = this.originJsonStr
      .toString()
      .match(/(<black-mark>).*?(<\/black-mark>)/g) || [];
    if (markVal.length) {
      markVal = markVal.map(item => item.replace(/<black-mark>/g, '').replace(/<\/black-mark>/g, ''),
      );
    }
    return markVal;
  }
  /** 检索的高亮列表 */
  get markList() {
    let markVal = this.originJsonStr.toString().match(/(<mark>).*?(<\/mark>)/g) || [];
    if (markVal.length) {
      markVal = markVal.map(item => item.replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
      );
    }
    return markVal;
  }
  /** 判断是否是key */
  checkBlackMark(splitItem) {
    if (!this.blackMarkList.length) return false;
    // 以句号开头或句号结尾的分词符匹配成功也高亮展示
    return this.blackMarkList.some(
      item => item === splitItem
        || splitItem.startsWith(`.${item}`)
        || splitItem.endsWith(`${item}.`),
    );
  }
  /** 判断是否是检索高亮 */
  checkMark(splitItem) {
    if (!this.markList.length) return false;
    // 以句号开头或句号结尾的分词符匹配成功也高亮展示
    return this.markList.some(
      item => item === splitItem
        || splitItem.startsWith(`.${item}`)
        || splitItem.endsWith(`${item}.`),
    );
  }

  render() {
    return (
      <span class="origin-content">
        {this.splitList.map((item) => {
          if (item === '\n') {
            return <br />;
          }
          if (this.checkBlackMark(item)) {
            return <span class="black-mark">{item}</span>;
          }
          if (this.checkMark(item)) {
            return <mark>{item}</mark>;
          }
          return item;
        })}
      </span>
    );
  }
}
