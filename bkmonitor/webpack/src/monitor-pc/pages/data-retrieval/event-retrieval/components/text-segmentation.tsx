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

import type { EventRetrievalViewType } from '../../typings';

import './text-segmentation.scss';

@Component
export default class FieldFiltering extends tsc<EventRetrievalViewType.ITextSegment> {
  @Prop({ default: '', type: String }) content: string; // 键值
  @Prop({ default: '', type: String }) fieldType: string; // 键名

  segmentReg = /([,&*+:;?^=!$<>'"{}()|[\]/\\|\s\r\n\t]|[-])/;
  dimensionsReg = /^dimensions\.[\s\S]*$/; // 是否是以dimensions开头的字段名
  limitCount = 256; // 支持分词最大数量
  curValue = '';
  segmentLimitIndex = 0; // 可操作的最多分词量
  popoverInstance = null;
  /** 判断是否是需要分词操作操作 */
  get isNeedSegment() {
    return ['event.content'].includes(this.fieldType);
  }
  /** 分词列表数组 */
  get splitList() {
    let arr = this.content.split(this.segmentReg);
    arr = arr.filter(val => val.length);
    this.getLimitValidIndex(arr);
    return arr;
  }

  @Emit('menuClick')
  emitMenuClick(value: object) {
    return value;
  }

  // checkMark(item) {
  //   return false;
  // }
  /** 获取最大有效分词的数组下标 */
  getLimitValidIndex(list) {
    let segmentCount = 0;
    this.segmentLimitIndex = 0;
    for (const reg of list) {
      this.segmentLimitIndex += 1;
      if (!this.segmentReg.test(reg)) segmentCount += 1;
      if (segmentCount > this.limitCount) break;
    }
  }

  handleClick(e, value) {
    this.handleDestroy();

    this.curValue = value;
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.$refs.moreTools,
      trigger: 'click',
      placement: 'bottom',
      arrow: true,
      theme: 'light',
      interactive: true,
      extCls: 'event-tippy-content',
      onHidden: () => {
        this.popoverInstance?.destroy();
        this.popoverInstance = null;
      },
    });
    this.popoverInstance?.show(10);
  }

  handleMenuClick(type: string) {
    this.emitMenuClick({ type, value: this.curValue });
    this.handleDestroy();
  }

  handleDestroy() {
    if (this.popoverInstance) {
      this.popoverInstance?.hide(0);
      this.popoverInstance?.destroy();
      this.popoverInstance = null;
      this.curValue = '';
    }
  }

  splitRender(item: string, index: number) {
    if (item === '\n') return <br />;
    if (this.segmentReg.test(item)) return item;
    // if (this.checkMark(item)) return <mark onClick={e => this.handleClick(e, item)}>{item}</mark>; // 高亮预留
    if (index < this.segmentLimitIndex)
      return (
        <span
          class='valid-text'
          onClick={e => this.handleClick(e, item)}
        >
          {item}
        </span>
      );
    return item;
  }
  render() {
    return (
      <span class='log-content-wrapper'>
        {!this.isNeedSegment ? (
          <span style='word-break: break-all;'>{this.content}</span>
        ) : (
          <span class='segment-content'>{this.splitList.map((item, index) => this.splitRender(item, index))}</span>
        )}
        <div v-show={false}>
          <div
            ref='moreTools'
            class='event-icons'
          >
            <span
              class='icon bk-icon icon-close-circle'
              v-bk-tooltips={{ content: this.$t('添加查询语句'), delay: 300 }}
              onClick={() => this.handleMenuClick('is')}
            />
            <span
              class='icon icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: this.$t('复制'), delay: 300 }}
              onClick={() => this.handleMenuClick('copy')}
            />
          </div>
        </div>
      </span>
    );
  }
}
