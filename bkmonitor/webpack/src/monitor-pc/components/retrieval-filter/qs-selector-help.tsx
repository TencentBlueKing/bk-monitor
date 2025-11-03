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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { skipToDocsLink } from 'monitor-common/utils/docs';

import './qs-selector-help.scss';

@Component
export default class QsSelectorHelp extends tsc<object> {
  handleClick() {
    skipToDocsLink('bkLogQueryString');
  }
  render() {
    return (
      <div class='retrieval-filter__qs-selector-help-component'>
        <div class='header-operate'>
          <span>{this.$t('如何查询')}?</span>
          <span
            class='link-btn'
            onClick={this.handleClick}
          >
            <span>{this.$t('查询语法')}</span>
            <span class='icon-monitor icon-fenxiang' />
          </span>
        </div>
        <div class='content-helps'>
          <div class='help-item'>
            <div class='item-title'>{this.$t('精确匹配（支持 AND、OR）')}：</div>
            <div class='item-content'>author:"John Smith" AND age:20</div>
          </div>
          <div class='help-item'>
            <div class='item-title'>{this.$t('精确匹配（支持 AND、OR）')}：</div>
            <div class='item-content'>
              <div>status:active</div>
              <div>title:(quick brown)</div>
            </div>
          </div>
          <div class='help-item'>
            <div class='item-title'>{this.$t('字段名模糊匹配')}：</div>
            <div class='item-content'>vers\*on:(quick brown)</div>
          </div>
          <div class='help-item'>
            <div class='item-title'>{this.$t('通配符匹配')}：</div>
            <div class='item-content'>qu?ck bro*</div>
          </div>
          <div class='help-item'>
            <div class='item-title'>{this.$t('正则匹配')}：</div>
            <div class='item-content'>name:/joh?n(ah[oa]n)/</div>
          </div>
          <div class='help-item'>
            <div class='item-title'>{this.$t('范围匹配')}：</div>
            <div class='item-content'>
              <div>count:[1 TO 5]</div>
              <div>{'count:[1 TO 5}'}</div>
              <div>count:[10 TO *]</div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
