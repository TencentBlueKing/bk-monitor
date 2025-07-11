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

import { Component, Prop, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './index.scss';

interface IProps {
  showType: string;
  lightList: Array<[]>;
}

@Component
export default class LogViewControl extends tsc<IProps> {
  @Prop({ default: 'log', type: String }) showType: string;
  @Prop({ default: () => [], type: Array }) lightList: Array<[]>;
  @Ref('jumpInput') jumpInputRef: HTMLElement;

  currentViewIndex = 1;
  catchViewIndex = 1;
  highlightHtmlList: Element[] | NodeListOf<Element> = [];
  lightSize = 0;
  focus = false;
  colorList = [
    {
      color: [
        {
          dark: '#324260',
          light: '#E1ECFF',
        },
      ],
      name: window.mainComponent.$t('默认定位'),
    },
    {
      color: [
        {
          dark: '#553C1B',
          light: '#FFE8C3',
        },
      ],
      name: window.mainComponent.$t('上下文命中'),
    },
    {
      color: [
        {
          dark: '#294832',
          light: '#2DCB56',
        },
      ],
      name: window.mainComponent.$t('新增'),
    },
    {
      color: [],
      name: window.mainComponent.$t('高亮'),
    },
  ];

  get currentShowType() {
    return this.showType === 'log' ? 'light' : 'dark';
  }

  @Watch('lightList', { deep: true })
  watchLightList(v) {
    !!v.length ? this.initLightItemList() : this.clearLightCatch();
  }
  @Watch('showType')
  watchShowType() {
    if (this.lightSize) {
      this.highlightHtmlList[this.currentViewIndex - 1].style.opacity = 1;
    }
  }

  initLightItemList(lightList = this.lightList, direction = '') {
    this.highlightHtmlList = document.querySelectorAll('[data-index="light"]');
    this.lightSize = this.highlightHtmlList.length;
    if (this.lightSize) {
      const markDom = document.querySelector('.dialog-log-markdown');
      const markTop = markDom.getBoundingClientRect().top;
      let isFindShow = false;
      for (let index = 0; index < this.highlightHtmlList.length; index++) {
        const iItemTop = this.highlightHtmlList[index].getBoundingClientRect().top;
        if (iItemTop > markTop) {
          this.currentViewIndex = Number(index) + 1;
          this.catchViewIndex = this.currentViewIndex;
          this.highlightHtmlList[index].style.opacity = 1;
          isFindShow = true;
          break;
        }
      }
      if (!isFindShow && direction !== 'top' && direction !== 'down') {
        this.catchViewIndex = this.highlightHtmlList.length;
        this.handelChangeLight(this.highlightHtmlList.length);
      }
      this.colorList[3].color = (lightList as any).map(item => item.color);
    }
  }

  handelChangeLight(page: number) {
    this.catchViewIndex = this.currentViewIndex;
    this.currentViewIndex = page > this.highlightHtmlList.length ? 1 : page;
    const viewIndex = this.currentViewIndex - 1;
    const catchIndex = this.catchViewIndex - 1;
    this.highlightHtmlList[viewIndex].scrollIntoView({
      behavior: 'instant',
      block: 'center',
      inline: 'center',
    });
    this.highlightHtmlList[catchIndex].style.opacity = 0.5;
    this.highlightHtmlList[viewIndex].style.opacity = 1;
    this.setInputIndexShow(this.currentViewIndex);
  }

  clearLightCatch() {
    this.lightSize = 0;
    this.currentViewIndex = 1;
    this.catchViewIndex = 1;
    this.highlightHtmlList = [];
    this.colorList[3].color = [];
  }

  handleInputChange(event) {
    const $target = event.target;
    const value = parseInt($target.textContent, 10);
    // 无效值不抛出事件
    if (!value || value < 1 || value > this.lightSize || value === this.currentViewIndex) return;
    this.currentViewIndex = value;
  }

  handleBlur() {
    this.focus = false;
    if (typeof this.catchViewIndex !== 'string') this.catchViewIndex = this.currentViewIndex;
    this.handelChangeLight(this.currentViewIndex);
  }

  handleKeyDown(e) {
    if (['Enter', 'NumpadEnter'].includes(e.code)) {
      this.focus = true;
      this.handelChangeLight(this.currentViewIndex + 1);
      e.preventDefault();
    }
  }

  setInputIndexShow(v: number) {
    this.jumpInputRef && (this.jumpInputRef.textContent = String(v));
  }

  render() {
    return (
      <div class={['markdown-control', `control-${this.currentShowType}`]}>
        <div class='left'>
          {this.colorList.map((item, index) => {
            if (!item.color.length) return undefined;
            return (
              <div class='color-item'>
                {item.color.map(cItem => (
                  <div
                    style={{ backgroundColor: index === 3 ? cItem.dark : cItem[this.currentShowType] }}
                    class='color-block'
                  ></div>
                ))}
                <span>{item.name}</span>
              </div>
            );
          })}
        </div>
        <div class='right'>
          {!!this.lightSize && (
            <div>
              <div class={['jump-input-wrapper', { focus: this.focus }]}>
                <span
                  ref='jumpInput'
                  class='jump-input'
                  contenteditable
                  onBlur={this.handleBlur}
                  onFocus={() => (this.focus = true)}
                  onInput={this.handleInputChange}
                  onKeydown={this.handleKeyDown}
                >
                  {this.catchViewIndex}
                </span>
                <span class={['page-total', { focus: this.focus }]}>/ {this.lightSize}</span>
              </div>
              <div
                class='jump-btn'
                onClick={() => {
                  if (this.currentViewIndex === 1) return;
                  this.handelChangeLight(this.currentViewIndex - 1);
                }}
              >
                <i class='bk-icon icon-angle-up'></i>
              </div>
              <div
                class='jump-btn next'
                onClick={() => {
                  if (this.currentViewIndex === this.lightSize) return;
                  this.handelChangeLight(this.currentViewIndex + 1);
                }}
              >
                <i class='bk-icon icon-angle-up'></i>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }
}
