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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

/*
 * @Date: 2021-06-10 17:44:25
 * @LastEditTime: 2021-06-24 11:45:29
 * @Description:
 */
import type { TranslateResult } from 'vue-i18n';

import './change-record.scss';

export interface ILabelRecordMap {
  createTime?: string | TranslateResult;
  createUser?: string | TranslateResult;
  updateTime?: string | TranslateResult;
  updateUser?: string | TranslateResult;
}
interface IChangeRecordProps {
  recordData: ILabelRecordMap;
  show: boolean;
}
@Component({
  name: 'ChangeRecord',
})
export default class MyComponent extends tsc<IChangeRecordProps, { onUpdateShow: boolean }> {
  value = false;
  labelMap: ILabelRecordMap = {};

  @Prop(Object)
  // 更新记录的数据
  recordData: ILabelRecordMap;

  @Prop(Boolean)
  // 是否弹窗
  show: boolean;

  @Watch('show', {
    immediate: true,
  })
  onShowChange(v) {
    this.value = v;
  }

  created() {
    this.labelMap = {
      createUser: this.$t('创建人:'),
      createTime: this.$t('创建时间'),
      updateUser: this.$t('最近更新人'),
      updateTime: this.$t('修改时间:'),
    };
  }

  // 弹窗状态变更时触发
  handleValueChange(v) {
    this.$emit('updateShow', v);
  }
  render() {
    return (
      <bk-dialog
        width='480'
        header-position='left'
        show-footer={false}
        title={this.$t('变更记录')}
        value={this.value}
        on-value-change={this.handleValueChange}
      >
        <ul class='change-record'>
          {Object.keys(this.labelMap).map(key => (
            <li
              key={key}
              class='change-record-item'
            >
              <span class='item-label'>{this.labelMap[key]}</span>
              <div class='item-content'>{this.recordData[key] || '--'}</div>
            </li>
          ))}
        </ul>
      </bk-dialog>
    );
  }
}
