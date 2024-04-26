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
import { Component, Prop, Emit } from 'vue-property-decorator';
import { getFlatObjValues } from '@/common/util';
import TextSegmentation from './text-segmentation';
import './original-light-height.scss';

interface IProps {
  originJson: object;
  visibleFields: Array<any>;
  isWrap: boolean;
  operatorConfig: object;
}
@Component
export default class QueryStatement extends tsc<IProps> {
  /** 原始日志 */
  @Prop({ type: Object, required: true }) originJson;
  @Prop({ type: Array<any>, required: true }) visibleFields;
  @Prop({ type: Boolean, required: true }) isWrap;
  @Prop({ type: Object, required: true }) operatorConfig;

  get visibleFieldsNameList() {
    return this.visibleFields.map(item => item.field_name);
  }

  get strOriginJson() {
    return JSON.stringify(this.fieldMapDataObj);
  }

  get unionIndexItemList() {
    return this.$store.getters.unionIndexItemList;
  }

  // 扁平化对象所有数据
  get fieldMapDataObj() {
    const { newObject } = getFlatObjValues(this.originJson || {});
    const visibleObject = {};
    Object.keys(newObject).forEach(el => {
      if (this.visibleFieldsNameList.includes(el)) {
        visibleObject[el] = newObject[el];
      }
    });
    const sortObject = this.visibleFields.reduce((pre, cur) => {
      let fieldValue = visibleObject[cur.field_name];
      if (this.operatorConfig.isShowSourceField && cur?.tag === 'union-source') {
        fieldValue =
          this.unionIndexItemList.find(item => item.index_set_id === String(this.originJson.__index_set_id__))
            ?.index_set_name ?? '';
      }
      pre[cur.field_name] = fieldValue ?? '';
      return pre;
    }, {});
    return sortObject;
  }

  @Emit('menuClick')
  handleEmitMenuClick(type, content, key, isLink) {
    const option = { fieldName: key, operation: type === 'not' ? 'is not' : type, value: content };
    const newMenuObj = { option, isLink };
    return newMenuObj;
  }

  getField(fieldName: string) {
    return this.visibleFields.find(item => item.field_name === fieldName);
  }

  render() {
    return (
      <span
        class='origin-content'
        title={this.isWrap ? '' : this.strOriginJson}
      >
        {Object.entries(this.fieldMapDataObj).map(([key, value]) => {
          return (
            <span>
              <span class='black-mark'>&nbsp;{key}:&nbsp;</span>
              <span class='origin-value'>
                <TextSegmentation
                  content={value}
                  field={this.getField(key)}
                  menu-click={(type, content, isLink) => this.handleEmitMenuClick(type, content, key, isLink)}
                />
              </span>
            </span>
          );
        })}
      </span>
    );
  }
}
