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

import { copyText, Debounce } from 'monitor-common/utils/utils';

import './position-link.scss';

interface IProps {
  copyContent?: string;
  icon?: string;
  positionText: string;
  tipsText?: string;
}

/**
 * 复制文本按钮组件 - 默认复制url链接
 */
@Component
export default class PositionLink extends tsc<IProps> {
  /** 需要拷贝的内容 默认拷贝url */
  @Prop({ type: String, default: '' }) copyContent: string;
  /** 拷贝的icon 默认拷贝链接图标 */
  @Prop({ type: String, default: 'icon-copy-link' }) icon: string;
  /** 提示文本 */
  @Prop({ type: String, default: window.i18n.tc('复制链接') }) tipsText: string;
  /** 定位文本 */
  @Prop({ type: String }) positionText: string;

  /** 复制该页面链接 */
  @Debounce(200)
  handleCopyText() {
    let hasErr = false;
    copyText(this.copyContent || location.href, errMsg => {
      this.$bkMessage({
        message: errMsg,
        theme: 'error',
      });
      hasErr = !!errMsg;
    });
    if (!hasErr) this.$bkMessage({ theme: 'success', message: this.$t('复制成功') });
  }
  render() {
    return (
      <div
        class='position-bar'
        v-bk-tooltips={{
          content: this.tipsText,
          delay: 200,
          boundary: 'window',
          disabled: !this.tipsText,
          placement: 'right',
          allowHTML: false,
        }}
        onClick={this.handleCopyText}
      >
        <i class='icon-monitor icon-dingwei1' />
        <span class='position-text'>{this.positionText}</span>
        <span
          style='font-size: 12px;'
          class={['icon-monitor', 'copy-text-button', this.icon]}
        />
      </div>
    );
  }
}
