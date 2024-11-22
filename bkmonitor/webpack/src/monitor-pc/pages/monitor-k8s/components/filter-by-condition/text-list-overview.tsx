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

import './text-list-overview.scss';

interface ITextsItem {
  id: string;
  name: string;
}

interface IProps {
  textList: ITextsItem[];
}

@Component
export default class TextListOverview extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) textList: ITextsItem[];

  texts: ITextsItem[] = [];
  delCount = 0;

  @Watch('textList', { immediate: true })
  handleWatchTextList() {
    this.texts = this.textList.map(item => {
      let name = item.name;
      if (item.name.length > 20) {
        name = `${name.slice(0, 20)}...`;
      }
      return {
        ...item,
        name,
      };
    });
    // this.overflowCountRender();
  }

  async overflowCountRender() {
    await this.$nextTick();
    let target = this.$el;
    while (target) {
      if (target.classList.contains('filter-by-condition-tag')) {
        break;
      }
      target = target.parentNode;
    }
    const wrapWidth = target.clientWidth;
    let delCount = 0;
    console.log('----', target, wrapWidth);
    if (wrapWidth > 400) {
      const visibleWrap = this.$el.querySelector('.condition-text-list-overview-visible');
      const textListEl = Array.from(visibleWrap.children);
      console.log(textListEl, visibleWrap);
      let tempW = wrapWidth;
      for (let i = textListEl.length - 1; i >= 0; i--) {
        const textEl = textListEl[i];
        tempW -= textEl.clientWidth;
        console.log(tempW, textEl.clientWidth);
        delCount += 1;
        if (tempW < 400) {
          break;
        }
      }
    }
    this.delCount = delCount;
  }

  textsRender(isVisible = false) {
    if (isVisible) {
      return this.texts.map((item, index) => (
        <span key={`${item.id}_index`}>
          {index > 0 && <span class='split'>, </span>}
          <span
            key={item.id}
            class='text'
          >
            {item.name}
          </span>
        </span>
      ));
    }
    return this.texts.slice(0, this.texts.length - this.delCount).map((item, index) => (
      <span key={`${item.id}_index`}>
        {index > 0 && <span class='split'>, </span>}
        <span
          key={item.id}
          class='text'
        >
          {item.name}
        </span>
      </span>
    ));
  }

  render() {
    return (
      <span class='condition-text-list-overview'>
        {this.textsRender()}
        {this.delCount ? `+${this.delCount}` : undefined}
        <div class='condition-text-list-overview-visible'>{this.textsRender(true)}</div>
      </span>
    );
  }
}
