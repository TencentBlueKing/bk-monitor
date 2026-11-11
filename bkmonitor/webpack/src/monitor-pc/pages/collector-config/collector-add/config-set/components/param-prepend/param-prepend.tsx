/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import './param-prepend.scss';

interface IProps {
  /** 参数说明（浮层第三行） */
  description?: string;
  /** 前置标签显示文案；不传时依次回退到 name / description */
  label?: string;
  /** 参数名称（浮层第一行） */
  name?: string;
  required?: boolean;
  /** 浮层定位参数，纯 UI 行为 */
  tippyOptions?: object;
  /** 参数类型的显示文本（浮层第二行）；i18n 与字典映射由调用方完成 */
  type?: string;
}

@Component({ name: 'ParamPrepend' })
export default class ParamPrepend extends tsc<IProps> {
  @Prop({ type: String, default: '' }) label: string;
  @Prop({ type: String, default: '' }) name: string;
  @Prop({ type: String, default: '' }) type: string;
  @Prop({ type: String, default: '' }) description: string;
  @Prop({ type: Boolean, default: false }) required: boolean;
  @Prop({ type: Object, default: () => ({ distance: 10 }) }) tippyOptions: object;

  get displayText() {
    return this.label || this.name || this.description;
  }

  render() {
    return (
      <bk-popover
        placement='top'
        tippy-options={this.tippyOptions}
      >
        <div class={['prepend-text', 'param-prepend-text', { required: this.required }]}>{this.displayText}</div>
        <div
          class='param-prepend-content'
          slot='content'
        >
          <div>
            {this.$t('参数名称')}
            {' : '}
            {this.name}
          </div>
          <div>
            {this.$t('参数类型')}
            {' : '}
            {this.type}
          </div>
          <div>
            {this.$t('参数说明')}
            {' : '}
            {this.description || '--'}
          </div>
        </div>
      </bk-popover>
    );
  }
}
