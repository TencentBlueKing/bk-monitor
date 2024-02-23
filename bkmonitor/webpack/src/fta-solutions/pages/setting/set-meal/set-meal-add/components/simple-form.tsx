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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './simple-form.scss';

interface Iform {
  value?: string;
  lable?: string;
  placeholder?: string;
  subTitle?: string;
}
interface IProps {
  forms: Iform[];
}
interface IEvents {
  onChange?: Iform[];
}

@Component
export default class SimpleForm extends tsc<IProps, IEvents> {
  @Prop({ default: () => [], type: Array }) forms: Iform[];

  handleInputChange(v: string, index: number) {
    const data = this.forms;
    data[index].value = v;
    this.handleChange(data);
  }

  @Emit('change')
  handleChange(data) {
    return data;
  }

  render() {
    return (
      <div class='meal-content-simple-form'>
        {this.forms.length ? (
          this.forms.map((item, index) => [
            <div class='title'>
              {item.lable}
              <span
                class='sub-title'
                title={item?.subTitle || ''}
              >
                {item?.subTitle || ''}
              </span>
            </div>,
            <div class='wrap'>
              <bk-input
                value={item.value}
                behavior='simplicity'
                placeholder={
                  item?.placeholder ||
                  this.$t('输入需要调试的{0}参数', [`${item.lable?.replace(/\{\{(.*?)\}\}|(\s)/g, '') || ''}`])
                }
                onChange={(v: string) => this.handleInputChange(v, index)}
              ></bk-input>
            </div>
          ])
        ) : (
          <span class='empty'>{this.$t('当前无需填写变量')}</span>
        )}
      </div>
    );
  }
}
