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
import { getFlatObjValues } from '@/common/util';
import './original-light-height.scss';

interface IProps {
  originJson: Object;
}

@Component
export default class QueryStatement extends tsc<IProps> {
  /** 原始日志 */
  @Prop({ type: Object, required: true }) originJson;

  segmentReg = /<mark>(.*?)<\/mark>/g;

  // 扁平化对象所有数据
  get fieldMapData() {
    const { newObject } = getFlatObjValues(this.originJson || {});
    return Object.entries(newObject);
  }

  /** 检索的高亮列表 */
  markItem(str: any) {
    let splitList = str
      .toString()
      .split(this.segmentReg)
      .filter(Boolean)
      .map(item => ({
        str: item,
        isMark: false,
      }));
    // 过滤切割的数组 判断所有的值filter(Boolean)清空所有空字符串后 若为空数组 则补一个空字符串展示位
    if (!splitList.length) splitList = ['""'];
    let markVal = str.toString().match(this.segmentReg);
    if (markVal?.length) {
      splitList.forEach((el) => {
        markVal = markVal.map(item => item.replace(/<mark>/g, '').replace(/<\/mark>/g, ''));
        markVal.includes(el.str) && (el.isMark = true); // 给匹配到的数据 mark高亮设置为true
      });
    }
    return splitList;
  }

  render() {
    const valueStr = (val) => {
      return this.markItem(val).map((item) => {
        if (item.isMark) return <mark>{item.str}</mark>;
        return item.str || '""';
      });
    };
    return (
      <span class="origin-content">
        {this.fieldMapData.map(([key, value]) => {
          return (
            <span>
              <span class="black-mark">&nbsp;{key}:&nbsp;</span>
              <span class="origin-value">{valueStr(value)}</span>
            </span>
          );
        })}
      </span>
    );
  }
}
