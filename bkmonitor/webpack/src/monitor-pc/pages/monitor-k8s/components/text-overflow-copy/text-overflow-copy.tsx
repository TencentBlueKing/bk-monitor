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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from '../../../../../monitor-common/utils/utils';
import { ITableItem } from '../../typings';

import './text-overflow-copy.scss';

interface IProps {
  val: ITableItem<'string'>;
}
@Component
export default class TextOverflowCopy extends tsc<IProps, {}> {
  @Prop({ default: '' }) val: ITableItem<'string'>;
  @Ref('wrapRef') wrapRef: HTMLDivElement;

  hasCopy = false;

  get text() {
    return Array.isArray(this.val) ? this.val.join(',') : this.val;
  }

  @Watch('val', { immediate: true })
  handleTextChange() {
    this.$nextTick(() => {
      if (!this.wrapRef) {
        this.hasCopy = false;
        return;
      }
      const { scrollWidth, clientWidth } = this.wrapRef;
      this.hasCopy = scrollWidth > clientWidth;
    });
  }

  handleCopy() {
    copyText(this.text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }

  render() {
    return (
      <div
        class={{ 'text-overflow-copy-comp': true, 'has-copy': this.hasCopy }}
        ref='wrapRef'
      >
        {this.val.icon &&
          (this.val.icon.length > 30 ? (
            <img
              src={this.val.icon}
              alt=''
            />
          ) : (
            <i class={['icon-monitor', 'string-icon', this.val.icon]} />
          ))}
        {this.text}
        {this.hasCopy && (
          <span
            class='icon-monitor icon-mc-copy'
            onClick={this.handleCopy}
          ></span>
        )}
      </div>
    );
  }
}
