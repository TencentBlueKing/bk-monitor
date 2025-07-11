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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { concatBKOtherDocsUrl, DOCS_LINK_MAP } from 'monitor-common/utils/docs';

import './log-metric-info.scss';

@Component
export default class MyComponent extends tsc<object> {
  @Prop() a: number;
  @Ref('helpContent') helpContentRef: HTMLDivElement;
  helpPopoverInstance: any = null;
  docCenterUrl = concatBKOtherDocsUrl(DOCS_LINK_MAP.BKOther.bkLogQueryString);
  beforeDestroy() {
    this.handleMouseLeave();
  }
  handleMouseEnter(e: MouseEvent) {
    if (!this.helpPopoverInstance) {
      this.helpPopoverInstance = this.$bkPopover(e.target, {
        content: this.helpContentRef,
        placement: 'bottom-start',
        distance: 9,
        theme: 'light',
        arrow: true,
        interactive: true,
        hideOnClick: true,
      });
    }
    if (!this.helpPopoverInstance?.state?.isShown) {
      this.helpPopoverInstance?.show?.(100);
    }
  }
  handleMouseLeave() {
    this.helpPopoverInstance?.hide?.();
    this.helpPopoverInstance?.destroy?.();
    this.helpPopoverInstance = null;
  }
  render() {
    return (
      <span class='log-metric-info'>
        <span
          class='icon-monitor icon-tips'
          onMouseenter={this.handleMouseEnter}
        />
        <div style='display: none;'>
          <div
            ref='helpContent'
            class='help-content'
          >
            <div>
              {this.$t('可输入SQL语句进行快速查询')}
              {this.docCenterUrl && (
                <a
                  class='tips-link'
                  href={this.docCenterUrl}
                  rel='noopener noreferrer'
                  target='_blank'
                >
                  {this.$t('查看语法')}
                  <span class='icon-monitor icon-fenxiang' />
                </a>
              )}
            </div>
            <div class='title'>{this.$t('精确匹配')}</div>
            <div class='detail'>author:"John Smith" AND age:20</div>
            <div class='title'>{this.$t('字段名匹配')}</div>
            <div class='detail'>status:active</div>
            <div class='detail'>title:(quick brown)</div>
            <div class='title'>{this.$t('字段名模糊匹配')}</div>
            <div class='detail'>vers\*on:(quick brown)</div>
            <div class='title'>{this.$t('通配符匹配')}</div>
            <div class='detail'>qu?ck bro*</div>
            <div class='title'>{this.$t('正则匹配')}</div>
            <div class='detail'>name:/joh?n(ath[oa]n/</div>
            <div class='title'>{this.$t('范围匹配')}</div>
            <div class='detail'>count:[1 TO 5]</div>
            <div class='detail'>count:[1 TO 5]</div>
            <div class='detail'>count:[10 TO *]</div>
          </div>
        </div>
      </span>
    );
  }
}
