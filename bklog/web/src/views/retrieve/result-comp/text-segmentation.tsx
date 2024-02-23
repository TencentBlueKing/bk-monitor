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
import './text-segmentation.scss';

interface IProps {
  field: any;
  content: String | Number;
  menuClick: Function;
}

@Component
export default class QueryStatement extends tsc<IProps> {
  @Prop({ type: Object, required: true }) field: any;
  @Prop({ type: [String, Number], required: true }) content: string | number;
  @Prop({ type: Function, required: true }) menuClick: Function;

  /** 当前选中分词 */
  curValue = '';
  /** 检索高亮分词字符串 */
  markRegStr = '<mark>(.*?)</mark>';
  /** 默认分词字符串 */
  // eslint-disable-next-line
  segmentRegStr = ",&*+:;?^=!$<>'\"{}()|[\\]/\\\|\\s\\r\\n\\t-";
  /** 分词超出最大数量边界下标 */
  segmentLimitIndex = 0;
  /** 支持分词最大数量 */
  limitCount = 256;
  /** 当前点击的分词实例 */
  currentEvent = null;
  /** 超出隐藏实例 */
  intersectionObserver = null;

  popoverInstance = null;

  get currentFieldReg() {
    try {
      if (!this.field.is_analyzed) return new RegExp(this.markRegStr);
      let currentFieldRegStr = this.segmentRegStr;
      if (this.field.tokenize_on_chars) currentFieldRegStr = this.field.tokenize_on_chars;
      return new RegExp(`${this.markRegStr}|([${currentFieldRegStr}])`);
    } catch (error) {
      return new RegExp(this.markRegStr);
    }
  }

  get isVirtual() {
    return this.field.field_type === '__virtual__';
  }

  get splitList() {
    const value = this.content.toString();
    let arr = value.split(this.currentFieldReg);
    arr = arr.filter(val => val && val.length);
    this.getLimitValidIndex(arr);
    return arr;
  }

  get markList() {
    let markVal = this.content.toString().match(/(<mark>).*?(<\/mark>)/g)
      || ([] as RegExpMatchArray[]);
    if (markVal.length) {
      markVal = markVal.map(item => item.replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
      );
    }
    return markVal;
  }

  /**
   * @desc 获取限制最大分词数下标
   * @param { Array } list
   */
  getLimitValidIndex(list: Array<string>) {
    let segmentCount = 0;
    this.segmentLimitIndex = 0;
    for (let index = 0; index < list.length; index++) {
      this.segmentLimitIndex += 1;
      if (!this.currentFieldReg.test(list[index])) {
        segmentCount += 1;
      }
      if (segmentCount > this.limitCount) break;
    }
  }

  handleClick(e, value) {
    if (!value.toString() || value === '--') return;
    this.handleDestroy();
    this.curValue = value;
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.$refs.moreTools,
      trigger: 'click',
      placement: 'bottom-start',
      arrow: true,
      theme: 'light',
      interactive: true,
      extCls: 'event-tippy-content',
      onHidden: () => {
        this.unregisterObserver();
        this.popoverInstance && this.popoverInstance.destroy();
        this.popoverInstance = null;
        this.currentEvent.classList.remove('focus-text');
      },
      onShow: () => {
        setTimeout(this.registerObserver, 20);
        this.currentEvent = e.target;
        this.currentEvent.classList.add('focus-text');
      },
    });
    this.popoverInstance && this.popoverInstance.show(10);
  }
  // 注册Intersection监听
  registerObserver() {
    if (this.intersectionObserver) this.unregisterObserver();
    this.intersectionObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (this.intersectionObserver) {
          if (entry.intersectionRatio <= 0) {
            this.popoverInstance.hide();
          }
        }
      });
    });
    this.intersectionObserver.observe(this.$el);
  }
  unregisterObserver() {
    if (this.intersectionObserver) {
      this.intersectionObserver.unobserve(this.$el);
      this.intersectionObserver.disconnect();
      this.intersectionObserver = null;
    }
  }
  handleDestroy() {
    if (this.popoverInstance) {
      this.popoverInstance?.hide(0);
      this.popoverInstance?.destroy();
      this.popoverInstance = null;
      this.curValue = '';
    }
  }
  checkMark(splitItem) {
    if (!this.markList.length) return false;
    // 以句号开头或句号结尾的分词符匹配成功也高亮展示
    return this.markList.some(
      item => item === splitItem
        || splitItem.startsWith(`.${item}`)
        || splitItem.endsWith(`${item}.`),
    );
  }

  handleMenuClick(event: string, isLink = false) {
    this.menuClick(event, this.curValue, isLink);
    this.handleDestroy();
  }

  render() {
    return (
      <span class="log-content-wrapper">
        {this.isVirtual ? (
          <span class="null-item">{this.content}</span>
        ) : (
          <span class="segment-content">
            {this.splitList.map((item, index) => {
              if (item === '\n') return <br />;
              if (this.currentFieldReg.test(item)) return item;
              if (this.checkMark(item)) return (
                  <mark onClick={$event => this.handleClick($event, item)}>
                    {item}
                  </mark>
              );
              if (index < this.segmentLimitIndex) return (
                  <span
                    class="valid-text"
                    onClick={$event => this.handleClick($event, item)}
                  >
                    {item}
                  </span>
              );
              return item;
            })}
          </span>
        )}

        <div v-show={ false }>
        <div ref="moreTools" class="event-icons">
          <div class="event-box">
            <span class="event-btn" onClick={() => this.handleMenuClick('copy')}>
              <i class="icon log-icon icon-copy"></i>
              <span>{ this.$t('复制') }</span>
            </span>
          </div>
          <div class="event-box">
            <span class="event-btn" onClick={() => this.handleMenuClick('is')}>
              <i class="icon bk-icon icon-plus-circle"></i>
              <span>{ this.$t('添加到本次检索') }</span>
            </span>
            <div
              class="new-link"
              v-bk-tooltips={ this.$t('新开标签页') }
              onClick={(e) => {
                e.stopPropagation();
                this.handleMenuClick('is', true);
              }}>
              <i class="log-icon icon-jump"></i>
            </div>
          </div>
          <div class="event-box">
            <span class="event-btn" onClick={() => this.handleMenuClick('not')}>
              <i class="icon bk-icon icon-minus-circle"></i>
              <span>{ this.$t('从本次检索中排除') }</span>
            </span>
            <div
              class="new-link"
              v-bk-tooltips={ this.$t('新开标签页') }
              onClick={(e) => {
                e.stopPropagation();
                this.handleMenuClick('new-page', true);
              }}>
              <i class="log-icon icon-jump"></i>
            </div>
          </div>
        </div>
      </div>
      </span>
    );
  }
}
